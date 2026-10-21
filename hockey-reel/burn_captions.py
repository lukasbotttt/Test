"""TikTok-Untertitel (Wort für Wort, aktives Wort orange) in ein fertiges Video einbrennen – ohne Neu-Rendern.

Wortzeiten aus dem Voiceover-Timing des jeweiligen Reels (VO_START + WT, faster-whisper), max. 3 Wörter pro Zeile.
Aufruf: python3 burn_captions.py        (reel33_lines_neon.mp4 -> reel33_lines_neon_cap.mp4)
        python3 burn_captions.py 31     (reel31_powerplay.mp4 -> reel31_powerplay_cap.mp4, + Logo oben)
"""
import json
import os
import subprocess
import sys

import numpy as np

import reel31_powerplay as M
import reel33_lines_neon as N

L = N.L
W, H, FPS = 1080, 1920, 30
SRC, DST = "reel33_lines_neon.mp4", "reel33_lines_neon_cap.mp4"
CAP_Y = 1535
SIZE = 56
VO, TIMING, END = L, "reel32_timing.json", N.T_END
LOGO_FROM = None                                  # Part 8: Logo-Lockup oben ab Ende der Hook-Frage
WORDS = {
    "q": "What do all these lines on a hockey rink mean?",
    "red": "Red line: shoot it from your half past their goal line? Icing.",
    "blue": "Blue lines: beat the puck into the zone? Offside.",
    "goal": "Goal line: the whole puck has to cross.",
    "dots": "Nine dots: every faceoff _ happens on one.",
    "crease": "Blue paint: the goalie's crease.",
    "trap": "And the trapezoid: the only place behind the net a goalie can play the puck.",
    "cta": "Which one didn't you know? One to six.",
}

if len(sys.argv) > 1 and sys.argv[1] == "31":
    SRC, DST = "reel31_powerplay.mp4", "reel31_powerplay_cap.mp4"
    CAP_Y = 1440                                  # unter dem Panel und den Fortschrittspunkten
    VO, TIMING, END = M, "reel31_timing.json", M.DUR - 0.1
    LOGO_FROM = M.T_SH + 0.1
    WORDS = {
        "q": "Why can THIS team ice the puck?",
        "sh": "They're short-handed. _ Four on five.",
        "rule": "Icing only counts if you're even or stronger. No whistle.",
        "goal": "Power-play _ goal? The minor ends. Instantly.",
        "blame": "Blame it on Montreal.",
        "hist": "Béliveau once scored three goals in forty-four seconds on one power play.",
        "cta": "Should short-handed _ teams get to ice it? Yes or no?",
    }


def chunks():
    """-> Liste (t0, t1, [(wort, t_wort)])"""
    with open(os.path.join(L.HERE, "voice", TIMING)) as f:
        dur = {k: v / VO.TEMPO for k, v in json.load(f).items()}
    out = []
    for key, text in WORDS.items():
        ws = text.split()
        ts = [VO.wt(key, i) for i in range(len(ws))]
        pairs = [(w, t) for w, t in zip(ws, ts) if w != "_"]
        end = min(VO.VO_START[key] + dur[key] - 0.05, END - 0.05)
        groups, cur = [], []
        for w, t in pairs:                       # max. 3 Wörter, nach Satzzeichen neue Zeile
            cur.append((w, t))
            if len(cur) == 3 or w[-1] in ".?:!,":
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        for i, g in enumerate(groups):
            t1 = groups[i + 1][0][1] if i + 1 < len(groups) else end
            out.append((g[0][1] - 0.04, t1 - 0.02, g))
    return out


CH = chunks()
ORANGE, WHITE = N.ORANGE, N.WHITE


def draw_logo(img, t):
    if LOGO_FROM is None or t < LOGO_FROM:
        return
    lk = N.brand_img("bladesandpucks_lockup_transparent.png", 320)
    M.draw(img, lk, 540, 330, 0.92 * M.c01((t - LOGO_FROM) / 0.3))


def draw_caption(img, t):
    for t0, t1, g in CH:
        if not (t0 <= t < t1):
            continue
        p = M.c01((t - t0) / 0.12)
        sprs = []
        for w, tw in g:
            col = ORANGE if tw <= t < (next((x for _, x in g if x > tw), t1)) else WHITE
            sprs.append(M.text_spr(w.upper(), "x8", SIZE, col, 0.01))
        gap = 0.3 * SIZE
        total = sum(s.tw for s in sprs) + gap * (len(sprs) - 1)
        x = W / 2 - total / 2
        y = CAP_Y + 18 * (1 - M.e_out(p))
        s = 0.92 + 0.08 * M.e_out(p)
        for spr in sprs:
            sh, hx, hy = N.shadow(spr, 8)
            M.blit(img, sh, x + spr.tw / 2 - hx, y - hy + 4, p)
            M.draw(img, spr, x + spr.tw / 2, y, p, s)
            x += spr.tw + gap
        return


def main():
    os.chdir(L.HERE)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", SRC, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                            "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest",
                            "-movflags", "+faststart", DST], stdin=subprocess.PIPE)
    n = 0
    while True:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32) / 255
        draw_logo(img, n / FPS)
        draw_caption(img, n / FPS)
        enc.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    print("fertig:", DST, n, "Bilder")


if __name__ == "__main__":
    main()
