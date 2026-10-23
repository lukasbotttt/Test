"""Löwen-Frankfurt-Heimtrikot 2026/27 (Produktbild) ohne Sponsoren: Logos per Inpainting entfernen, Halsinnenseite dunkel.

Quelle: kit/loewen_home_front_src.png (Produktbild aus dem Fanshop). Ausgabe: kit/loewen_home_clean.png
Entfernt: techem (Ärmel), Hit Radio FFH (Kragen), PENNY DEL (Brust), VGF, CCM, Jersey53 – Vereinsdesign bleibt.
"""
import os

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "kit", "loewen_home_front_src.png")
DST = os.path.join(HERE, "kit", "loewen_home_clean.png")

# (x0, y0, x1, y1, Modus): "bright" = nur helle/rote Pixel maskieren, "full" = ganze Fläche
BOXES = [(145, 325, 298, 425, "bright"), (1298, 330, 1455, 445, "bright"),      # techem
         (630, 245, 730, 360, "full"), (860, 245, 965, 360, "full"),              # FFH
         (995, 260, 1255, 392, "full"),                                           # PENNY DEL
         (730, 432, 880, 495, "bright"),                                          # VGF
         (1200, 1290, 1262, 1340, "bright"), (340, 1285, 392, 1350, "bright")]   # CCM, Jersey53


def main():
    im = Image.open(SRC).convert("RGBA")
    rgba = np.asarray(im).copy()
    rgb = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2BGR)
    mask = np.zeros(rgb.shape[:2], np.uint8)
    lum = rgba[..., :3].astype(np.int32).mean(2)
    red = (rgba[..., 0].astype(np.int32) - rgba[..., 1]) > 60
    for x0, y0, x1, y1, mode in BOXES:
        if mode == "full":
            sub = rgba[y0:y1, x0:x1]
            orange = (sub[..., 0] > 200) & (sub[..., 1] > 70) & (sub[..., 1] < 150) & (sub[..., 2] < 80)
            mask[y0:y1, x0:x1][~orange] = 255                               # Kragen-Orange nicht anfassen
        else:
            sub = (lum[y0:y1, x0:x1] > 110) | red[y0:y1, x0:x1]
            mask[y0:y1, x0:x1][sub] = 255
    mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
    mask[rgba[..., 3] < 128] = 0
    out = cv2.inpaint(rgb, mask, 9, cv2.INPAINT_TELEA)
    for x0, y0, x1, y1, mode in BOXES:                                      # Kragenpatches: glatt schwarz
        if mode == "full" and y1 < 400 and x1 < 1000:
            sub = out[y0:y1, x0:x1]
            m = mask[y0:y1, x0:x1] > 0
            sub[m] = (33, 33, 35)
    out = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
    # Halsöffnung (hellgrau) = Innenseite des Rückens -> dunkel
    neck = (np.abs(out.astype(np.int32) - np.array([236, 238, 238])).sum(2) < 40)
    neck[:, :600] = False
    neck[:, 1000:] = False
    neck[300:] = False
    out[neck] = (34, 34, 36)
    res = np.dstack([out, rgba[..., 3]])
    Image.fromarray(res.astype(np.uint8), "RGBA").save(DST)
    print("fertig:", DST)


if __name__ == "__main__":
    main()
