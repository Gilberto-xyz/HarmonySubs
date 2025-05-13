# Traducir Subtítulos con Gemini (Consola)

Este script permite extraer, traducir y guardar subtítulos de archivos de video o archivos `.srt` utilizando la API de Google Gemini (Google Generative AI). Está orientado especialmente a la traducción de subtítulos de canciones, manteniendo el tono poético y la emoción del texto original.

## Características principales

- **Extracción automática de subtítulos** de archivos de video (`.mkv`, `.mp4`, `.avi`, `.mov`) usando `ffmpeg`.
- **Traducción automática** de archivos `.srt` (subtítulos) mediante la API de Gemini, con manejo de lotes para eficiencia y control de errores.
- **Interfaz por consola** para seleccionar archivos y configurar idiomas de origen y destino.
- **Soporte para traducción de subtítulos de canciones**, preservando saltos de línea y formato.
- **Manejo de errores y advertencias** para problemas comunes (API, ffmpeg, archivos, etc.).

## Requisitos

- Python 3.8 o superior
- ffmpeg instalado y en el PATH del sistema ([descargar aquí](https://ffmpeg.org/download.html))
- Las siguientes librerías de Python:
  - `pysubs2`
  - `google-generativeai`

Puedes instalar las dependencias con:

```
pip install pysubs2 google-generativeai
```

## Configuración de la API Key

> **¡IMPORTANTE!** No incluyas tu API key de Gemini en el código en producción. Usa variables de entorno.

- Por defecto, el script busca la variable de entorno `GEMINI_API_KEY`.
- Si no está definida, usará la clave hardcodeada (no recomendado para producción).

Para definir la variable de entorno en Windows (PowerShell):

```
$env:GEMINI_API_KEY="TU_API_KEY"
```

## Uso

1. Coloca el script en el directorio donde tengas tus videos o archivos `.srt`.
2. Ejecuta el script:

```
python traducir_srt_song.py
```

3. Elige el archivo de video o subtítulo a traducir cuando se te solicite.
4. Si seleccionas un video, el script intentará extraer los subtítulos automáticamente.
5. Indica el idioma de origen y destino (por defecto: EN → ES).
6. El archivo traducido se guardará en el mismo directorio, con sufijo del idioma destino (ejemplo: `archivo_es.srt`).

## Detalles técnicos

- El script traduce en lotes de 20 bloques de texto únicos para optimizar el uso de la API.
- Preserva los saltos de línea y el formato de los subtítulos.
- Si la traducción falla para algún bloque, se mantiene el texto original.
- Soporta archivos de subtítulos incrustados y externos.

## Notas y recomendaciones

- El uso de la API de Gemini puede tener costos asociados según tu cuota.
- Si el archivo de video no tiene subtítulos incrustados, puedes usar un `.srt` externo.
- Para traducciones de otros idiomas, simplemente indícalo cuando se te pregunte.
- El script está pensado para uso personal y educativo. No compartas tu API key públicamente.

## Créditos

Desarrollado por [Gilberto Nava - Gemini 2.5 pro y o4-mini-high].

---

¿Dudas o problemas? Revisa los mensajes de error en consola o consulta la documentación de las librerías utilizadas.
