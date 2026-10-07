"""Reel 5: "BURE > SELÄNNE?" – Debatte im Action-Stil, These schon in Sekunde 1.

Aufruf: python3 reel5_sniper.py  ->  reel5_sniper.mp4
Fakten: Selänne 684 NHL-Tore (1451 Spiele, 0,47 pro Spiel);
        Bure 437 NHL-Tore in 702 Spielen (0,62 pro Spiel).
Fotos: Wikimedia Commons (siehe reel4_legends2.py), Clips: Pexels (Tima Miroshnichenko).
"""
import math
import os
import subprocess

from PIL import Image, ImageDraw

import make_hockey_reel as m
import reel3_cup_day as r3
import reel4_legends2 as r4
import reel4b_action as ra
from make_hockey_reel import ICE, WHITE, W, H, clamp, ease_out_back, ease_out_cubic, paste_center, text_img

FPS = 30
HERE = m.HERE
r3.VOICE = os.path.join(HERE, "voice", "reel5.mp3")
r4.SENTENCES = ["Pavel Bure was a better sniper than Teemu Selanne.",
                "Selanne scored six hundred eighty-four goals.",
                "But Bure scored four hundred thirty-seven in just seven hundred two games.",
                "So who's the real sniper?"]
TAIL = 1.8
ra.FACES["selanne.jpg"] = (0.45, 0.2, 1.25)  # Foto hat geringe Auflösung -> weniger Zoom
SEL = ("selanne.jpg", "TEEMU SELÄNNE", "Photo: Arnold C / Wikimedia Commons")
BURE = ("bure.jpg", "PAVEL BURE", "Photo: Håkan Dahlström / CC BY 2.0")
GOAL_SHOT = ("6847328-hd_720_1280_25fps.mp4", 3.0)   # Schuss, Puck schlägt im Netz ein
NET_HIT = ("6847335-hd_720_1280_25fps.mp4", 2.2)     # Puck ins Netz (hinter dem Tor)
STICK = ("6848067-hd_720_1280_25fps.mp4", 5.0)       # Schläger trifft Puck


def clip_bg(frame, clip, lt, dur):
    frames = ra.clip_frames(clip[0], clip[1], dur)
    img = Image.fromarray(frames[min(int(lt * FPS), len(frames) - 1)])
    z = 1.15 + 0.25 * lt / dur
    big = img.resize((int(W * z), int(H * z)), Image.BILINEAR)
    ox, oy = (big.width - W) // 2, (big.height - H) // 2
    frame.paste(big.crop((ox, oy, ox + W, oy + H)), (0, 0))


def thesis(frame, lt, y=1180):
    ra.slam(frame, "BURE", 210, ICE, W / 2, y - 120, lt, 0.0)
    ra.slam(frame, "> SELÄNNE?", 170, WHITE, W / 2, y + 80, lt, 0.15)


def split(frame, lt, left, right):
    p = ease_out_cubic(lt / 0.25)
    ph = (lt % ra.BEAT) / ra.BEAT
    bump = 0.06 * math.exp(-ph * 6)
    n = int(lt / ra.BEAT)
    tmp = Image.new("RGBA", (W, H), (5, 10, 25, 255))
    r4.place(tmp, left[0], 0, 0, 540, H, 1.0 + 0.05 * lt + (bump if n % 2 == 0 else 0), 0.3)
    r4.place(tmp, right[0], 540, 0, 540, H, 1.0 + 0.05 * lt + (bump if n % 2 else 0), 0.3)
    frame.paste(tmp.crop((0, 0, 540, H)), (int(-540 * (1 - p)), 0))
    frame.paste(tmp.crop((540, 0, W, H)), (540 + int(540 * (1 - p)), 0))
    frame.alpha_composite(r4.SHADE)
    d = ImageDraw.Draw(frame)
    d.line((540, 0, 540, H), fill=ICE, width=8 + int(4 * math.sin(lt * 10)))
    r = 85 * ease_out_back((lt - 0.15) / 0.25) * (1 + 0.08 * math.sin(lt * 9))
    if r > 5:
        d.ellipse((W / 2 - r, 760 - r, W / 2 + r, 760 + r), fill=(5, 10, 25), outline=ICE, width=8)
        paste_center(frame, text_img("VS", 100, WHITE), W / 2, 763, scale=clamp(r / 85))


def player(frame, lt, dur, p, lines, cut=0.45):
    name, nm, cred = p
    if lt < dur * cut:
        r4.place(frame, name, 0, 0, W, H, 1.0 + 0.12 * lt / dur, 0.3)
    else:
        ra.face_zoom(frame, name, lt - dur * cut)
    frame.alpha_composite(r4.SHADE)
    ra.slam(frame, nm, 140, WHITE, W / 2, 1200, lt, 0.0)
    for txt, size, col, y, delay in lines:
        ra.slam(frame, txt, size, col, W / 2, y, lt, delay)
    r4.credit(frame, cred)


def count(txt_fn, lt, start, dur, target):
    return txt_fn(int(target * ease_out_cubic((lt - start) / dur)))


