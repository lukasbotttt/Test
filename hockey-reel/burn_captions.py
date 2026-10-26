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
LIGHT = False                                     # heller Studio-Look: dunkle Schrift mit weißem Halo
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

if len(sys.argv) > 1 and sys.argv[1] == "34":
    import reel34_octopus as O
    SRC, DST = "reel34_octopus.mp4", "reel34_octopus_cap.mp4"
    CAP_Y = 1660                                  # unter LED-Tafeln und FOLLOW, Logo ist schon im Video
    VO, TIMING, END = O, "reel34_timing.json", O.DUR - 0.1
    WORDS = {
        "q": "Why is THIS on the rink?",
        "born": "Detroit, 1952, Stanley Cup Final.",
        "arms": "Eight arms, for the eight wins it took to win the Cup.",
        "won": "Detroit won all eight.",
        "today": "Today you would need 16. Two octopuses.",
        "cta": "Next: why do fans throw hats? Follow so you don't miss it.",
    }

if len(sys.argv) > 1 and sys.argv[1] == "35":
    import reel35_hats as HT35
    SRC, DST = "reel35_hats.mp4", "reel35_hats_cap.mp4"
    CAP_Y = 1700                                  # unter Zählern, Hüten im Fokus und FOLLOW
    VO, TIMING, END = HT35, "reel35_timing.json", HT35.DUR - 0.1
    LIGHT = True
    WORDS = {
        "q": "Why is the ice covered in HATS?",
        "three": "Three goals by one player: a hat trick.",
        "cricket": "It started in cricket: three wickets, three balls, one new hat.",
        "toronto": "Then a Toronto hat shop promised a player a free hat for three goals. He scored four.",
        "fans": "Now fans throw theirs.",
        "cta": "Next: why do Florida fans throw rats? Follow.",
    }

if len(sys.argv) > 1 and sys.argv[1] == "36":
    import reel36_goalie_line as GL36
    SRC, DST = "reel36_goalie_line.mp4", "reel36_goalie_line_cap.mp4"
    CAP_Y = 1700
    VO, TIMING, END = GL36, "reel36_timing.json", GL36.DUR - 0.1
    LIGHT = True
    WORDS = {
        "q": "Why can't the goalie touch the puck HERE?",
        "rule": "Past the center red line, a goalie can't play the puck. Two-minute penalty.",
        "twist": "From his own half? He can shoot, and even score.",
        "cta": "Should that change? Follow for more rules.",
    }

if len(sys.argv) > 1 and sys.argv[1] == "37":
    import reel37_jersey as JS37
    SRC, DST = "reel37_jersey.mp4", "reel37_jersey_cap.mp4"
    CAP_Y = 1755
    VO, TIMING, END = JS37, "reel37_timing.json", JS37.DUR - 0.1
    LIGHT = True
    WORDS = {
        "q": "Why is THIS a penalty in the NHL?",
        "rule": "Protective gear has to be worn under the uniform. So every shift starts with the jersey untucked.",
        "pen": "Tucked anyway? First, a warning. Then, two minutes.",
        "hist": "It hadn't been called since 2013. This season, it's back.",
        "cta": "Should this be a penalty? Follow for more rules.",
    }

if len(sys.argv) > 1 and sys.argv[1] == "38":
    import reel38_quiz as QZ38
    SRC, DST = "reel38_quiz.mp4", "reel38_quiz_cap.mp4"
    CAP_Y = 1720
    VO, TIMING, END = QZ38, "reel38_timing.json", QZ38.DUR - 0.1
    LIGHT = True
    WORDS = {
        "q": "Three goals. Only ONE counts.",
        "lock": "Which one? Lock it in.",
        "r1": "One: the attacker's stick is above the crossbar. No goal.",
        "r2": "Two. Batted in by hand. No goal.",
        "r3": "Three counts! A defender's high stick into his own net is a goal.",
        "cta": "Did you get it? Follow for more rules.",
    }

