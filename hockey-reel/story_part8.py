"""Instagram-Story-Teaser (1080x1920) für Part 8 – Power Play. Aufruf: python3 story_part8.py"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import reel31_powerplay as M
import reel33_lines_neon as N

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
NAVY, ORANGE, WHITE = N.NAVY, N.ORANGE, N.WHITE
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "story_hook.png")


def background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.array(NAVY, np.float32) / 255
    g = 0.55 + 0.75 * np.exp(-(((xx - 540) / 700) ** 2 + ((yy - 980) / 760) ** 2))
    img = base[None, None, :] * g[..., None]
    img += np.array(ORANGE, np.float32)[None, None] / 255 * 0.10 * np.exp(-(((xx - 820) / 260) ** 2 + ((yy - 760) / 260) ** 2))[..., None]
    return img.astype(np.float32)


def panel(path):
    """Panel-Ausschnitt aus dem Video (16:9) mit runden Ecken, Rand und Schatten."""
    im = Image.open(path).convert("RGB").crop((0, 656, 1080, 1264)).resize((960, 540), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), 32, fill=255)
    card = Image.new("RGBA", im.size)
    card.paste(im, (0, 0), mask)
    ImageDraw.Draw(card).rounded_rectangle((1, 1, im.width - 2, im.height - 2), 32, outline=(255, 255, 255, 46),
                                           width=3)
    return card


def main():
    img = background()
    # Logo oben (unterhalb der Story-Kopfzeile)
    M.draw(img, N.brand_img("bladesandpucks_lockup_transparent.png", 420), 540, 270, 0.95)
    # "NEW · PART 8"-Chip
    N.chip(img, "NEW REEL · PART 8", 540, 380, 1.0, 1.15)
    # Headline
    for i, ln in enumerate([[("WHY", WHITE), ("CAN", WHITE)], [("THIS", ORANGE), ("TEAM", WHITE)],
                            [("ICE", WHITE), ("THE", WHITE), ("PUCK?", WHITE)]]):
        N.NLine(ln, "x9", 120, 540, 500 + i * 140, [-5] * len(ln), None).render(img, 0.0)
    # Video-Ausschnitt
    card = panel(SRC)
    sh = Image.new("RGBA", (card.width + 120, card.height + 120), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((60, 70, 60 + card.width, 70 + card.height), 32, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    M.draw(img, M.Spr(sh, sh.width / 2, sh.height / 2), 540, 1135)
    M.draw(img, M.Spr(card, card.width / 2, card.height / 2), 540, 1120)
    # Teaser-Zeile
    N.NLine([("Blame", WHITE), ("it", WHITE), ("on", WHITE), ("Montreal", ORANGE), ("👀", WHITE)][:4], "in6", 52, 540,
            1460, [-5] * 4, None, track=0).render(img, 0.0)
    N.NLine([("3 goals in 44 seconds · Nov 5, 1955", (200, 200, 214))], "in6", 34, 540, 1525, [-5], None,
            track=0).render(img, 0.0)
    # Platz für den Link-Sticker + Hinweis
    N.NLine([("TAP", ORANGE), ("TO", WHITE), ("WATCH", WHITE)], "x9", 46, 540, 1640, [-5] * 3, None).render(img, 0.0)
    d = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    dr = ImageDraw.Draw(d)
    for k in range(3):                                            # kleiner Pfeil nach unten zum Sticker
        y = 1690 + k * 18
        dr.line((520, y, 540, y + 14, 560, y), fill=ORANGE + (255,) if k == 2 else (255, 146, 60), width=5)
    d.save(os.path.join(HERE, "story_part8.png"))
    d.convert("RGB").save(os.path.join(HERE, "story_part8.jpg"), quality=95)
    print("fertig: story_part8.png")


if __name__ == "__main__":
    main()
