"""Reel 2: "NHL records that will NEVER be broken" (nutzt Grafik + Audio aus make_hockey_reel).

Aufruf: python3 reel2_records.py  ->  reel2_records.mp4
Fakten:
- Henri Richard: 11 Stanley Cups als Spieler (Rekord)
- Glenn Hall: 502 aufeinanderfolgende komplette Spiele als Goalie (1955-1962), ohne Maske
- Darryl Sittler: 10 Punkte in einem Spiel (6 Tore, 4 Assists), 7. Feb. 1976
"""
import math
import os
import subprocess

from PIL import Image, ImageDraw

import make_hockey_reel as m
from make_hockey_reel import (ICE, WHITE, GREY, W, H, FPS, clamp, ease_out_back, ease_out_cubic,
                              ease_in_out, pop, slide_up, pill, flash, paste_center, text_img,
                              puck, shadow, speed_lines, ice_spray, goal_light)

GOLD = (255, 200, 60)


def scene_hook(frame, t):
    stop = 0.45
    tx, ty = W / 2, 1250
    p = ease_out_cubic(t / stop)
    x = W + 300 - (W + 300 - tx) * p  # diesmal von rechts
    if t < stop + 0.1:
        speed_lines(frame, x, x + 700, ty, 40, alpha=clamp(1 - t / (stop + 0.1)), seed=3)
    shadow(frame, x, ty + 70, 330)
    paste_center(frame, puck(320), x, ty)
    ice_spray(frame, t - stop + 0.1, tx - 140, ty + 40, 8)
    shake = math.sin(t * 70) * 10 * clamp(1 - (t - stop) / 0.3) if t > stop else 0
    pop(frame, "NHL RECORDS", 170, WHITE, W / 2 + shake, 430, t, 0.05)
    pop(frame, "THAT WILL", 150, WHITE, W / 2 - shake, 600, t, 0.3)
    pop(frame, "NEVER BE BROKEN", 140, ICE, W / 2, 770, t, 0.55)
    slide_up(frame, "#1 is unreal", 56, WHITE, W / 2, 1560, t, 1.3)


def cup(d, cx, cy, s, col):
    """Einfache Stanley-Cup-Silhouette."""
    d.ellipse((cx - 22 * s, cy - 40 * s, cx + 22 * s, cy - 24 * s), fill=col)
    d.polygon([(cx - 22 * s, cy - 32 * s), (cx + 22 * s, cy - 32 * s), (cx + 9 * s, cy - 12 * s),
               (cx - 9 * s, cy - 12 * s)], fill=col)
    d.rectangle((cx - 9 * s, cy - 12 * s, cx + 9 * s, cy - 4 * s), fill=col)
    for k, wdt in enumerate((14, 17, 20, 23)):
        y = cy - 4 * s + k * 9 * s
        d.rectangle((cx - wdt * s, y, cx + wdt * s, y + 8 * s), fill=col)
        d.line((cx - wdt * s, y + 8 * s, cx + wdt * s, y + 8 * s), fill=(120, 90, 20, 255), width=2)


def scene_richard(frame, t):
    flash(frame, t)
    pill(frame, "RECORD 1 / 3", 330, t)
    pop(frame, "HENRI RICHARD WON", 112, WHITE, W / 2, 470, t, 0.1)
    n = int(clamp((t - 0.7) / 1.9) * 11 + 0.999) if t > 0.7 else 0
    big = 1 + (0.12 * clamp(1 - (t - 2.6) / 0.25) if t > 2.6 else 0)
    if t > 0.7:
        paste_center(frame, text_img(str(n), 260, GOLD if n == 11 else WHITE), W / 2, 680, scale=big)
    pop(frame, "STANLEY CUPS", 120, ICE, W / 2, 860, t, 0.5)
    d = ImageDraw.Draw(frame)
    for i in range(n):  # 11 Pokale in zwei Reihen
        row, col = (0, i) if i < 6 else (1, i - 6)
        per = 6 if row == 0 else 5
        cx = W / 2 + (col - (per - 1) / 2) * 150
        cy = 1080 + row * 190
        cup(d, cx, cy, 1.9, GOLD + (255,))
    slide_up(frame, "as a player. The most ever.", 54, WHITE, W / 2, 1440, t, 2.9)
    slide_up(frame, "Nobody else has more than 10.", 54, GREY, W / 2, 1515, t, 3.2)


