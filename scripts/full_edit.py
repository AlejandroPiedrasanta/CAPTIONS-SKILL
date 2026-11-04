#!/usr/bin/env python3
"""Edición completa de un video vertical: color, zooms, captions, audio, efectos de sonido y cierre.

  python3 scripts/full_edit.py VIDEO -o SALIDA.mp4 [--style popsticker] [--words NOMBRE_words.json]
          [--cta "SÍGUEME|PARA MÁS"]

- Imagen: lo lleva a 1080x1920, sube un poco el contraste y la saturación, y enfoca.
- Zoom: empieza con un zoom que se abre y se acerca en cada palabra especial.
- Captions: el estilo de viral_captions.py (por defecto, captions normales + títulos pop).
- Audio: quita graves sobrantes, comprime, normaliza a -14 LUFS (redes) y suma un "whoosh"
  y un "pop" en cada palabra especial.
- Cierre: congela el último cuadro, lo oscurece y muestra el llamado a la acción (--cta "" lo quita).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import viral_captions as vc  # noqa: E402
from make_captions import FONTS, esc, load_words, probe  # noqa: E402

SR, TAIL = 44100, 1.8  # frecuencia del audio y segundos del cierre


def sfx_pop():
    t = np.arange(int(0.12 * SR)) / SR
    return 0.35 * np.sin(2 * np.pi * np.cumsum(1100 - 800 * t / 0.12) / SR) * np.exp(-35 * t)


def sfx_whoosh():
    n, k = int(0.45 * SR), int(0.3 * SR)
    b = np.cumsum(np.random.default_rng(1).standard_normal(n))
    b -= np.convolve(b, np.ones(300) / 300, "same")  # ruido filtrado: suena a aire
    y = b * np.concatenate([np.linspace(0, 1, k) ** 2, np.linspace(1, 0, n - k) ** 1.5])
    return 0.22 * y / np.abs(y).max()


def windows(words, v):
    """(inicio, fin) de cada título pop, con la misma regla que viral_captions.mix_events."""
    sp, out = vc.pick_specials(words, v.get("gap", 2.5)), []
    for i, grp in enumerate(sp):
        g = [words[j] for j in grp]
        end = max(g[-1]["e"] + 0.6, g[0]["s"] + 1.1)
        if i + 1 < len(sp):
            end = min(end, words[sp[i + 1][0]]["s"] - 0.05)
        out.append((g[0]["s"], end))
    return out


def main():
    ap = argparse.ArgumentParser(description="Edición completa de un video vertical.")
    ap.add_argument("video")
    ap.add_argument("-o", "--out", required=True, help="video final (.mp4)")
    ap.add_argument("--style", default="popsticker", help="estilo de viral_captions.py")
    ap.add_argument("--words", help="NOMBRE_words.json ya corregido (si no, transcribe el video)")
    ap.add_argument("--cta", default="SÍGUEME|PARA MÁS", help='texto del cierre; "|" separa bloques; "" lo quita')
    a = ap.parse_args()
    if a.style not in vc.VIRAL:
        sys.exit(f"Estilo desconocido: {a.style}. Opciones: {', '.join(vc.VIRAL)}")
    video, dst = os.path.abspath(a.video), os.path.abspath(a.out)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    w, h, dur = probe(video)
    fps = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                          "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip() or "30"
    v, resx = vc.VIRAL[a.style], 1080

    with tempfile.TemporaryDirectory() as work:
        if a.words:
            with open(a.words, encoding="utf-8") as f:
                words = json.load(f)
        else:
            words = load_words(video, os.path.dirname(dst), os.path.splitext(os.path.basename(dst))[0])
        wins = windows(words, v)

        # captions + cierre
        evs = [vc.dialogue(la, s, e, "S", t) for la, s, e, t in vc.events(words, v, resx)]
        parts = [p for p in a.cta.split("|") if p.strip()]
        if parts:
            cta = [{"w": p, "s": dur + 0.1 + 0.25 * i, "e": dur + 0.6 + 0.25 * i} for i, p in enumerate(parts)]
            evs += [vc.dialogue(la, s, e, "S", t)
                    for la, s, e, t in vc.pop_events(v, cta, 99, str.upper, resx // 2, 960, resx, dur + TAIL)]
        with open(os.path.join(work, "captions.ass"), "w", encoding="utf-8") as f:
            f.write(vc.ass_doc(resx, [vc.style_line(v, "S")], evs))

        # efectos de sonido: whoosh que llega a su punto justo cuando sale cada título, y un pop
        track, pop, whoosh = np.zeros(int((dur + TAIL) * SR)), sfx_pop(), sfx_whoosh()

        def put(clip, at):
            i = int(at * SR)
            if 0 <= i < len(track):
                track[i:i + len(clip)] += clip[:len(track) - i]
        for t0, _ in wins + ([(dur + 0.1, 0)] if parts else []):
            put(whoosh, t0 - 0.3)
            put(pop, t0)
        with wave.open(os.path.join(work, "sfx.wav"), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SR)
            f.writeframes((np.clip(track, -1, 1) * 32767).astype("<i2").tobytes())

        # zoom: se abre al empezar y se acerca un 12 % mientras se ve cada título pop
        z = "+".join(["0.15*clip(1-it/0.6,0,1)"] + [f"0.12*clip((it-{s:.2f})/0.15,0,1)*clip(({e:.2f}-it)/0.2,0,1)"
                                                    for s, e in wins])
        fc = (f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,"
              f"eq=contrast=1.06:saturation=1.12:brightness=0.005,scale=2160:3840:flags=lanczos,"
              f"zoompan=z='1+{z}':d=1:x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':s=1080x1920:fps={fps},"
              f"unsharp=5:5:0.45,tpad=stop_mode=clone:stop_duration={TAIL},"
              f"drawbox=c=black@0.45:t=fill:enable='gte(t,{dur:.2f})',"
              f"ass={esc('captions.ass')}:fontsdir={esc(os.path.relpath(FONTS, work))},format=yuv420p[v];"
              f"[0:a]highpass=f=60,acompressor=threshold=-18dB:ratio=2.5:attack=10:release=200,"
              f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample={SR},apad=pad_dur={TAIL}[voz];"
              f"[1:a]aresample={SR}[sfx];[voz][sfx]amix=inputs=2:duration=first:dropout_transition=0,"
              f"volume=2,alimiter=limit=0.95[a]")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", "sfx.wav", "-filter_complex", fc,
                        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst], check=True, cwd=work)
    print("Listo:", dst)


if __name__ == "__main__":
    main()
