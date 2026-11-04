#!/usr/bin/env python3
"""20 estilos de captions virales, cada uno con su propia tipografía y animación.

  python3 scripts/viral_captions.py VIDEO [-o CARPETA] [--name NOMBRE] [--styles a,b,...]
          [--bg black|video|none] [--reel] [--grid]

Usa el mismo NOMBRE_words.json que make_captions.py (si no existe, transcribe el video) y
escribe NOMBRE_ESTILO.ass por estilo. Además:
  --bg black|video  renderiza cada estilo (fondo negro, o sobre el video original como _final.mp4)
  --reel            REEL_NOMBRE.mp4: pasa por los estilos uno tras otro, con su nombre y tipografía
  --grid            GRID_NOMBRE.mp4: mosaico con todos los estilos a la vez
"""
import argparse
import functools
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_captions import FONTS, HDR, esc, groups, load_words, probe, render, ts  # noqa: E402

LABEL_FONT = "Montserrat-Black.ttf"


def c(h):
    """'#RRGGBB' -> color para tags ASS (&HBBGGRR&)."""
    return f"&H{h[5:7]}{h[3:5]}{h[1:3]}&"


def sc(h, a=0):
    """'#RRGGBB' y alfa -> color para la línea Style (&HAABBGGRR)."""
    return f"&H{a:02X}{h[5:7]}{h[3:5]}{h[1:3]}"


def S(name, font, size, n, **kw):
    return dict(name=name, font=font, size=size, n=n, **kw)


