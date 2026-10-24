"""Freisteller für Reel 38 aus echten Fotos (Wikimedia Commons), Ausgabe in gear/:
- stick_white.png (Blatt mit weißem Tape + Schaft), puck.png: "Ice hockey stick and puck 20170120", Santeri Viinamäki, CC BY-SA 4.0
- stick_black.png: "Ice hockey stick and puck 20181220", Santeri Viinamäki, CC BY-SA 4.0
- glove.png: "Easton hockey gloves", Petey21, CC0 (Markenschrift per Inpainting entfernt)
- goal_clean.jpg: "Ice hockey goal 20180721", Santeri Viinamäki, CC BY-SA 4.0 (Herstellerschrift entfernt)
Aufruf: python3 gear_cut.py
"""
import os

import cv2
import numpy as np

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gear")


def grab(im, rect, scale=0.25, fg_fn=None):
    h, w = im.shape[:2]
    sm = cv2.resize(im, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    mask = np.zeros(sm.shape[:2], np.uint8)
    bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(sm, mask, tuple(int(v * scale) for v in rect), bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    if fg_fn is not None:
        mask[fg_fn(sm) & (mask != 0)] = 1
        cv2.grabCut(sm, mask, None, bgd, fgd, 3, cv2.GC_INIT_WITH_MASK)
    m = ((mask == 1) | (mask == 3)).astype(np.float32)
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)


def below(shape, poly):
    """Maske: Pixel unterhalb eines Polygonzugs (x aufsteigend)."""
    h, w = shape
    xs = np.arange(w)
    yb = np.interp(xs, [p[0] for p in poly], [p[1] for p in poly])
    return np.arange(h)[:, None] > yb[None, :]


def largest(m):
    n, lab, st, _ = cv2.connectedComponentsWithStats((m > 0.5).astype(np.uint8))
    if n <= 1:
        return m
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return m * (lab == k)


def save_rgba(im, m, path, feather=1.2):
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), feather)
    ys, xs = np.nonzero(m > 0.02)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([im[y0:y1, x0:x1, ::-1], (np.clip(m[y0:y1, x0:x1], 0, 1) * 255).astype(np.uint8)])
    cv2.imwrite(path, rgba[..., [2, 1, 0, 3]])
    return (x0, y0)


def main():
    # weißer Schläger + Puck
    im = cv2.imread(os.path.join(HERE, "stick_white_src.jpg"))
    m = grab(im, (0, 950, 2950, 1960), fg_fn=lambda s: s.max(2) < 70)
    edge = [(0, 1965), (1300, 1946), (1600, 1886), (1800, 1806), (2100, 1736), (2400, 1656), (2600, 1596),
            (2800, 1496), (2880, 1386), (3000, 1300), (4640, 1300)]
    bl = below(m.shape, edge)
    stick = largest(m * ~bl)
    save_rgba(im, stick, os.path.join(HERE, "stick_white.png"))
    dark = (im.max(2) < 95).astype(np.float32)
    dark[:1800] = 0
    dark[:, :2200] = 0
    dark[:, 2900:] = 0
    pk = largest(dark)
    hull = cv2.convexHull(np.argwhere(pk > 0.5)[:, ::-1].astype(np.int32))
    puck = np.zeros_like(pk)
    cv2.fillPoly(puck, [hull], 1.0)
    puck = cv2.erode(puck, np.ones((5, 5), np.uint8))
    save_rgba(im, puck, os.path.join(HERE, "puck.png"))
    # schwarzer Schläger
    im = cv2.imread(os.path.join(HERE, "stick_black_src.jpg"))
    m = grab(im, (0, 560, 3800, 1750), fg_fn=lambda s: s.max(2) < 60)
    edge = [(0, 1262), (456, 1467), (913, 1741), (1369, 1718), (2282, 1536), (2966, 1216), (4564, 1216)]
    m = largest(m * ~below(m.shape, edge))
    cnts, _ = cv2.findContours((m > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    m = np.zeros_like(m)
    cv2.drawContours(m, cnts, -1, 1.0, -1)
    save_rgba(im, m, os.path.join(HERE, "stick_black.png"))
    # Handschuh (links im Bild), Hintergrund hellgrau
    im = cv2.imread(os.path.join(HERE, "glove_src.jpg"))
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    fg = ((hsv[..., 1] > 70) | (hsv[..., 2] < 90)).astype(np.uint8)
    fg[:, 800:] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    fg = largest(fg.astype(np.float32))
    cnts, _ = cv2.findContours((fg > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    full = np.zeros_like(fg)
    cv2.drawContours(full, cnts, -1, 1.0, -1)
    # Markenschrift/Logo: weiße Pixel im Stulpenbereich ausmalen
    white = (hsv[..., 1] < 60) & (hsv[..., 2] > 170) & (full > 0.5)
    logo = np.zeros_like(white)
    logo[40:560] = white[40:560]
    logo = cv2.dilate(logo.astype(np.uint8), np.ones((7, 7), np.uint8))
    im = cv2.inpaint(im, logo, 9, cv2.INPAINT_TELEA)
    save_rgba(im, full, os.path.join(HERE, "glove.png"), feather=1.5)
    # Tor-Foto: Herstellerschrift auf dem Polster entfernen
    im = cv2.imread(os.path.join(HERE, "goal_src.jpg"))
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    box = np.zeros(im.shape[:2], np.uint8)
    box[2020:2170, 2340:2610] = 1
    txt = ((hsv[..., 0] > 85) & (hsv[..., 0] < 140) & (hsv[..., 1] > 40)) & (box > 0)
    txt = cv2.dilate(txt.astype(np.uint8), np.ones((9, 9), np.uint8))
    im = cv2.inpaint(im, txt, 7, cv2.INPAINT_TELEA)
    cv2.imwrite(os.path.join(HERE, "goal_clean.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print("fertig")


if __name__ == "__main__":
    main()
