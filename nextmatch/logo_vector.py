"""NEXT MATCH – Logo A (NM») in maximaler Auflösung: Vektor (SVG/PDF) + hochaufgelöste PNGs.

Die Buchstaben kommen als echte Konturen aus Archivo Expanded Black (fontTools), N und M werden zu einer Fläche
vereinigt (skia-pathops), dann kursiv geschert – identische Geometrie wie logo.py, nur verlustfrei skalierbar.
Aufruf: python3 logo_vector.py  -> out/max/*
"""
import os

import cairosvg
import pathops
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

import logo as L

OUT = os.path.join(L.OUT, "max")
FONT = os.path.join(L.FONTS, "ArchivoX900.ttf")


def hexcol(c):
    return "#%02X%02X%02X" % c


def build_paths():
    """-> (weiß, lime, (x0, y0, x1, y1)) als pathops-Pfade in SVG-Koordinaten (y nach unten)."""
    tt = TTFont(FONT)
    gs = tt.getGlyphSet()
    cmap = tt.getBestCmap()
    gn, gm = gs[cmap[ord("N")]], gs[cmap[ord("M")]]
    from fontTools.pens.boundsPen import BoundsPen
    bounds = {}
    for k, g in (("N", gn), ("M", gm)):
        bp = BoundsPen(gs)
        g.draw(bp)
        bounds[k] = bp.bounds
    # Stammpositionen wie in logo.py aus dem Raster messen, als Anteil der Tintenbreite
    rn = L.text_img("N", "ArchivoX900.ttf", 2000, L.WHITE)
    rm = L.text_img("M", "ArchivoX900.ttf", 2000, L.WHITE)
    n_stem = L.stem_runs(rn)[-1]
    m_stem = L.stem_runs(rm)[0]
    nx0, ny0, nx1, ny1 = bounds["N"]
    mx0, my0, mx1, my1 = bounds["M"]
    wn = nx1 - nx0
    stem = (n_stem[1] - n_stem[0]) / rn.width * wn
    n_stem_x = nx0 + n_stem[0] / rn.width * wn
    m_stem_x = mx0 + m_stem[0] / rm.width * (mx1 - mx0)
    dx_m = n_stem_x - m_stem_x                     # M so verschieben, dass sein linker Stamm auf dem rechten N-Stamm liegt
    base, cap = min(ny0, my0), max(ny1, my1)
    h = cap - base
    k = L.SHEAR

    def mat(dx):
        # Font (y nach oben) -> SVG (y nach unten), dabei kursiv: x' = x + k*(y - base)
        return (1, 0, k, -1, dx - nx0 - k * base, cap)

    white = pathops.Path()
    gn.draw(TransformPen(white.getPen(), mat(0)))
    gm.draw(TransformPen(white.getPen(), mat(dx_m)))
    white.simplify(fix_winding=True)

    lime = pathops.Path()
    w, dep, gap = stem * 0.82, h * 0.40, stem * 0.42
    x_ch = dx_m + mx1 + stem * 0.55
    pen = TransformPen(lime.getPen(), mat(0))
    for i in range(2):
        x0 = x_ch + i * (w + gap)
        pts = [(x0, cap), (x0 + w, cap), (x0 + w + dep, base + h / 2), (x0 + w, base), (x0, base), (x0 + dep, base + h / 2)]
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    lime.simplify(fix_winding=True)
    b = pathops.op(white, lime, pathops.PathOp.UNION).bounds
    return white, lime, b


def d_attr(path):
    sp = SVGPathPen(None, ntos=lambda v: ("%.2f" % v).rstrip("0").rstrip("."))
    path.draw(sp)
    return sp.getCommands()


def symbol_svg(white, lime, b, col_w, col_l, pad=0.0):
    x0, y0, x1, y1 = b
    p = (y1 - y0) * pad
    vb = f"{x0 - p:.1f} {y0 - p:.1f} {x1 - x0 + 2 * p:.1f} {y1 - y0 + 2 * p:.1f}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">\n'
            f'  <title>NEXT MATCH</title>\n'
            f'  <path fill="{hexcol(col_w)}" d="{d_attr(white)}"/>\n'
            f'  <path fill="{hexcol(col_l)}" d="{d_attr(lime)}"/>\n'
            f'</svg>\n')