# n = palabras por bloque. on = palabra que se está diciendo, past = las ya dichas, off = el resto.
# intro = animación al aparecer cada bloque; move = desde dónde entra; line = tags de toda la línea.
# layers = copias debajo del texto (extrusión 3D, brillo neón, glitch): d = desplazamiento,
# m = desplazamiento extra al entrar, h = tags de línea, p = tags por palabra.
# Comodines: %A color del bloque (acc), %J color de la palabra (pal), %F1/%F2 tipografías,
# %S/%T tamaños, %W ancho del lienzo, %Y altura del texto.
VIRAL = {
    "hormozi": S("Hormozi", "Montserrat-Black.ttf", 96, 3, case="upper", bord=7, shad=4,
                 acc=["#4ADE80", "#FACC15"],
                 on=r"\c%A\fscx100\fscy100\t(0,90,\fscx116\fscy116)", off=r"\c&HFFFFFF&\fscx100\fscy100"),
    "beast": S("Beast", "LuckiestGuy-Regular.ttf", 148, 2, case="upper", primary="#FFE600", bord=12, back_a=0,
               line=r"\xshad7\yshad11", on=r"\c&HFFFFFF&", off=rf"\c{c('#FFE600')}",
               intro=r"\frz-8\fscx40\fscy40\t(0,110,\frz3\fscx112\fscy112)\t(110,190,\frz0\fscx100\fscy100)"),
    "karaoke": S("Karaoke", "Poppins-Black.ttf", 96, 5, mode="karaoke", primary="#22D3EE", bord=5,
                 intro=r"\fad(120,0)"),
    "neon": S("Neón", "Righteous-Regular.ttf", 112, 3, font2="Pacifico-Regular.ttf", size2=144,
              primary="#FFE4F2", outline="#FF2D95", bord=3, line=r"\blur1.5",
              on=rf"\fn%F2\fs%T\c&HFFFFFF&\3c{c('#00F0FF')}", off=rf"\fn%F1\fs%S\c{c('#FFE4F2')}\3c{c('#FF2D95')}",
              intro=r"\alpha&HFF&\t(0,40,\alpha&H00&)\t(40,80,\alpha&HB0&)\t(80,140,\alpha&H00&)",
              layers=[dict(p=rf"\c{c('#B0186A')}\3c{c('#FF2D95')}\bord12\blur14")]),
    "typewriter": S("Máquina de escribir", "CourierPrime-Bold.ttf", 84, 6, mode="type", secondary_a=0xFF, bord=3),
    "arcade": S("Arcade", "PressStart2P-Regular.ttf", 60, 2, case="upper", primary="#39FF14", back="#FF00FF",
                back_a=0, bord=3, shad=6, spacing=4, on=r"\c&HFFFFFF&", off=rf"\c{c('#39FF14')}",
                intro=r"\fscy0\t(0,90,\fscy100)"),
    "glitch": S("Glitch", "RubikGlitch-Regular.ttf", 112, 2, case="upper", bord=0, mt=150,
                on=r"\c&HFFFFFF&\fscx108\fscy108", off=r"\c&HDDDDDD&\fscx100\fscy100",
                intro=r"\blur6\t(0,150,\blur0)",
                layers=[dict(d=(-7, 0), m=(-24, 0), p=rf"\c{c('#FF0040')}\alpha&H30&"),
                        dict(d=(7, 0), m=(24, 0), p=rf"\c{c('#00F0FF')}\alpha&H30&")]),
    "marker": S("Marcador", "PermanentMarker-Regular.ttf", 116, 4, bord=5, shad=3, line=r"\frz-3",
                on=rf"\c{c('#FFD60A')}\alpha&HFF&\t(0,120,\alpha&H00&)", past=r"\c&HFFFFFF&\alpha&H00&",
                off=r"\alpha&HFF&"),
    "editorial": S("Editorial", "Lato-Bold.ttf", 84, 4, case="lower", font2="InstrumentSerif-Italic.ttf",
                   size2=118, bord=2, shad=3, on=rf"\fn%F2\fs%T\c{c('#F5C26B')}", off=r"\fn%F1\fs%S\c&HFFFFFF&",
                   move=(0, 40), mt=180, intro=r"\fad(180,0)"),
    "retro": S("Retro 70s", "Shrikhand-Regular.ttf", 112, 2, primary="#FFF1D6", outline="#FF7A1A", bord=6,
               on=rf"\c{c('#FFC93C')}", off=rf"\c{c('#FFF1D6')}", move=(-90, 0), mt=160, intro=r"\fad(100,0)",
               layers=[dict(d=(9, 9), p=rf"\c{c('#7A2E0E')}\3c{c('#7A2E0E')}")]),
    "sticker": S("Sticker", "ArchivoBlack-Regular.ttf", 72, 4, primary="#111111", outline="#FFFFFF",
                 back="#FE2C55", back_a=0, border_style=3, bord=14, shad=7, line=r"\frz-2",
                 on=rf"\c{c('#FE2C55')}", off=rf"\c{c('#111111')}",
                 intro=r"\fscx70\fscy70\t(0,120,\fscx106\fscy106)\t(120,200,\fscx100\fscy100)"),
    "trailer": S("Tráiler", "BebasNeue-Regular.ttf", 128, 3, font2="DMSerifDisplay-Italic.ttf", size2=118,
                 bord=2, on=rf"\fn%F2\fs%T\fsp1\alpha&H00&\c{c('#E8C547')}",
                 off=r"\fn%F1\fs%S\fsp10\alpha&H90&\c&HFFFFFF&", intro=r"\fad(150,0)\blur6\t(0,300,\blur0)"),
    "pop3d": S("Pop 3D", "TitanOne-Regular.ttf", 112, 2, case="upper", outline="#7C3AED", bord=5,
               on=rf"\c{c('#FDE047')}", off=r"\c&HFFFFFF&",
               intro=r"\fscx0\fscy0\t(0,130,\fscx115\fscy115)\t(130,210,\fscx100\fscy100)",
               layers=[dict(d=(i * 2.5, i * 3), p=rf"\c{c('#4C1D95')}\3c{c('#4C1D95')}") for i in range(6, 0, -1)]),
    "twotone": S("Bicolor", "LilitaOne-Regular.ttf", 124, 2, case="upper", primary="#FFE066", bord=6, shad=4,
                 main_h=r"\clip(0,0,%W,%Y)", on=r"\fscx112\fscy112", off=r"\fscx100\fscy100",
                 move=(0, 60), mt=140, intro=r"\fad(80,0)",
                 layers=[dict(h=r"\clip(0,%Y,%W,1920)", p=rf"\c{c('#FF6B00')}")]),
    "hollow": S("Contorno a relleno", "DelaGothicOne-Regular.ttf", 92, 3, case="upper", outline="#FFFFFF", bord=3,
                on=rf"\1a&HFF&\c{c('#FF3B30')}\3c{c('#FF3B30')}\t(0,140,\1a&H00&)",
                past=r"\1a&H00&\c&HFFFFFF&\3c&HFFFFFF&", off=r"\1a&HFF&\3c&HFFFFFF&"),
    "rainbow": S("Arcoíris", "Bungee-Regular.ttf", 170, 3, case="upper", bord=6,
                 pal=["#22D3EE", "#A78BFA", "#F472B6", "#FBBF24", "#34D399"],
                 on=r"\c%J\3c&HFFFFFF&\bord9", off=r"\c%J\3c&H000000&\bord6",
                 move=(0, -90), mt=160, intro=r"\fad(60,0)"),
    "sport": S("Deportivo", "BarlowCondensed-ExtraBoldItalic.ttf", 136, 3, case="upper", bord=0, shad=6,
               back="#E11D48", back_a=0, on=rf"\c{c('#E11D48')}\4c&HFFFFFF&", off=rf"\c&HFFFFFF&\4c{c('#E11D48')}",
               move=(140, 0), mt=120, intro=r"\fad(40,0)"),
    "bubble": S("Burbuja", "PaytoneOne-Regular.ttf", 96, 3, case="lower", outline="#FF8FC7", bord=10, shad=6,
                back="#B794F4", back_a=0,
                on=rf"\3c{c('#7DD3FC')}\fscx100\fscy100\t(0,90,\fscx124\fscy124)\t(90,200,\fscx110\fscy110)",
                off=rf"\3c{c('#FF8FC7')}\fscx100\fscy100", move=(0, 40), mt=150, intro=r"\fad(100,0)"),
    "blurin": S("Minimal blur", "Michroma-Regular.ttf", 104, 3, case="upper", bord=0, shad=2, spacing=6,
                on=r"\alpha&HFF&\blur14\t(0,220,\alpha&H00&\blur0)", past=r"\alpha&H00&\blur0", off=r"\alpha&HFF&"),
    "graffiti": S("Graffiti", "SedgwickAveDisplay-Regular.ttf", 220, 2, primary="#A3E635", bord=8,
                  on=r"\c&HFFFFFF&", off=rf"\c{c('#A3E635')}",
                  intro=r"\frz-6\fscx130\fscy130\t(0,140,\frz0\fscx100\fscy100)",
                  layers=[dict(p=rf"\c{c('#D946EF')}\3c{c('#D946EF')}\bord16\blur10")]),
    "pill": S("Píldora", "Kanit-ExtraBold.ttf", 110, 3, case="upper", mode="pill", bord=5, shad=3,
              pills=[("#FF2E63", "#FFFFFF"), ("#FFD60A", "#111111"), ("#00C853", "#FFFFFF"),
                     ("#2F6BFF", "#FFFFFF"), ("#A64DFF", "#FFFFFF")]),
}

