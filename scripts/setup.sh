#!/usr/bin/env bash
# Instala lo necesario para generar captions: paquetes de Python, fuentes y modelo de transcripción.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v ffmpeg >/dev/null || { echo "Falta ffmpeg (con libass): apt install ffmpeg  /  brew install ffmpeg"; exit 1; }
python3 -m pip install -q sherpa-onnx numpy fonttools

mkdir -p fonts models
G=https://raw.githubusercontent.com/google/fonts/main
while read -r f url; do
  [ -f "fonts/$f" ] && continue
  curl -sSfL -o "fonts/$f.part" "$url" && mv "fonts/$f.part" "fonts/$f" || { rm -f "fonts/$f.part"; echo "No se pudo descargar $f"; }
done <<EOF
Anton-Regular.ttf $G/ofl/anton/Anton-Regular.ttf
Bangers-Regular.ttf $G/ofl/bangers/Bangers-Regular.ttf
Montserrat-Black.ttf https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-Black.ttf
LuckiestGuy-Regular.ttf $G/apache/luckiestguy/LuckiestGuy-Regular.ttf
Poppins-Black.ttf $G/ofl/poppins/Poppins-Black.ttf
Righteous-Regular.ttf $G/ofl/righteous/Righteous-Regular.ttf
Pacifico-Regular.ttf $G/ofl/pacifico/Pacifico-Regular.ttf
CourierPrime-Bold.ttf $G/ofl/courierprime/CourierPrime-Bold.ttf
PressStart2P-Regular.ttf $G/ofl/pressstart2p/PressStart2P-Regular.ttf
RubikGlitch-Regular.ttf $G/ofl/rubikglitch/RubikGlitch-Regular.ttf
PermanentMarker-Regular.ttf $G/apache/permanentmarker/PermanentMarker-Regular.ttf
Lato-Bold.ttf $G/ofl/lato/Lato-Bold.ttf
InstrumentSerif-Italic.ttf $G/ofl/instrumentserif/InstrumentSerif-Italic.ttf
Shrikhand-Regular.ttf $G/ofl/shrikhand/Shrikhand-Regular.ttf
ArchivoBlack-Regular.ttf $G/ofl/archivoblack/ArchivoBlack-Regular.ttf
BebasNeue-Regular.ttf $G/ofl/bebasneue/BebasNeue-Regular.ttf
DMSerifDisplay-Italic.ttf $G/ofl/dmserifdisplay/DMSerifDisplay-Italic.ttf
TitanOne-Regular.ttf $G/ofl/titanone/TitanOne-Regular.ttf
LilitaOne-Regular.ttf $G/ofl/lilitaone/LilitaOne-Regular.ttf
DelaGothicOne-Regular.ttf $G/ofl/delagothicone/DelaGothicOne-Regular.ttf
Bungee-Regular.ttf $G/ofl/bungee/Bungee-Regular.ttf
BarlowCondensed-ExtraBoldItalic.ttf $G/ofl/barlowcondensed/BarlowCondensed-ExtraBoldItalic.ttf
PaytoneOne-Regular.ttf $G/ofl/paytoneone/PaytoneOne-Regular.ttf
Michroma-Regular.ttf $G/ofl/michroma/Michroma-Regular.ttf
SedgwickAveDisplay-Regular.ttf $G/ofl/sedgwickavedisplay/SedgwickAveDisplay-Regular.ttf
Kanit-ExtraBold.ttf $G/ofl/kanit/Kanit-ExtraBold.ttf
Silkscreen-Bold.ttf $G/ofl/silkscreen/Silkscreen-Bold.ttf
EOF
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