def scene_hall(frame, t):
    flash(frame, t)
    pill(frame, "RECORD 2 / 3", 330, t)
    pop(frame, "GOALIE GLENN HALL", 112, WHITE, W / 2, 470, t, 0.1)
    pop(frame, "STARTED", 100, WHITE, W / 2, 600, t, 0.3)
    fill = ease_in_out((t - 0.5) / 1.6)
    big = 1 + (0.12 * clamp(1 - (t - 2.1) / 0.25) if t > 2.1 else 0)
    paste_center(frame, text_img(str(int(502 * fill)), 300, WHITE if fill < 1 else ICE), W / 2, 830, scale=big)
    pop(frame, "GAMES IN A ROW", 120, ICE, W / 2, 1040, t, 0.6)
    # Fortschrittsbalken "Spiele"
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle((90, 1150, 990, 1190), radius=20, fill=(255, 255, 255, 30))
    d.rounded_rectangle((90, 1150, 90 + max(40, 900 * fill), 1190), radius=20, fill=ICE + (255,))
    if 2.1 < t < 2.7:
        p = (t - 2.1) / 0.6
        x = -200 + (W + 400) * p
        speed_lines(frame, x - 900, x, 1290, 30, seed=11)
        paste_center(frame, puck(150), x, 1290)
    slide_up(frame, "Every minute of every game.", 54, WHITE, W / 2, 1420, t, 2.5)
    slide_up(frame, "WITHOUT A MASK.", 76, ICE, W / 2, 1510, t, 2.8, kind="Black")


def scene_sittler(frame, t):
    flash(frame, t)
    pill(frame, "RECORD 3 / 3", 330, t)
    pop(frame, "DARRYL SITTLER SCORED", 100, WHITE, W / 2, 470, t, 0.1)
    pop(frame, "10 POINTS", 220, ICE, W / 2, 650, t, 0.4, angle=-2)
    pop(frame, "IN ONE GAME", 120, WHITE, W / 2, 830, t, 0.7)
    # 6 Tore + 4 Assists als Pucks / Punkte
    d = ImageDraw.Draw(frame)
    for i in range(10):
        p = (t - 1.2 - i * 0.12) / 0.3
        if p <= 0:
            continue
        goal = i < 6
        row, col = (0, i) if goal else (1, i - 6)
        per = 6 if goal else 4
        cx = W / 2 + (col - (per - 1) / 2) * 150
        cy = 1040 + row * 200
        if goal:
            paste_center(frame, puck(110), cx, cy, scale=ease_out_back(p))
        else:
            r = 44 * ease_out_back(p)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ICE + (255,), width=10)
    slide_up(frame, "6 GOALS", 50, WHITE, W / 2, 1125, t, 2.4, kind="Black")
    slide_up(frame, "4 ASSISTS", 50, ICE, W / 2, 1325, t, 2.6, kind="Black")
    slide_up(frame, "Feb 7, 1976. Still the NHL record.", 50, GREY, W / 2, 1480, t, 3.2)


def scene_cta(frame, t):
    flash(frame, t)
    goal_light(frame, t)
    pop(frame, "WHAT RECORD", 160, WHITE, W / 2, 480, t, 0.05)
    pop(frame, "DID WE", 160, WHITE, W / 2, 660, t, 0.25)
    pop(frame, "MISS?", 230, ICE, W / 2, 860, t, 0.45, angle=math.sin(t * 5) * 1.5)
    if t > 0.5:
        shadow(frame, W / 2, 1150, 260, 0.4)
        paste_center(frame, puck(240), W / 2, 1090 + math.sin(t * 5) * 14,
                     scale=ease_out_back((t - 0.5) / 0.4))
    slide_up(frame, "Drop it in the comments", 56, WHITE, W / 2, 1310, t, 0.9)
    if t > 1.1:
        d = ImageDraw.Draw(frame)
        y = 1395 + abs(math.sin(t * 6)) * 30
        d.polygon([(W / 2 - 40, y), (W / 2 + 40, y), (W / 2, y + 50)], fill=ICE + (255,))
    slide_up(frame, "+ FOLLOW FOR PART 2", 64, ICE, W / 2, 1540, t, 1.5, kind="Black")


# Szenen in das Basis-Modul einsetzen (Render-Loop, Fortschrittsbalken und Audio nutzen sie)
m.SCENES = [(0.0, 2.8), (2.8, 7.8), (7.8, 13.0), (13.0, 18.6), (18.6, 22.6)]
m.DURATION = m.SCENES[-1][1]
m.SCENE_FUNCS = [scene_hook, scene_richard, scene_hall, scene_sittler, scene_cta]


def main():
    os.chdir(m.HERE)
    m.make_audio("audio.wav")
    nf = int(m.DURATION * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", "audio.wav", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", "reel2_records.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(nf):
        proc.stdin.write(m.render_frame(i).tobytes())
    proc.stdin.close()
    proc.wait()
    m.render_frame(int(1.9 * FPS)).save("reel2_thumbnail.jpg", quality=92)
    print("fertig: reel2_records.mp4")


if __name__ == "__main__":
    main()