_FONTS = {}


def font(file):
    """(nombre completo, cmap, hmtx, alto de línea) de una fuente de fonts/."""
    if file not in _FONTS:
        from fontTools.ttLib import TTFont
        path = os.path.join(FONTS, file)
        if not os.path.exists(path):
            sys.exit(f"Falta la fuente {file}. Corre:  bash scripts/setup.sh")
        f = TTFont(path, lazy=True)
        _FONTS[file] = (f["name"].getDebugName(4), f.getBestCmap(), f["hmtx"],
                        f["OS/2"].usWinAscent + f["OS/2"].usWinDescent)
    return _FONTS[file]


def text_width(file, text, size, spacing=0):
    """Ancho aproximado en píxeles tal como lo dibuja libass."""
    _, cmap, hmtx, unit = font(file)
    adv = sum(hmtx[cmap[ord(ch)]][0] if ord(ch) in cmap else unit // 2 for ch in text)
    return adv * size / unit + spacing * len(text)


def style_line(v, sname):
    return (f"Style: {sname},{font(v['font'])[0]},{v['size']},{sc(v.get('primary', '#FFFFFF'))},"
            f"{sc(v.get('secondary', '#FFFFFF'), v.get('secondary_a', 0))},{sc(v.get('outline', '#000000'))},"
            f"{sc(v.get('back', '#000000'), v.get('back_a', 0x60))},0,0,0,0,100,100,{v.get('spacing', 0)},0,"
            f"{v.get('border_style', 1)},{v.get('bord', 6)},{v.get('shad', 0)},5,40,40,0,1")


def dialogue(layer, s, e, sname, txt):
    return f"Dialogue: {layer},{ts(s)},{ts(e)},{sname},,0,0,0,,{txt}"


def ass_doc(resx, styles, evs):
    return HDR.format(resx=resx, style="\n".join(styles)) + "\n".join(evs) + "\n"


def state(v, j, i):
    if j == i:
        return v["on"]
    return v.get("past", v["off"]) if j < i else v.get("future", v["off"])


def events(words, v, resx, y=1150):
    """Lista de (capa, inicio, fin, texto) de un estilo."""
    x, out, wi = resx // 2, [], 0
    case = {"upper": str.upper, "lower": str.lower}.get(v.get("case"), str)
    f1 = font(v["font"])[0]
    f2 = font(v["font2"])[0] if "font2" in v else f1

    def fill(t, gi, j, fs, fs2):
        t = (t.replace("%F1", f1).replace("%F2", f2).replace("%S", str(fs)).replace("%T", str(fs2))
              .replace("%W", str(resx)).replace("%Y", str(y)))
        if "acc" in v:
            t = t.replace("%A", c(v["acc"][gi % len(v["acc"])]))
        if "pal" in v:
            t = t.replace("%J", c(v["pal"][j % len(v["pal"])]))
        return t

    gs = groups(words, v["n"])
    for gi, g in enumerate(gs):
        gend = min(g[-1]["e"] + 0.35, gs[gi + 1][0]["s"]) if gi + 1 < len(gs) else g[-1]["e"] + 0.5
        # achica el bloque si alguna palabra no cabe a lo ancho
        widest = max(text_width(v["font"], case(w["w"]), v["size"], v.get("spacing", 0)) for w in g)
        k = min(1.0, (resx - 80) * 0.88 / (widest + 2 * v.get("bord", 6)))
        fs, fs2 = round(v["size"] * k), round(v.get("size2", v["size"]) * k)
        base = rf"\an5\fs{fs}" + v.get("line", "")
        mode = v.get("mode")
        if mode == "pill":
            out += pill_events(v, g, wi, case, x, y, resx, gend)
        elif mode in ("karaoke", "type"):
            head = "{" + fill(base + rf"\pos({x},{y})" + v.get("intro", ""), gi, 0, fs, fs2) + "}"
            if mode == "karaoke":  # el color barre cada palabra mientras se dice
                durs = [(g[i + 1]["s"] if i + 1 < len(g) else w["e"]) - w["s"] for i, w in enumerate(g)]
                body = " ".join(rf"{{\kf{round(d * 100)}}}" + case(w["w"]) for d, w in zip(durs, g))
            else:  # máquina de escribir: las letras aparecen una por una
                chars = []
                for i, w in enumerate(g):
                    txt = case(w["w"]) + (" " if i + 1 < len(g) else "")
                    nxt = g[i + 1]["s"] if i + 1 < len(g) else w["e"]
                    per = min(0.06, max(nxt - w["s"], 0.05) / len(txt))
                    chars += [(w["s"] - g[0]["s"] + n * per, ch) for n, ch in enumerate(txt)]
                cs = [round(t * 100) for t, _ in chars] + [round((gend - g[0]["s"]) * 100)]
                body = "".join(rf"{{\ko{max(0, cs[i + 1] - cs[i])}}}" + ch for i, (_, ch) in enumerate(chars))
            out.append((0, g[0]["s"], gend, head + body))
        else:
            layers = v.get("layers", []) + [dict(h=v.get("main_h", ""))]
            mx, my = v.get("move", (0, 0))
            for i, w in enumerate(g):
                s, e = w["s"], (g[i + 1]["s"] if i + 1 < len(g) else gend)
                for li, L in enumerate(layers):
                    (dx, dy), (lx, ly) = L.get("d", (0, 0)), L.get("m", (0, 0))
                    if i == 0 and (mx or my or lx or ly):
                        pos = rf"\move({x + dx + mx + lx},{y + dy + my + ly},{x + dx},{y + dy},0,{v.get('mt', 150)})"
                    else:
                        pos = rf"\pos({x + dx},{y + dy})"
                    tags = base + pos + (v.get("intro", "") if i == 0 else "") + L.get("h", "")
                    body = " ".join("{" + fill(state(v, j, i) + L.get("p", ""), gi, wi + j, fs, fs2) + "}"
                                    + case(wd["w"]) for j, wd in enumerate(g))
                    out.append((li, s, e, "{" + fill(tags, gi, 0, fs, fs2) + "}" + body))
        wi += len(g)
    return out


@functools.lru_cache(maxsize=None)
def vmetrics(file):
    """(ascendente, altura de mayúsculas) en unidades de la fuente, como las usa libass."""
    from fontTools.ttLib import TTFont
    os2 = TTFont(os.path.join(FONTS, file), lazy=True)["OS/2"]
    return os2.usWinAscent, getattr(os2, "sCapHeight", 0) or round(os2.usWinAscent * 0.7)


def pill_path(w, h):
    """Rectángulo de puntas redondas (píldora) como dibujo ASS."""
    w, r = max(w, h), h / 2
    k = r * 0.552

    def n(*p):
        return " ".join(f"{q:.0f}" for q in p)
    return (f"m {n(r, 0)} l {n(w - r, 0)} b {n(w - r + k, 0, w, r - k, w, r)} b {n(w, r + k, w - r + k, h, w - r, h)} "
            f"l {n(r, h)} b {n(r - k, h, 0, r + k, 0, r)} b {n(0, r - k, r - k, 0, r, 0)}")


def pill_events(v, g, wi, case, x, y, resx, gend):
    """Píldora de color debajo de la palabra que se dice; se desliza de palabra en palabra."""
    unit = font(v["font"])[3]
    words = [case(w["w"]) for w in g]
    space, w1 = text_width(v["font"], "  ", 1), [text_width(v["font"], t, 1) for t in words]
    fs = round(min(v["size"], (resx - 160) / (sum(w1) + space * (len(words) - 1))))  # el bloque cabe en una línea
    ws, sp = [t * fs for t in w1], space * fs
    cx, left = [], x - (sum(ws) + sp * (len(ws) - 1)) / 2
    for t in ws:
        cx.append(left + t / 2)
        left += t + sp
    asc, cap = (m * fs / unit for m in vmetrics(v["font"]))
    cy, ph, padx = y - fs / 2 + asc - cap / 2, cap * 1.7, cap * 0.4
    pills, out = v["pills"], []
    for i, w in enumerate(g):
        s, e = w["s"], (g[i + 1]["s"] if i + 1 < len(g) else gend)
        bg, fg = pills[(wi + i) % len(pills)]
        pw = ws[i] + 2 * padx
        if i == 0:  # aparece con un pequeño rebote
            anim = rf"\pos({cx[0]:.1f},{cy:.1f})\1c{c(bg)}\fscx40\fscy40\t(0,110,\fscx100\fscy100)"
        else:  # se desliza desde la palabra anterior cambiando de ancho y de color
            prev = pills[(wi + i - 1) % len(pills)][0]
            anim = (rf"\move({cx[i - 1]:.1f},{cy:.1f},{cx[i]:.1f},{cy:.1f},0,120)\1c{c(prev)}\t(0,120,\1c{c(bg)})"
                    rf"\fscx{(ws[i - 1] + 2 * padx) / pw * 100:.0f}\t(0,120,\fscx100)")
        out.append((0, s, e, r"{\an5\bord0\shad0\blur0.6" + anim + r"\p1}" + pill_path(pw, ph)))
        body = r" \h".join(("{" + rf"\bord0\shad0\c&HFFFFFF&\t(0,120,\c{c(fg)})" + "}" if j == i else
                         "{" + rf"\bord{v.get('bord', 6)}\shad{v.get('shad', 0)}\c&HFFFFFF&" + "}") + t
                        for j, t in enumerate(words))
        out.append((1, s, e, "{" + rf"\an5\pos({x},{y})\fs{fs}" + (r"\fad(80,0)" if i == 0 else "") + "}" + body))
    return out


def reel_doc(words, keys, resx, dur):
    """Un estilo por tramo; corta en inicios de frase para que cada estilo empiece con un bloque nuevo."""
    cuts = [words[i]["s"] for i in range(1, len(words)) if re.search(r"[.,!?]$", words[i - 1]["w"])]
    bounds, step = [0.0], dur / len(keys)
    min_len = min(2.0, step * 0.7)  # cada estilo se ve al menos 2 segundos
    for n in range(1, len(keys)):
        lo, hi = bounds[-1] + min_len, dur - (len(keys) - n) * min_len
        cand = [t for t in cuts if lo <= t <= hi]
        bounds.append(min(cand, key=lambda t: abs(t - n * step)) if cand else max(lo, min(n * step, hi)))
    bounds.append(dur)
    styles, evs = [label_style()], []
    for n, key in enumerate(keys):
        v, sn, b0, b1 = VIRAL[key], f"V{n}", bounds[n], bounds[n + 1]
        styles.append(style_line(v, sn))
        evs += [dialogue(la, s, min(e, b1), sn, t) for la, s, e, t in events(words, v, resx) if b0 <= s < b1]
        evs.append(dialogue(9, b0, b1, "L", label_text(key)))
    return ass_doc(resx, styles, evs)


def label_style():
    return (f"Style: L,{font(LABEL_FONT)[0]},50,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,2,0,1,0,0,8,40,40,140,1")


def label_text(key):
    """Número, nombre y tipografías del estilo, para las previews."""
    v = VIRAL[key]
    names = " + ".join(re.sub(r" Regular$", "", font(f)[0]) for f in (v["font"], v.get("font2")) if f)
    return f"{list(VIRAL).index(key) + 1:02d} · {v['name'].upper()}\\N{{\\fs32\\alpha&H60&}}{names}"


def grid(video, keys, name, out, dur, w, h, cols=4):
    pw = 270
    ph = round(pw * h / w / 2) * 2
    fdir = esc(os.path.relpath(FONTS, out))
    lab = esc(os.path.relpath(os.path.join(FONTS, LABEL_FONT), out))
    fc = [f"color=black:s={pw}x{ph}:r=30:d={dur},ass={esc(f'{name}_{k}.ass')}:fontsdir={fdir},"
          f"drawtext=fontfile={lab}:text='{n + 1} {VIRAL[k]['name'].upper()}':fontcolor=gray:fontsize=15:x=8:y=8,"
          f"drawbox=c=gray@0.3:t=1[p{n}]" for n, k in enumerate(keys)]
    layout = "|".join(f"{n % cols * pw}_{n // cols * ph}" for n in range(len(keys)))
    fc.append("".join(f"[p{n}]" for n in range(len(keys))) + f"xstack=inputs={len(keys)}:layout={layout}"
              + (":fill=black" if len(keys) % cols else "") + "[v]")
    dst = f"GRID_{name}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-filter_complex", ";".join(fc), "-map", "[v]",
                    "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", dst], check=True, cwd=out)
    return os.path.join(out, dst)


