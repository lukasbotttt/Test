"""Instagram-Story für den Umfrage-Sticker zu Part 8 (1080x1920). Aufruf: python3 story_poll8.py"""
import os

import numpy as np
from PIL import Image, ImageDraw

import reel31_powerplay as M
import reel33_lines_neon as N
import story_part8 as S

HERE = os.path.dirname(os.path.abspath(__file__))
NAVY, ORANGE, WHITE = N.NAVY, N.ORANGE, N.WHITE
GREY = (200, 200, 214)


def main():
    img = S.background()
    M.draw(img, N.brand_img("bladesandpucks_lockup_transparent.png", 420), 540, 270, 0.95)
    N.chip(img, "QUICK POLL · PART 8", 540, 380, 1.0, 1.15)
    # Strafuhr: 1:56 -> 0:00
    old = M.text_spr("1:56", "m7", 100, (150, 150, 168))
    new = M.text_spr("0:00", "m7", 150, ORANGE)
    M.draw(img, old, 235, 560, 0.9)
    M.draw(img, new, 700, 560, 1.0, glow=0.9)
    d = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    dr = ImageDraw.Draw(d)
    dr.line((112, 560, 358, 560), fill=(255, 70, 80), width=7)          # alte Zeit durchgestrichen
    dr.polygon([(452, 542), (488, 560), (452, 578)], fill=ORANGE)        # Pfeil
    dr.line((392, 560, 456, 560), fill=ORANGE, width=7)
    img = np.asarray(d).astype(np.float32) / 255
    lab = M.text_spr("PENALTY BOX", "m7", 26, GREY)
    M.draw(img, lab, 540, 440)
    # Frage
    N.NLine([("POWER-PLAY", WHITE), ("GOAL", WHITE), ("=", ORANGE)], "x9", 74, 540, 760, [-5] * 3, None).render(img, 0)
    N.NLine([("PENALTY", WHITE), ("OVER.", ORANGE)], "x9", 74, 540, 850, [-5] * 2, None).render(img, 0)
    N.NLine([("Should players serve the", WHITE)], "in6", 50, 540, 965, [-5], None, track=0).render(img, 0)
    N.NLine([("FULL 2 minutes again?", ORANGE)], "in6", 50, 540, 1030, [-5], None, track=0).render(img, 0)
    # Platz für den Umfrage-Sticker (ca. y 1150-1450) + Hinweis
    N.NLine([("VOTE", ORANGE), ("BELOW", WHITE)], "x9", 44, 540, 1110, [-5] * 2, None).render(img, 0)
    N.NLine([("Until 1956 they did. Montreal's power play changed it.", GREY)], "in6", 32, 540, 1560, [-5], None,
            track=0, maxw=980).render(img, 0)
    N.NLine([("Full story in the new reel", WHITE)], "in6", 36, 540, 1620, [-5], None, track=0).render(img, 0)
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    out.save(os.path.join(HERE, "story_poll8.png"))
    out.convert("RGB").save(os.path.join(HERE, "story_poll8.jpg"), quality=95)
    print("fertig: story_poll8.png")


if __name__ == "__main__":
    main()
