"""Platzhalter-Bilder für die 4 Szenen (Hintergrund + freigestelltes Vordergrund-Objekt), bis die KI-Bilder da sind.

Gleiche Dateinamen/Größen wie die echten Bilder -> einfach überschreiben. Aufruf: python3 make_placeholders.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
W, H = 1080, 1920
FONT = os.path.join(HERE, "fonts", "JBMono700.ttf")

SCENES = {
    "s1": dict(c1=(10, 4, 30), c2=(255, 0, 110), c3=(0, 230, 255), label="S1 HACKER-RAUM"),
    "s2": dict(c1=(2, 6, 18), c2=(0, 120, 255), c3=(120, 0, 255), label="S2 REGEN / LANGEWEILE"),
    "s3": dict(c1=(14, 8, 2), c2=(255, 170, 0), c3=(255, 80, 0), label="S3 KI-ROBOTER"),
    "s4": dict(c1=(6, 2, 16), c2=(190, 0, 255), c3=(0, 255, 170), label="S4 SMARTPHONE"),
}


def bg(c1, c2, c3, label):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.ones((H, W, 3), np.float32) * np.array(c1, np.float32) / 255
    img += np.exp(-(((xx - 200) / 500) ** 2 + ((yy - 500) / 600) ** 2))[..., None] * np.array(c2) / 255 * 0.5
    img += np.exp(-(((xx - 900) / 500) ** 2 + ((yy - 1500) / 600) ** 2))[..., None] * np.array(c3) / 255 * 0.45
    grid = ((xx % 90 < 2) | (yy % 90 < 2)).astype(np.float32)[..., None] * 0.06
    img += grid
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 34)
    d.text((60, 1820), f"PLATZHALTER · {label} · HINTERGRUND", font=f, fill=(255, 255, 255))
    return im


def fg(key, c2, c3, label):
    im = Image.new("RGBA", (900, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = c2 + (255,)
    if key == "s1":                                   # Kapuzen-Silhouette
        d.ellipse((300, 120, 600, 470), fill=(12, 10, 20, 255), outline=col, width=8)
        d.polygon([(130, 1200), (250, 520), (650, 520), (770, 1200)], fill=(12, 10, 20, 255), outline=col)
    elif key == "s2":                                 # schmelzendes Handy
        d.rounded_rectangle((250, 150, 650, 900), 50, fill=(10, 14, 30, 255), outline=col, width=10)
        for x, ln in ((320, 220), (420, 300), (540, 180)):
            d.rounded_rectangle((x, 880, x + 40, 880 + ln), 20, fill=c3 + (255,))
    elif key == "s3":                                 # Roboterkopf
        d.rounded_rectangle((200, 200, 700, 750), 90, fill=(30, 20, 8, 255), outline=col, width=10)
        for x in (330, 570):
            d.ellipse((x - 50, 400, x + 50, 500), fill=c2 + (255,))
        d.rectangle((300, 750, 600, 1150), fill=(30, 20, 8, 255), outline=col, width=8)
    else:                                             # Hand + Handy
        d.rounded_rectangle((260, 100, 640, 860), 60, fill=(14, 8, 24, 255), outline=col, width=10)
        d.rounded_rectangle((180, 700, 720, 1200), 160, fill=(40, 26, 30, 255))
    glow = im.split()[3].filter(ImageFilter.GaussianBlur(18))
    halo = Image.new("RGBA", im.size, c3 + (0,))
    halo.putalpha(glow.point(lambda v: int(v * 0.5)))
    out = Image.alpha_composite(halo, im)
    ImageDraw.Draw(out).text((40, 20), f"PLATZHALTER · {label}\nVORDERGRUND (freigestellt)", font=ImageFont.truetype(FONT, 30),
                             fill=(255, 255, 255, 255))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for k, s in SCENES.items():
        bg(s["c1"], s["c2"], s["c3"], s["label"]).save(os.path.join(OUT, f"{k}_bg.jpg"), quality=90)
        fg(k, s["c2"], s["c3"], s["label"]).save(os.path.join(OUT, f"{k}_fg.png"))
    print("fertig")


if __name__ == "__main__":
    main()