def main():
    ap = argparse.ArgumentParser(description="20 estilos de captions virales.")
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="captions_out", help="carpeta de salida")
    ap.add_argument("--name", help="nombre base de los archivos (por defecto, el del video)")
    ap.add_argument("--styles", default=",".join(VIRAL), help="estilos separados por coma")
    ap.add_argument("--bg", choices=["black", "video", "none"], default="none",
                    help="renderiza cada estilo: black = fondo negro, video = sobre el video original")
    ap.add_argument("--reel", action="store_true", help="un video que pasa por todos los estilos")
    ap.add_argument("--grid", action="store_true", help="mosaico con todos los estilos a la vez")
    ap.add_argument("--label", action="store_true", help="muestra arriba el nombre y la tipografía del estilo")
    a = ap.parse_args()

    keys = [s.strip() for s in a.styles.split(",") if s.strip()]
    if bad := [k for k in keys if k not in VIRAL]:
        sys.exit(f"Estilo desconocido: {', '.join(bad)}. Opciones: {', '.join(VIRAL)}")
    video, out = os.path.abspath(a.video), os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    name = a.name or re.sub(r"[^\w-]", "_", os.path.splitext(os.path.basename(video))[0])
    w, h, dur = probe(video)
    words = load_words(video, out, name)
    resx = round(1920 * w / h)

    for k in keys:
        ass = os.path.join(out, f"{name}_{k}.ass")
        styles = [style_line(VIRAL[k], "S")]
        evs = [dialogue(la, s, e, "S", t) for la, s, e, t in events(words, VIRAL[k], resx)]
        if a.label:
            styles.append(label_style())
            evs.append(dialogue(9, 0, dur, "L", label_text(k)))
        with open(ass, "w", encoding="utf-8") as f:
            f.write(ass_doc(resx, styles, evs))
        if a.bg != "none":
            mp4 = os.path.join(out, f"{name}_{k}{'_final' if a.bg == 'video' else ''}.mp4")
            render(video, ass, mp4, w, h, dur, a.bg, out)
            print("Listo:", mp4)
    if a.reel:
        ass, mp4 = os.path.join(out, f"REEL_{name}.ass"), os.path.join(out, f"REEL_{name}.mp4")
        with open(ass, "w", encoding="utf-8") as f:
            f.write(reel_doc(words, keys, resx, dur))
        render(video, ass, mp4, w, h, dur, "black", out)
        print("Listo:", mp4)
    if a.grid and len(keys) > 1:
        print("Listo:", grid(video, keys, name, out, dur, w, h))


if __name__ == "__main__":
    main()
