"""Freisteller für Reel 14 (Top 5 Forgotten Legends). Fotos: Wikimedia Commons, Lizenzen siehe reel14_legends.py.

Aufruf: python3 prep_reel14_cuts.py [name ...]  ->  photos/<name>_cut.png  (benötigt: pip install rembg onnxruntime)
"""
import sys

import numpy as np
from PIL import Image
from rembg import new_session, remove
from scipy import ndimage

NAMES = sys.argv[1:] or ["toews", "kane", "selanne_oly", "bedard"]
SESSION = new_session("isnet-general-use")

for name in NAMES:
    im = Image.open(f"photos/{name}.jpg").convert("RGB")
    a = np.asarray(remove(im, session=SESSION))[:, :, 3].astype(np.float32)
    mask = a > 60
    lab, n = ndimage.label(mask)
    keep = lab == (1 + int(np.argmax(ndimage.sum(mask, lab, range(1, n + 1)))))
    closed = ndimage.binary_closing(keep, iterations=6)
    holes, nh = ndimage.label(ndimage.binary_fill_holes(closed) & ~closed)
    small = np.isin(holes, 1 + np.flatnonzero(ndimage.sum(np.ones_like(holes), holes, range(1, nh + 1)) < 3000))
    solid = closed | small
    core = ndimage.binary_erosion(solid, iterations=3)
    near = ndimage.binary_dilation(solid, iterations=4)
    alpha = np.where(core, 255, np.where(near, a, 0))
    out = Image.fromarray(np.dstack([np.asarray(im), alpha.astype(np.uint8)]), "RGBA")
    out = out.crop(out.getbbox())
    out.save(f"photos/{name}_cut.png", optimize=True)
    print(name, out.size)
