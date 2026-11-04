# CAPTIONS-SKILL
Captions Skill

Genera captions animados palabra por palabra para videos (reels, TikTok, shorts) en 3 estilos:

| Estilo | Cómo se ve |
|---|---|
| `pop` | Mayúsculas gruesas (Anton), 3 palabras; la palabra que se dice se pone amarilla y más grande |
| `box` | Minúsculas (Inter Display Black), 4 palabras; la palabra que se dice va en un recuadro verde |
| `comic` | Una palabra a la vez (Bangers) con rebote, color e inclinación alternados |

## Instalación (una vez)

Necesitas Python 3.8+ y ffmpeg con libass.

```bash
bash scripts/setup.sh
```

Instala `sherpa-onnx`, descarga las fuentes a `fonts/` y el modelo de transcripción Parakeet v3
(español y otros idiomas europeos) a `models/`. Esas dos carpetas no se suben al repo.

## Uso

```bash
# 1. Transcribe y crea previews de los 3 estilos sobre fondo negro + comparativa lado a lado
python3 scripts/make_captions.py "mi video.mp4" -o salida --compare

# 2. Corrige palabras en salida/<nombre>_words.json y vuelve a correr el paso 1 (no transcribe otra vez)

# 3. Video final con el estilo elegido sobre el video original
python3 scripts/make_captions.py "mi video.mp4" -o salida --styles pop --bg video
```

Opciones: `--styles pop,box,comic`, `--bg black|video|none`, `--compare`, `--name`.
Pensado para videos cortos (hasta unos minutos).

Ejemplos con los videos de prueba en `prueba captions/previews/`.
