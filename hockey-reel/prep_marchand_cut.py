"""Freisteller für Reel 11b: Brad Marchand (Lisa Gansky, CC BY-SA 2.0, Wikimedia Commons).

Aufruf: python3 prep_marchand_cut.py  ->  photos/marchand_cut.png  (benötigt: pip install rembg onnxruntime)
"""
import numpy as np
from PIL import Image
from rembg import new_session, remove
from scipy import ndimage

im = Image.open("photos/marchand.jpg").convert("RGB")
a = np.asarray(remove(im, session=new_session("isnet-general-use")))[:, :, 3].astype(np.float32)
mask = a > 60
lab, n = ndimage.label(mask)
keep = lab == (1 + int(np.argmax(ndimage.sum(mask, lab, range(1, n + 1)))))
closed = ndimage.binary_closing(keep, iterations=6)
# nur kleine Löcher füllen (Logo), große Lücken (Eis zwischen Arm und Trikot) bleiben offen
holes, nh = ndimage.label(ndimage.binary_fill_holes(closed) & ~closed)
small = np.isin(holes, 1 + np.flatnonzero(ndimage.sum(np.ones_like(holes), holes, range(1, nh + 1)) < 4000))
solid = closed | small
core = ndimage.binary_erosion(solid, iterations=4)
near = ndimage.binary_dilation(solid, iterations=6)
alpha = np.where(core, 255, np.where(near, a, 0)) * keep.astype(np.float32).clip(0, 1).__ge__(0)
out = Image.fromarray(np.dstack([np.asarray(im), alpha.astype(np.uint8)]), "RGBA")
out = out.crop(out.getbbox())
s = 1700 / out.height
out = out.resize((int(out.width * s), 1700), Image.LANCZOS)
arr = np.asarray(out).copy()
# fremder Schläger über der rechten Schulter
arr[230:372, 750:840, 3] = 0
Image.fromarray(arr, "RGBA").save("photos/marchand_cut.png", optimize=True)
print("fertig:", out.size)
