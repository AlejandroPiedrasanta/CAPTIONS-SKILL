#!/usr/bin/env python3
"""Captions animados para videos en 3 estilos: pop, box y comic.

  python3 scripts/make_captions.py VIDEO [-o CARPETA] [--name NOMBRE]
          [--styles pop,box,comic] [--bg black|video|none] [--compare]

1. Transcribe el audio con Parakeet v3 (español y otros idiomas europeos) y guarda
   NOMBRE_words.json con el tiempo de cada palabra. Si ese archivo ya existe no se vuelve
   a transcribir: edítalo para corregir palabras y corre el script otra vez.
2. Escribe un subtítulo .ass por estilo.
3. Renderiza: --bg black = preview sobre fondo negro (NOMBRE_ESTILO.mp4),
   --bg video = captions sobre el video original (NOMBRE_ESTILO_final.mp4), --bg none = solo .ass.
   --compare junta los estilos lado a lado (COMPARATIVA_NOMBRE.mp4).

Antes de usarlo por primera vez: bash scripts/setup.sh
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "models", "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8")
FONTS = os.path.join(ROOT, "fonts")

# Campos ASS: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold,
# Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment,
# MarginL, MarginR, MarginV, Encoding. Colores en &HAABBGGRR. El número es el máximo de palabras en pantalla.
STYLES = {
    "pop": ("Style: S,Anton,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,0,0,0,0,100,100,2,0,1,9,6,2,60,60,560,1", 3),
    "box": ("Style: S,Inter Display Black,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,2,70,70,560,1", 4),
    "comic": ("Style: S,Bangers,170,&H00FFFFFF,&H00FFFFFF,&H00000000,&HAA000000,0,0,0,0,100,100,4,0,1,11,8,5,40,40,0,1", 1),
}
POP_ON, POP_OFF = r"{\c&H00E5FF&\fscx112\fscy112}", r"{\c&HFFFFFF&\fscx100\fscy100}"  # palabra activa amarilla y más grande
BOX_ON, BOX_OFF = r"{\3c&H3FD94A&\bord22\c&HFFFFFF&}", r"{\3c&H000000&\bord6}"  # palabra activa en recuadro verde
COMIC_COLORS = ["&HFFFFFF&", "&H00E5FF&", "&HFFE14D&", "&HB469FF&"]  # blanco, amarillo, celeste, rosa

HDR = """[Script Info]
ScriptType: v4.00+
PlayResX: {resx}
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(x):
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def esc(path):
    """Ruta segura para usarla como opción dentro de un filtro de ffmpeg."""
    return "'" + path.replace("\\", "/").replace(":", "\\:") + "'"


def probe(path):
    j = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-of", "json", "-show_entries",
         "stream=width,height:stream_tags=rotate:stream_side_data=rotation:format=duration", path],
        capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]
    w, h = s["width"], s["height"]
    rot = int(s.get("tags", {}).get("rotate", 0))
    for sd in s.get("side_data_list", []):
        rot = int(sd.get("rotation", rot))
    if abs(rot) % 180 == 90:  # video de celular con rotación en los metadatos
        w, h = h, w
    return w, h, float(j["format"]["duration"])


def transcribe(path):
    import numpy as np
    import sherpa_onnx as so
    if not os.path.isdir(MODEL):
        sys.exit("Falta el modelo de transcripción. Corre primero:  bash scripts/setup.sh")
    rec = so.OfflineRecognizer.from_transducer(
        encoder=f"{MODEL}/encoder.int8.onnx", decoder=f"{MODEL}/decoder.int8.onnx",
        joiner=f"{MODEL}/joiner.int8.onnx", tokens=f"{MODEL}/tokens.txt",
        model_type="nemo_transducer", num_threads=os.cpu_count() or 4)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    stream = rec.create_stream()
    stream.accept_waveform(16000, audio)
    rec.decode_stream(stream)
    words = []  # los tokens que empiezan con "▁" abren una palabra nueva
    for tok, t in zip(stream.result.tokens, stream.result.timestamps):
        if tok.startswith(("▁", " ")) or not words:
            words.append({"w": tok.lstrip("▁ "), "s": round(t, 3)})
        else:
            words[-1]["w"] += tok
    words = [w for w in words if w["w"]]
    dur = len(audio) / 16000
    for i, w in enumerate(words):
        nxt = words[i + 1]["s"] if i + 1 < len(words) else dur
        w["e"] = round(min(nxt, w["s"] + 0.15 * len(w["w"]) + 0.25), 3)
    return words