def build(spans, total):
    s = [a for a, _ in spans]
    e = [b for _, b in spans]
    return [
        (0.0, 0.9, "opener"),
        (0.9, e[0] + 0.25, "split1"),
        (e[0] + 0.25, s[1] - 0.06, "insert_net"),
        (s[1] - 0.06, s[2] - 0.06, "selanne"),
        (s[2] - 0.06, e[2] + 0.1, "bure"),
        (e[2] + 0.1, s[3] - 0.06, "insert_stick"),
        (s[3] - 0.06, total, "end"),
    ]


def draw(frame, kind, lt, dur, t, spans):
    if kind == "opener":
        clip_bg(frame, GOAL_SHOT, lt, dur)
        frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 80)))
        thesis(frame, lt)
        ra.slam(frame, "CHANGE MY MIND", 70, WHITE, W / 2, 1420, lt, 0.4)
    elif kind == "split1":
        split(frame, lt, BURE, SEL)
        paste_center(frame, text_img("BURE", 210, ICE), W / 2, 1060)
        paste_center(frame, text_img("> SELÄNNE?", 170, WHITE), W / 2, 1260)
        ra.slam(frame, "CHANGE MY MIND", 70, WHITE, W / 2, 1420, lt, 0.2)
    elif kind == "insert_net":
        clip_bg(frame, NET_HIT, lt, dur)
    elif kind == "insert_stick":
        clip_bg(frame, STICK, lt, dur)
    elif kind == "selanne":
        player(frame, lt, dur, SEL, [])
        n = int(684 * ease_out_cubic((lt - 0.3) / 1.2)) if lt > 0.3 else 0
        if lt > 0.3:
            paste_center(frame, text_img(f"{n} GOALS", 110, ICE), W / 2, 1360,
                         scale=1 + (0.12 * clamp(1 - (lt - 1.5) / 0.2) if lt > 1.5 else 0))
    elif kind == "bure":
        player(frame, lt, dur, BURE, [])
        n = int(437 * ease_out_cubic((lt - 0.3) / 1.0)) if lt > 0.3 else 0
        if lt > 0.3:
            paste_center(frame, text_img(f"{n} GOALS", 110, ICE), W / 2, 1360)
        games_at = spans[2][0] + (spans[2][1] - spans[2][0]) * 0.55 - (spans[2][0] - 0.06)
        ra.slam(frame, "IN JUST 702 GAMES", 80, WHITE, W / 2, 1480, lt, games_at)
    else:  # end
        split(frame, lt, BURE, SEL)
        ra.slam(frame, "BURE", 92, ICE, 270, 1030, lt, 0.1)
        ra.slam(frame, "SELÄNNE", 92, ICE, 810, 1030, lt, 0.2)
        ra.slam(frame, "0.62 G/GP", 64, WHITE, 270, 1130, lt, 0.35)
        ra.slam(frame, "0.47 G/GP", 64, WHITE, 810, 1130, lt, 0.45)
        ra.slam(frame, "REAL SNIPER?", 150, WHITE, W / 2, 1290, lt, 0.6)
        if lt > 1.0:
            q = ease_out_cubic((lt - 1.0) / 0.3)
            paste_center(frame, text_img("Comment your pick", 60, WHITE, "ExtraBold"), W / 2, 1430 + (1 - q) * 60, alpha=q)
            d = ImageDraw.Draw(frame)
            y = 1495 + abs(math.sin(lt * 6)) * 26
            d.polygon([(W / 2 - 36, y), (W / 2 + 36, y), (W / 2, y + 46)], fill=ICE + (255,))
        r4.credit(frame, "Photos: H. Dahlström CC BY 2.0 · Arnold C / Wikimedia Commons")


def main():
    voice = r3.load_voice()
    spans = r4.sentence_spans(r3.speech_segments(voice))
    total = spans[-1][1] + TAIL
    segs = build(spans, total)
    for a, b, k in segs:
        print(f"{a:5.2f}-{b:5.2f} {k}")
    cuts = [a for a, _, _ in segs] + [total]
    ra.mix(voice, cuts, total)
    nf = int(round(total * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", "audio_mix.wav", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", "reel5_sniper.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=HERE)
    for i in range(nf):
        t = i / FPS
        k = max(j for j, sg in enumerate(segs) if sg[0] <= t + 1e-6)
        a, b, kind = segs[k]
        lt = t - a
        frame = Image.new("RGBA", (W, H), (5, 10, 25, 255))
        draw(frame, kind, lt, b - a, t, spans)
        cut_lt = lt
        if kind in ("selanne", "bure") and lt >= (b - a) * 0.45:
            cut_lt = lt - (b - a) * 0.45
        if t > 0.05:
            if cut_lt < 0.07:
                frame = ra.glitch(frame, 18)
            if cut_lt < 0.1:
                frame.alpha_composite(Image.new("RGBA", (W, H), (220, 245, 255, int(150 * (1 - cut_lt / 0.1)))))
        frame = ra.apply_shake(frame, *ra.shake_offset(cut_lt))
        d = ImageDraw.Draw(frame)
        d.rectangle((0, H - 12, W, H), fill=(0, 0, 0, 140))
        d.rectangle((0, H - 12, int(W * t / total), H), fill=ICE + (255,))
        proc.stdin.write(frame.convert("RGB").tobytes())
        if i == 15:
            frame.convert("RGB").save(os.path.join(HERE, "reel5_thumbnail.jpg"), quality=92)
    proc.stdin.close()
    proc.wait()
    print("fertig: reel5_sniper.mp4")


if __name__ == "__main__":
    main()