def profile_svg(white, lime, b):
    """Profilbild als Vektor: Hintergrund mit Lichtflecken, Speedlines, Glow und Symbol (für Browser/Illustrator/Figma)."""
    x0, y0, x1, y1 = b
    S = 1080
    s = min(820 / (x1 - x0), 440 / (y1 - y0))
    tx = S / 2 - (x0 + x1) / 2 * s
    ty = S / 2 - (y0 + y1) / 2 * s
    bg, lm = hexcol(L.BG), hexcol(L.LIME)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}">
  <title>NEXT MATCH – Profilbild</title>
  <defs>
    <radialGradient id="spot" cx="0.72" cy="0.25" r="0.55">
      <stop offset="0" stop-color="{lm}" stop-opacity="0.07"/><stop offset="1" stop-color="{lm}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="blue" cx="0.2" cy="0.9" r="0.55">
      <stop offset="0" stop-color="#3340A0" stop-opacity="0.12"/><stop offset="1" stop-color="#3340A0" stop-opacity="0"/>
    </radialGradient>
    <pattern id="speed" width="28.4" height="{S}" patternUnits="userSpaceOnUse" patternTransform="rotate(24.2)">
      <rect width="1.2" height="{S}" fill="#FFFFFF" fill-opacity="0.025"/>
    </pattern>
    <filter id="glow" x="-30%" y="-60%" width="160%" height="220%"><feGaussianBlur stdDeviation="{20 / s:.1f}"/></filter>
  </defs>
  <rect width="{S}" height="{S}" fill="{bg}"/>
  <rect width="{S}" height="{S}" fill="url(#spot)"/>
  <rect width="{S}" height="{S}" fill="url(#blue)"/>
  <rect width="{S}" height="{S}" fill="url(#speed)"/>
  <g transform="translate({tx:.2f} {ty:.2f}) scale({s:.5f})">
    <g filter="url(#glow)" fill="{lm}" opacity="0.4"><path d="{d_attr(white)}"/><path d="{d_attr(lime)}"/></g>
    <path fill="{hexcol(L.WHITE)}" d="{d_attr(white)}"/>
    <path fill="{lm}" d="{d_attr(lime)}"/>
  </g>
</svg>
'''


def render_png(svg, width):
    import io
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=width))).convert("RGBA")


def profile_png(svg_sym, n):
    """Profilbild als PNG in n×n – Hintergrund/Glow wie logo.py, Symbol scharf aus dem Vektor."""
    s = n / 1080
    img = L.bg_square(n)
    sym = render_png(svg_sym, int(820 * s))
    sym = L.fit(sym, 820 * s, 440 * s)
    g = L.glow(L.pad(sym, int(80 * s)), L.LIME, 40 * s, 0.35)
    L.center(img, g, n / 2, n / 2)
    L.center(img, sym, n / 2, n / 2)
    return img.convert("RGB")


def main():
    os.makedirs(OUT, exist_ok=True)
    white, lime, b = build_paths()
    files = {
        "NM_symbol_dunkel.svg": symbol_svg(white, lime, b, L.WHITE, L.LIME),
        "NM_symbol_hell.svg": symbol_svg(white, lime, b, L.BG, L.LIME_INK),
        "NM_symbol_weiss.svg": symbol_svg(white, lime, b, L.WHITE, L.WHITE),
        "NM_symbol_schwarz.svg": symbol_svg(white, lime, b, L.BG, L.BG),
        "NM_profilbild.svg": profile_svg(white, lime, b),
    }
    for name, svg in files.items():
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)
        if name.startswith("NM_symbol"):
            stem = name[:-4]
            cairosvg.svg2pdf(bytestring=svg.encode(), write_to=os.path.join(OUT, stem + ".pdf"))
            render_png(svg, 8000).save(os.path.join(OUT, stem + "_8000px.png"), optimize=True)
    profile_png(files["NM_symbol_dunkel.svg"], 4096).save(os.path.join(OUT, "NM_profilbild_4096px.png"), optimize=True)
    print("fertig")


if __name__ == "__main__":
    main()