def save_words(path, words):
    """Una palabra por línea para que sea fácil corregirlas a mano."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(w, ensure_ascii=False) for w in words) + "\n]\n")


def groups(words, n):
    """Bloques de hasta n palabras; se corta en pausas largas y en signos de puntuación."""
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= n or w["s"] - cur[-1]["e"] > 0.6):
            out.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.,!?]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build(words, style, resx):
    sty, n = STYLES[style]
    gs, ev = groups(words, n), []
    for gi, g in enumerate(gs):
        gend = min(g[-1]["e"] + 0.35, gs[gi + 1][0]["s"]) if gi + 1 < len(gs) else g[-1]["e"] + 0.5
        for k, w in enumerate(g):
            s, e = w["s"], (g[k + 1]["s"] if k + 1 < len(g) else gend)
            if style == "pop":
                txt = " ".join((POP_ON if j == k else POP_OFF) + x["w"].upper() for j, x in enumerate(g))
            elif style == "box":
                txt = r"\h\h ".join((BOX_ON if j == k else BOX_OFF) + x["w"] for j, x in enumerate(g))
            else:  # comic: una palabra a la vez con rebote, color e inclinación alternados
                txt = (rf"{{\an5\pos({resx // 2},1050)\c{COMIC_COLORS[gi % 4]}\frz{3 if gi % 2 else -3}"
                       r"\fscx60\fscy60\t(0,90,\fscx118\fscy118)\t(90,170,\fscx100\fscy100)}"
                       + w["w"].upper().strip(".,"))
            ev.append(f"Dialogue: 0,{ts(s)},{ts(e)},S,,0,0,0,,{txt}")
    return HDR.format(resx=resx, style=sty) + "\n".join(ev) + "\n"


def render(video, ass, mp4, w, h, dur, bg, out):
    vf = f"ass={esc(os.path.basename(ass))}:fontsdir={esc(os.path.relpath(FONTS, out))}"
    if bg == "black":  # lienzo negro con la proporción del video y 1080 px en el lado corto
        W, H = (1080, round(1080 * h / w / 2) * 2) if w < h else (round(1080 * w / h / 2) * 2, 1080)
        src = ["-f", "lavfi", "-i", f"color=black:s={W}x{H}:r=30:d={dur}", "-i", video, "-map", "0:v", "-map", "1:a?"]
    else:
        src = ["-i", video, "-map", "0:v:0", "-map", "0:a?"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *src, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest",
                    os.path.basename(mp4)], check=True, cwd=out)


def compare(mp4s, styles, dst, out):
    font = os.path.join(FONTS, "Anton-Regular.ttf")
    font = f"fontfile={esc(os.path.relpath(font, out))}:" if os.path.exists(font) else ""
    n = len(mp4s)
    fc = "".join(f"[{i}:v]scale=trunc(iw/4)*2:trunc(ih/4)*2,drawtext={font}text='{i + 1} {st.upper()}'"
                 f":fontcolor=gray:fontsize=30:x=20:y=20[v{i}];" for i, st in enumerate(styles))
    fc += "".join(f"[v{i}]" for i in range(n)) + f"hstack={n}"
    fc += "".join(f",drawbox=x=iw*{i}/{n}-1:y=0:w=2:h=ih:color=gray@0.4:t=fill" for i in range(1, n))
    ins = [arg for m in mp4s for arg in ("-i", os.path.basename(m))]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc + "[v]", "-map", "[v]",
                    "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "copy",
                    os.path.basename(dst)], check=True, cwd=out)


def main():
    ap = argparse.ArgumentParser(description="Captions animados (pop, box, comic) para un video.")
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="captions_out", help="carpeta de salida")
    ap.add_argument("--name", help="nombre base de los archivos (por defecto, el del video)")
    ap.add_argument("--styles", default="pop,box,comic", help="estilos separados por coma")
    ap.add_argument("--bg", choices=["black", "video", "none"], default="black",
                    help="black: fondo negro; video: sobre el video original; none: solo .ass")
    ap.add_argument("--compare", action="store_true", help="video con los estilos lado a lado")
    a = ap.parse_args()

    styles = [s.strip() for s in a.styles.split(",") if s.strip()]
    if bad := [s for s in styles if s not in STYLES]:
        sys.exit(f"Estilo desconocido: {', '.join(bad)}. Opciones: {', '.join(STYLES)}")
    video, out = os.path.abspath(a.video), os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    name = a.name or re.sub(r"[^\w-]", "_", os.path.splitext(os.path.basename(video))[0])
    w, h, dur = probe(video)

    wj = os.path.join(out, f"{name}_words.json")
    if os.path.exists(wj):
        with open(wj, encoding="utf-8") as f:
            words = json.load(f)
        print(f"Usando {wj} (bórralo para transcribir de nuevo)")
    else:
        words = transcribe(video)
        save_words(wj, words)
        print("Transcripción:", " ".join(x["w"] for x in words))

    resx, suffix, mp4s = round(1920 * w / h), ("_final" if a.bg == "video" else ""), []
    for st in styles:
        ass = os.path.join(out, f"{name}_{st}.ass")
        with open(ass, "w", encoding="utf-8") as f:
            f.write(build(words, st, resx))
        if a.bg != "none":
            mp4s.append(os.path.join(out, f"{name}_{st}{suffix}.mp4"))
            render(video, ass, mp4s[-1], w, h, dur, a.bg, out)
            print("Listo:", mp4s[-1])
    if a.compare and len(mp4s) > 1:
        dst = os.path.join(out, f"COMPARATIVA_{name}{suffix}.mp4")
        compare(mp4s, styles, dst, out)
        print("Listo:", dst)


if __name__ == "__main__":
    main()