if len(sys.argv) > 1 and sys.argv[1] == "39":
    import reel39_goalline as GL39
    SRC, DST = "reel39_goalline.mp4", "reel39_goalline_cap.mp4"
    CAP_Y = 1720
    VO, TIMING, END = GL39, "reel39_timing.json", GL39.DUR - 0.1
    LIGHT = True
    WORDS = {
        "q": "Three pucks. Only ONE is a goal.",
        "lock": "Which one? Lock it in.",
        "r1": "One: half on the line. Nope.",
        "r3": "Three: sooo close. Still touching. No goal.",
        "r2": "Two counts! The whole puck is over the line.",
        "cta": "Did you get it? Follow for part three.",
    }

if len(sys.argv) > 1 and sys.argv[1] == "40":
    import reel40_points as PT40
    SRC, DST = "reel40_points.mp4", "reel40_points_cap.mp4"
    CAP_Y = 1730
    VO, TIMING, END = PT40, "reel40_timing.json", PT40.DUR - 0.1
    LIGHT = True
    WORDS = {
        "q": "In the NHL, you get a point for losing.",
        "nhl": "Win: two points. Lose in overtime or a shootout? Still one.",
        "eu": "In Sweden, Finland and Germany, a regulation win is worth three.",
        "twist": "So in the NHL, some games are worth three points. Others, only two.",
        "cta": "NHL or Europe? Which is fairer?",
    }

if len(sys.argv) > 1 and sys.argv[1] == "40m":
    import reel40_motion as PM40
    SRC, DST = "reel40_motion.mp4", "reel40_motion_cap.mp4"
    CAP_Y = 1710                                  # dunkler Motion-Look: weiße Schrift, aktives Wort orange
    VO, TIMING, END = PM40, "reel40_timing.json", PM40.DUR - 0.1
    WORDS = {
        "q": "In the NHL, you get a point for losing.",
        "nhl": "Win: two points. Lose in overtime or a shootout? Still one.",
        "eu": "In Sweden, Finland and Germany, a regulation win is worth three.",
        "twist": "So in the NHL, some games are worth three points. Others, only two.",
        "cta": "NHL or Europe? Which is fairer?",
    }

if len(sys.argv) > 1 and sys.argv[1] == "41":
    import reel41_icing as IC41
    SRC, DST = "reel41_icing.mp4", "reel41_icing_cap.mp4"
    CAP_Y = 1710                                  # dunkler Motion-Look
    VO, TIMING, END = IC41, "reel41_timing.json", IC41.DUR - 0.1
    WORDS = {
        "q": "Three shots. Only ONE is icing.",
        "lock": "Which one?",
        "r1": "One touches the red line. No icing.",
        "r3": "Three is over it. No icing.",
        "r2": "But two never touched it. Icing!",
        "twist": "For a goal? The whole puck. For icing? Just a touch.",
        "cta": "Did you get it? Follow for part four.",
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
        if LIGHT:
            light_caption(img, g, t, t1, y, p)
            return
        for spr in sprs:
            sh, hx, hy = N.shadow(spr, 8)
            M.blit(img, sh, x + spr.tw / 2 - hx, y - hy + 4, p)
            M.draw(img, spr, x + spr.tw / 2, y, p, s)
            x += spr.tw + gap
        return


def light_caption(img, g, t, t1, y, p):
    """Wie im Video: schwarze Schrift (aktives Wort orange) mit weißem Halo."""
    import reel18_dangle as R18
    import reel15_puck as R15
    from PIL import Image
    ims = []
    for w, tw in g:
        act = tw <= t < (next((x for _, x in g if x > tw), t1))
        ims.append(R18.word_img(w.upper(), SIZE, R15.ORANGE if act else R15.INK, (255, 255, 255)))
    gap = 0.3 * SIZE - 80
    total = sum(im.width for im in ims) + gap * (len(ims) - 1)
    x = W / 2 - total / 2
    yy = y + 0 * p
    for im in ims:
        a = np.asarray(im).astype(np.float32) / 255
        x0, y0 = int(round(x)), int(round(yy - im.height / 2))
        xa, ya = max(0, x0), max(0, y0)
        xb, yb = min(W, x0 + im.width), min(H, y0 + im.height)
        if xb > xa and yb > ya:
            sub = a[ya - y0:yb - y0, xa - x0:xb - x0]
            al = sub[..., 3:4] * p
            img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - al) + sub[..., :3] * al
        x += im.width + gap


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
