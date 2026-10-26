"""Eisteufel-Frankfurt-Logos (PNG von der Vereinswebsite) als Vektor nachzeichnen -> SVG + PDF.

Vorgehen: 4x hochskalieren (Lanczos), auf die Logo-Farbpalette quantisieren (saubere Flächen statt Kantenrauschen),
mit vtracer in Splines umwandeln, Rot bekommt wieder den leichten Verlauf des Originals, PDF via cairosvg (vektoriell).
Achtung: Nachzeichnung, nicht die Original-Vektordatei des Vereins.

Aufruf: python3 vectorize.py original/eisteufel-icon.png original/et-logo-typo.png
"""
import os
import re
import sys
import tempfile

import cairosvg
import cv2
import numpy as np
import vtracer
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RED = (213, 79, 78)
# echte Logofarben (Hellgrau 217 und Dunkelgrau 133 im Original sind nur Kantenglättung -> nicht in die Palette)
PAL_ICON = [(32, 29, 30), (254, 254, 254), RED, (173, 178, 178)]
PAL_TYPO = PAL_ICON + [(51, 51, 51)]               # Schriftzug ist etwas heller als die Konturen


def quantize(src, palette, scale=4):
    im = Image.open(src).convert("RGBA")
    up = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    a = np.asarray(up).astype(np.float32)
    pal = np.array(palette, np.float32)
    d = ((a[..., None, :3] - pal[None, None]) ** 2).sum(-1)
    lab = d.argmin(-1)
    # Mehrheitsfilter: entfernt dünne Übergangssäume (z. B. Grau zwischen Schwarz und Weiß), echte Flächen bleiben
    votes = np.stack([cv2.boxFilter((lab == i).astype(np.float32), -1, (7, 7)) for i in range(len(pal))], -1)
    q = pal[votes.argmax(-1)].astype(np.uint8)
    alpha = np.where(a[..., 3] >= 128, 255, 0).astype(np.uint8)
    return Image.fromarray(np.dstack([q, alpha]), "RGBA")


def trace(src, palette, name, red_grad=True):
    q = quantize(src, palette)
    with tempfile.TemporaryDirectory() as td:
        tmp_png, tmp_svg = os.path.join(td, "q.png"), os.path.join(td, "o.svg")
        q.save(tmp_png)
        vtracer.convert_image_to_svg_py(tmp_png, tmp_svg, colormode="color", hierarchical="stacked", mode="spline",
                                        filter_speckle=10, color_precision=8, layer_difference=10,
                                        corner_threshold=60, length_threshold=4.0, max_iterations=10,
                                        splice_threshold=45, path_precision=2)
        svg = open(tmp_svg).read()
    w, h = q.size
    # feste Größe + viewBox, damit das PDF sauber skaliert
    head = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    if red_grad:
        head += (f'<defs><linearGradient id="red" x1="0" y1="0" x2="0" y2="{h}" gradientUnits="userSpaceOnUse">'
                 f'<stop offset="0.45" stop-color="#D24C4A"/><stop offset="1" stop-color="#D4616A"/></linearGradient></defs>')
    pal = np.array(palette, np.float32)

    def snap(m):
        # vtracer mittelt beim Zusammenfassen Farben -> zurück auf die Palette, Rot bekommt den Verlauf
        c = np.array([int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)], np.float32)
        p = tuple(int(v) for v in pal[((pal - c) ** 2).sum(-1).argmin()])
        if red_grad and p == RED:
            return 'fill="url(#red)"'
        return 'fill="#%02X%02X%02X"' % p

    svg = re.sub(r'fill="#([0-9A-Fa-f]{6})"', snap, svg)
    svg = re.sub(r'<svg[^>]*>', head, svg, 1)
    svg_path = os.path.join(HERE, name + ".svg")
    with open(svg_path, "w") as f:
        f.write(svg)
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=os.path.join(HERE, name + ".pdf"))
    cairosvg.svg2png(bytestring=svg.encode(), write_to=os.path.join(HERE, name + "_vorschau.png"), output_width=1600)
    return svg_path


if __name__ == "__main__":
    icon, typo = sys.argv[1], sys.argv[2]
    print(trace(icon, PAL_ICON, "Eisteufel_Logo"))
    print(trace(typo, PAL_TYPO, "Eisteufel_Logo_Schriftzug"))
