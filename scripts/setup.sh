#!/usr/bin/env bash
# Instala lo necesario para generar captions: paquetes de Python, fuentes y modelo de transcripción.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v ffmpeg >/dev/null || { echo "Falta ffmpeg (con libass): apt install ffmpeg  /  brew install ffmpeg"; exit 1; }
python3 -m pip install -q sherpa-onnx numpy

mkdir -p fonts models
GF=https://raw.githubusercontent.com/google/fonts/main/ofl
[ -f fonts/Anton-Regular.ttf ] || curl -sSfL -o fonts/Anton-Regular.ttf "$GF/anton/Anton-Regular.ttf"
[ -f fonts/Bangers-Regular.ttf ] || curl -sSfL -o fonts/Bangers-Regular.ttf "$GF/bangers/Bangers-Regular.ttf"
if [ ! -f fonts/InterDisplay-Black.ttf ]; then
  T=$(mktemp -d)
  curl -sSfL -o "$T/inter.zip" https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip
  python3 - "$T/inter.zip" <<'EOF'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
name = next(n for n in z.namelist() if n.endswith("/InterDisplay-Black.ttf"))
open("fonts/InterDisplay-Black.ttf", "wb").write(z.read(name))
EOF
  rm -rf "$T"
fi

M=sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8
if [ ! -d "models/$M" ]; then
  echo "Descargando el modelo de transcripción (puede tardar unos minutos)..."
  curl -sSfL "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$M.tar.bz2" | tar xj -C models
fi
echo "Listo. Prueba:  python3 scripts/make_captions.py VIDEO.mp4 -o salida --compare"
