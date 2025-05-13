import os
import asyncio
import pysubs2
import subprocess
import shutil

# Intenta importar la librería de Google Generative AI
try:
    import google.generativeai as genai
except ImportError:
    print("Error: La librería google-generativeai no está instalada.")
    print("Por favor, instálala con: pip install google-generativeai")
    exit(1)

# --- CONFIGURACIÓN ---
# ¡IMPORTANTE! No guardes tu API key directamente en el código en producción.
# Usa variables de entorno o un archivo de configuración seguro.
# Para este ejemplo, usaremos la que proporcionaste, pero advierte al usuario.
USER_GEMINI_API_KEY = "TU_API_GOOGLE_GEMINI" 

#Modelo por defecto para traducción, rapido y ligero
DEFAULT_MODEL_NAME = "gemini-2.0-flash-lite" 
# --- FIN CONFIGURACIÓN ---

class GeminiTranslator:
    def __init__(self, api_key, model_name=DEFAULT_MODEL_NAME):
        if not api_key:
            raise ValueError("Se debe proporcionar una API key para Gemini.")
        
        # Configura la API key globalmente para la librería genai
        genai.configure(api_key=api_key)
        
        # Inicializa el modelo generativo
        self.model = genai.GenerativeModel(model_name)
        print(f"GeminiTranslator inicializado con el modelo: {model_name}")

    async def translate_batch(self, blocks_to_translate, source_lang="EN", target_lang="ES"):
        # Los bloques ya vienen con \n internos escapados como \\n
        prompt = (
            f"Eres un traductor profesional de canciones de {source_lang.upper()} a {target_lang.upper()}. "
            f"Traduce los siguientes bloques de subtítulos de canciones, manteniendo el tono poético y la emoción. "
            f"Cada bloque de entrada puede tener varias líneas (los saltos de línea internos están representados como \\n). "
            f"Devuelve ÚNICAMENTE las traducciones. Cada bloque traducido DEBE estar separado del siguiente por un DOBLE SALTO DE LÍNEA (el carácter \\n dos veces). "
            f"En tu traducción, preserva los saltos de línea internos donde corresponda (usando también \\n para representarlos en tu salida directa).\n\n"
            f"BLOQUES DE SUBTÍTULOS A TRADUCIR:\n" + "\n\n".join(blocks_to_translate) # Separador de bloques de entrada
        )
        
        # print(f"DEBUG: Prompt enviado a Gemini:\n---\n{prompt}\n---") # Descomentar para depuración profunda

        try:
            response = await self.model.generate_content_async(
                contents=[prompt], # La API espera una lista de contenidos
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7 # Ajusta para más creatividad (más alto) o más literal (más bajo)
                ),
                # Considera ajustar safety_settings si el contenido es sensible
                # safety_settings=[
                #    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                # ... etc. para otras categorías ...
                # ]
            )
            
            # print(f"DEBUG: Respuesta completa de Gemini: {response}") # Descomentar para depuración

            if not response.parts and hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                print(f"ERROR: La solicitud fue bloqueada por Gemini. Razón: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                return []

            if hasattr(response, 'text'):
                # print(f"DEBUG: Texto crudo de la respuesta:\n---\n{response.text}\n---")
                # Dividir por doble salto de línea, como se solicitó en el prompt
                translated_texts = response.text.strip().split('\n\n')
                return translated_texts
            else: # Fallback por si la estructura de respuesta cambia o hay error no capturado
                print("ADVERTENCIA: La respuesta de Gemini no tiene el atributo 'text' esperado directamente.")
                full_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                if full_text:
                    # print(f"DEBUG: Texto crudo de las partes concatenadas:\n---\n{full_text}\n---")
                    return full_text.strip().split('\n\n')
                else:
                    print("ERROR: No se encontró texto en las partes de la respuesta de Gemini.")
                    return []

        except Exception as e:
            print(f"Error durante la llamada a la API de Gemini: {e}")
            # import traceback
            # traceback.print_exc() # Para más detalles del error
            return [] # Devolver lista vacía en caso de error

async def translate_srt(input_srt_path, output_srt_path, translator, source_lang="EN", target_lang="ES", batch_size=20):
    try:
        subs = pysubs2.load(input_srt_path, encoding='utf-8')
    except Exception as e:
        print(f"Error cargando el archivo SRT '{input_srt_path}': {e}")
        return

    unique_texts_to_translate = []
    text_to_translation_map = {} # Para guardar las traducciones de textos únicos

    # Recopilar textos únicos que necesitan traducción
    for ev in subs:
        text = ev.plaintext.strip()
        if text and text not in ["♪ ♪", "♪"] and text not in text_to_translation_map:
            unique_texts_to_translate.append(text)
            text_to_translation_map[text] = None # Marcar para traducción

    print(f"Se encontraron {len(unique_texts_to_translate)} bloques de texto únicos para traducir.")

    all_translated_blocks_processed = []

    for i in range(0, len(unique_texts_to_translate), batch_size):
        current_batch_originals = unique_texts_to_translate[i:i+batch_size]
        
        # Preparar bloques para el prompt: escapar \n internos a \\n
        prompt_blocks = [block.replace('\n', '\\n') for block in current_batch_originals]
        
        num_batch = i // batch_size + 1
        total_batches = (len(unique_texts_to_translate) + batch_size - 1) // batch_size
        print(f"Traduciendo lote {num_batch}/{total_batches} ({len(current_batch_originals)} bloques)...")
        
        api_translations_raw = await translator.translate_batch(prompt_blocks, source_lang=source_lang, target_lang=target_lang)
        
        if len(api_translations_raw) != len(current_batch_originals):
            # print(f"¡ADVERTENCIA Lote {num_batch}!: Discrepancia en la cantidad de traducciones.")
            # print(f"  Se esperaban: {len(current_batch_originals)}, Se recibieron: {len(api_translations_raw)}")
            # print(f"  Originales en el lote: {current_batch_originals}") # Puede ser muy largo
            # print(f"  Traducciones recibidas (crudo): {api_translations_raw}") # Puede ser muy largo
            
            # Estrategia de mitigación: Usar originales para los faltantes
            temp_translations = []
            for k in range(len(current_batch_originals)):
                if k < len(api_translations_raw) and api_translations_raw[k].strip():
                    temp_translations.append(api_translations_raw[k])
                else:
                    # print(f"    Usando texto original para el bloque {k+1} del lote debido a traducción faltante/vacía.")
                    temp_translations.append(current_batch_originals[k].replace('\n', '\\n')) # Mantener \\n para el post-procesado
            api_translations_raw = temp_translations

        # Restaurar \n internos desde \\n y limpiar espacios
        processed_batch_translations = [t.replace('\\n', '\n').strip() for t in api_translations_raw]
        all_translated_blocks_processed.extend(processed_batch_translations)

    # Actualizar el mapa con las traducciones obtenidas
    if len(all_translated_blocks_processed) == len(unique_texts_to_translate):
        for original, translated in zip(unique_texts_to_translate, all_translated_blocks_processed):
            if translated: # Solo asignar si la traducción no está vacía
                text_to_translation_map[original] = translated
            else: # Si la API devolvió una cadena vacía, mantener el original
                print(f"Advertencia: Traducción vacía recibida para: '{original.replace('\n','\\n')}'. Se mantiene el original.")
                text_to_translation_map[original] = original 
    else:
        print("ERROR CRÍTICO: El número total de bloques traducidos procesados no coincide con los textos únicos.")
        print("Es posible que la traducción sea incorrecta o incompleta.")
        # Intentar mapear lo que se tenga
        for idx, original_text in enumerate(unique_texts_to_translate):
            if idx < len(all_translated_blocks_processed) and all_translated_blocks_processed[idx]:
                text_to_translation_map[original_text] = all_translated_blocks_processed[idx]
            else:
                text_to_translation_map[original_text] = original_text # Fallback al original


    # Construir el nuevo archivo de subtítulos
    # No se modifica la lista original de eventos `subs.events` directamente durante la iteración
    # sino que se actualiza el atributo `text` de cada evento.
    for ev in subs:
        original_text_cleaned = ev.plaintext.strip()
        if original_text_cleaned in text_to_translation_map:
            translation = text_to_translation_map[original_text_cleaned]
            if translation: # Debería ser siempre el caso con el fallback
                ev.text = translation
            # Si no hay traducción (o es el original por fallback), ev.text ya tiene el original
        # Los textos como "♪ ♪" o vacíos se mantienen sin cambios (no estaban en text_to_translation_map)

    # Filtrar eventos que hayan quedado completamente vacíos DESPUÉS de la traducción (si es que alguno resulta así)
    # subs.events = [ev for ev in subs if ev.text.strip()] # Esto puede ser muy agresivo si algunas traducciones son intencionalmente cortas.
                                                       # Podría ser mejor no filtrar o hacerlo con más cuidado.
                                                       # Por ahora, lo comentaré para asegurar que no se pierdan líneas si la traducción es solo "..." por ejemplo.

    subs.save(output_srt_path, encoding='utf-8', format_='srt')
    print(f"Subtítulos traducidos guardados en: {output_srt_path}")


def verificar_ffmpeg():
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg no está instalado o no se encuentra en el PATH del sistema.")
        print("Por favor, instala ffmpeg y asegúrate de que esté en el PATH.")
        print("Puedes descargarlo desde: https://ffmpeg.org/download.html")
        return False
    return True

def listar_archivos(directorio, extensiones):
    try:
        archivos = [f for f in os.listdir(directorio) if os.path.isfile(os.path.join(directorio, f)) and f.lower().endswith(extensiones)]
        return archivos
    except FileNotFoundError:
        print(f"Error: El directorio '{directorio}' no fue encontrado.")
        return []


def extraer_srt(video_path, srt_out_path):
    if not verificar_ffmpeg(): # verificar_ffmpeg ya imprime mensajes
        return False
        
    # Comando para extraer la primera pista de subtítulos encontrada (puede necesitar ajuste)
    # -map 0:s:0? intenta seleccionar la primera pista de subtítulos si existe, sin fallar si no hay.
    # Pero es más robusto verificar el resultado.
    comando = [
        "ffmpeg", "-y", # Sobrescribir archivo de salida si existe
        "-i", video_path,
        "-map", "0:s:0", # Extraer la primera pista de subtítulos (stream 0, subtitle track 0)
        srt_out_path
    ]
    print(f"Intentando extraer subtítulos con: {' '.join(comando)}")
    try:
        proceso = subprocess.run(comando, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore')
        if proceso.returncode != 0:
            print(f"Error ejecutando ffmpeg (código {proceso.returncode}):")
            print("Stderr:", proceso.stderr.strip() if proceso.stderr else "N/A")
            # print("Stdout:", proceso.stdout.strip() if proceso.stdout else "N/A") # ffmpeg a menudo usa stderr para info
            if "Subtitle stream not found" in proceso.stderr or not os.path.exists(srt_out_path) or os.path.getsize(srt_out_path) == 0 :
                 print("No se encontraron subtítulos incrustados o no se pudieron extraer.")
                 if os.path.exists(srt_out_path): os.remove(srt_out_path) # Limpiar archivo vacío
                 return False
            return True # Puede que ffmpeg haya tenido warnings pero aun así extrajo.
        
        if not os.path.exists(srt_out_path) or os.path.getsize(srt_out_path) == 0:
            print("ffmpeg se ejecutó, pero el archivo SRT no se creó o está vacío.")
            if os.path.exists(srt_out_path): os.remove(srt_out_path) # Limpiar archivo vacío
            return False
            
        print(f"Subtítulos extraídos a: {srt_out_path}")
        return True

    except FileNotFoundError:
        print("Error: ffmpeg no encontrado. Asegúrate de que está instalado y en el PATH.")
        return False
    except Exception as e:
        print(f"Excepción inesperada durante la extracción de subtítulos: {e}")
        return False

def generar_nombre_salida(filepath_entrada, sufijo_idioma="es", ext=".srt"):
    if not filepath_entrada:
        return None
    directorio, nombre_completo = os.path.split(filepath_entrada)
    nombre_base, _ = os.path.splitext(nombre_completo)
    # Si el archivo original ya tiene un sufijo como "_original" o "_en", quitarlo primero.
    # Esto es opcional y depende de cómo quieras nombrar los archivos.
    # Ejemplo: nombre_base = nombre_base.replace("_original", "").replace("_en", "")
    nombre_salida = f"{nombre_base}_{sufijo_idioma.lower()}{ext}"
    return os.path.join(directorio, nombre_salida) # os.path.join maneja / y \


async def async_main():
    api_key_to_use = os.environ.get("GEMINI_API_KEY")
    if not api_key_to_use:
        print("ADVERTENCIA: La variable de entorno GEMINI_API_KEY no está configurada.")
        print(f"Usando la API key hardcodeada: ...{USER_GEMINI_API_KEY[-4:]} (ESTO NO ES SEGURO PARA PRODUCCIÓN)")
        api_key_to_use = USER_GEMINI_API_KEY
        if not api_key_to_use: # Doble check por si USER_GEMINI_API_KEY está vacía
            print("ERROR: No se proporcionó una API key de Gemini. Configura GEMINI_API_KEY o edita el script.")
            return

    print("=== Traductor de Subtítulos Gemini (Consola) ===")
    directorio_trabajo = os.getcwd()
    
    archivos_video = listar_archivos(directorio_trabajo, (".mkv", ".mp4", ".avi", ".mov"))
    archivos_srt_existentes = listar_archivos(directorio_trabajo, (".srt",))

    opciones_disponibles = []
    print("\nArchivos disponibles en el directorio actual:")
    idx_opcion = 1
    for f_video in archivos_video:
        print(f"{idx_opcion}. [VIDEO] {f_video}")
        opciones_disponibles.append({"path": os.path.join(directorio_trabajo, f_video), "tipo": "video"})
        idx_opcion += 1
    for f_srt in archivos_srt_existentes:
        print(f"{idx_opcion}. [SRT]   {f_srt}")
        opciones_disponibles.append({"path": os.path.join(directorio_trabajo, f_srt), "tipo": "srt"})
        idx_opcion += 1
    
    if not opciones_disponibles:
        print("No se encontraron archivos de video o SRT compatibles en el directorio actual.")
        return

    seleccion_valida = False
    seleccion_info = None
    while not seleccion_valida:
        try:
            num_input = input("Selecciona el número del archivo a traducir: ")
            idx_seleccionado = int(num_input) - 1
            if 0 <= idx_seleccionado < len(opciones_disponibles):
                seleccion_info = opciones_disponibles[idx_seleccionado]
                seleccion_valida = True
            else:
                print("Selección fuera de rango.")
        except ValueError:
            print("Entrada inválida. Por favor, ingresa un número.")

    archivo_entrada_principal_path = seleccion_info["path"]
    tipo_archivo_principal = seleccion_info["tipo"]
    srt_a_traducir_path = None

    if tipo_archivo_principal == "video":
        nombre_base_video, _ = os.path.splitext(os.path.basename(archivo_entrada_principal_path))
        # srt_extraido_sugerido_path = os.path.join(directorio_trabajo, f"{nombre_base_video}_extracted.srt")
        # Usar _original para que sea más claro que es el srt fuente
        srt_extraido_sugerido_path = generar_nombre_salida(archivo_entrada_principal_path, sufijo_idioma="original", ext=".srt")


        if extraer_srt(archivo_entrada_principal_path, srt_extraido_sugerido_path):
            srt_a_traducir_path = srt_extraido_sugerido_path
        else:
            print(f"No se pudieron extraer subtítulos de '{archivo_entrada_principal_path}'.")
            # Opcional: buscar un .srt con el mismo nombre que el video
            srt_externo_path = os.path.splitext(archivo_entrada_principal_path)[0] + ".srt"
            if os.path.exists(srt_externo_path):
                usar_externo = input(f"Se encontró un archivo SRT externo: '{os.path.basename(srt_externo_path)}'. ¿Usarlo? (s/N): ").strip().lower()
                if usar_externo == 's':
                    srt_a_traducir_path = srt_externo_path
                else:
                    print("Operación cancelada.")
                    return
            else:
                print("No se encontró un archivo SRT externo con el mismo nombre.")
                return
    else: # tipo_archivo_principal == "srt"
        srt_a_traducir_path = archivo_entrada_principal_path

    if not srt_a_traducir_path or not os.path.exists(srt_a_traducir_path):
        print("Error: No se pudo determinar o encontrar el archivo SRT de origen para la traducción.")
        return

    idioma_origen = input(f"Idioma de origen del archivo '{os.path.basename(srt_a_traducir_path)}' (ej: EN, FR) [EN]: ").strip().upper() or "EN"
    idioma_destino = input("Idioma destino para la traducción (ej: ES, FR) [ES]: ").strip().upper() or "ES"

    srt_traducido_path = generar_nombre_salida(srt_a_traducir_path, sufijo_idioma=idioma_destino)

    try:
        translator_instance = GeminiTranslator(api_key=api_key_to_use)
    except ValueError as e: # Error de API key no proporcionada
        print(f"Error al inicializar el traductor: {e}")
        return
    except Exception as e: # Otros errores de configuración de genai
        print(f"Error crítico al configurar Gemini (verifica tu API key y la librería 'google-generativeai'): {e}")
        return

    print(f"\nTraduciendo: {os.path.basename(srt_a_traducir_path)} ({idioma_origen})")
    print(f"      ↳ A: {os.path.basename(srt_traducido_path)} ({idioma_destino})")
    
    await translate_srt(srt_a_traducir_path, srt_traducido_path, translator_instance, 
                        source_lang=idioma_origen, target_lang=idioma_destino, batch_size=20) # Ajusta batch_size si es necesario

if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario.")
    except Exception as e:
        print(f"\nOcurrió un error inesperado en el flujo principal: {e}")
        import traceback
        traceback.print_exc()
