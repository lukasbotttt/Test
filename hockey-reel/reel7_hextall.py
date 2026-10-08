"""Reel 7: "Hockey stories that sound fake – Part 2": A GOALIE SCORED A GOAL.

Aufruf: python3 reel7_hextall.py  ->  reel7_hextall.mp4
Fakten: Ron Hextall (Philadelphia Flyers) schoss am 8.12.1987 gegen Boston als erster NHL-Goalie
selbst ein Tor (Schuss ins leere Tor über das ganze Eis); am 11.4.1989 gelang ihm das auch in den
Playoffs (gegen Washington) – ebenfalls als Erster.
Fotos: Hextall 1987 – Jim Tyron, CC BY 2.0; Sammelkarte 1986 – gemeinfrei (Wikimedia Commons).
"""
import os
import subprocess

from PIL import Image, ImageDraw

import make_hockey_reel as m
import reel3_cup_day as r3
import reel4_legends2 as r4
import reel4b_action as ra
import reel5_sniper as r5
import reel6_zamboni as r6
from make_hockey_reel import ICE, WHITE, W, H, clamp, ease_out_cubic, paste_center, text_img

FPS = 30
HERE = m.HERE
r3.VOICE = os.path.join(HERE, "voice", "reel7.mp3")
r4.SENTENCES = ["A goalie scored a goal.",
                "In 1987, Ron Hextall shot the puck the length of the ice into an empty net.",
                "Then he did it again in the playoffs.",
                "Could YOU make that shot?"]
TAIL = 2.2
CARD = ("hextall_card.png", (0.0, 0.0, 1.0, 0.72))   # Sammelkarte ohne Logo-Band unten
ICE_PHOTO = ("hextall_ice.jpg", (0.22, 0.0, 0.62, 1.0))  # Ausschnitt auf Hextall (#27)
CREDIT_CARD = "Photo: 1986 Flyers postcard / public domain"
CREDIT_ICE = "Photo: Jim Tyron / CC BY 2.0"


def photo(frame, spec, lt, dur, z_from=1.0, z_to=1.12, fy=0.3):
    name, (x0, y0, x1, y1) = spec
    im = Image.open(os.path.join(r4.PHOTOS, name)).convert("RGB")
    im = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
    z = z_from + (z_to - z_from) * lt / dur
    s = max(W / im.width, H / im.height) * z
    big = im.resize((int(im.width * s), int(im.height * s)), Image.BICUBIC)
    cx = (big.width - W) // 2
    cy = int(clamp(fy * (big.height - H), 0, big.height - H))
    frame.paste(big.crop((cx, cy, cx + W, cy + H)), (0, 0))


def build(spans, total):
    s = [a for a, _ in spans]
    e = [b for _, b in spans]
    mid = s[1] + (e[1] - s[1]) * 0.5
    return [
        (0.0, e[0] + 0.15, "opener"),
        (e[0] + 0.15, s[1] - 0.06, "insert_stick"),
        (s[1] - 0.06, mid, "card"),
        (mid, e[1] + 0.12, "ice"),
        (e[1] + 0.12, s[2] - 0.06, "insert_net"),
        (s[2] - 0.06, e[2] + 0.15, "playoffs"),
        (e[2] + 0.15, total, "end"),
    ]


def draw(frame, kind, lt, dur):
    if kind == "opener":
        r5.clip_bg(frame, r5.GOAL_SHOT, lt, dur)
        frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 90)))
        ra.slam(frame, "A GOALIE", 200, ICE, W / 2, 1020, lt, 0.0)
        ra.slam(frame, "SCORED A GOAL", 140, WHITE, W / 2, 1200, lt, 0.2)
        ra.slam(frame, "Hockey stories that sound fake · Pt. 2", 46, WHITE, W / 2, 1330, lt, 0.5)
    elif kind == "insert_stick":
        r5.clip_bg(frame, r5.STICK, lt, dur)
    elif kind == "insert_net":
        r5.clip_bg(frame, r5.NET_HIT, lt, dur)
    elif kind == "card":
        photo(frame, CARD, lt, dur, 1.0, 1.12, 0.2)
        frame.alpha_composite(r4.SHADE)
        ra.slam(frame, "RON HEXTALL", 150, WHITE, W / 2, 1200, lt, 0.0)
        ra.slam(frame, "1987 · GOALIE", 84, ICE, W / 2, 1340, lt, 0.3)
        r4.credit(frame, CREDIT_CARD)
    elif kind == "ice":
        photo(frame, ICE_PHOTO, lt, dur, 1.05, 1.25, 0.25)
        frame.alpha_composite(r4.SHADE)
        ra.slam(frame, "FULL-ICE SHOT", 130, WHITE, W / 2, 1200, lt, 0.0)
        ra.slam(frame, "INTO THE EMPTY NET", 90, ICE, W / 2, 1340, lt, 0.25)
        r4.credit(frame, CREDIT_ICE)
    elif kind == "playoffs":
        photo(frame, CARD, lt, dur, 1.35, 1.6, 0.12)
        frame.alpha_composite(r4.SHADE)
        ra.slam(frame, "...THEN AGAIN", 130, WHITE, W / 2, 1200, lt, 0.0)
        ra.slam(frame, "IN THE PLAYOFFS", 110, ICE, W / 2, 1340, lt, 0.25)
        ra.slam(frame, "(1989)", 56, WHITE, W / 2, 1450, lt, 0.5)
        r4.credit(frame, CREDIT_CARD)
    else:  # end
        r5.clip_bg(frame, r6.GOALIE, lt, dur)
        frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 110)))
        ra.slam(frame, "COULD YOU", 150, WHITE, W / 2, 900, lt, 0.0)
        ra.slam(frame, "MAKE THAT SHOT?", 130, ICE, W / 2, 1060, lt, 0.15)
        r6.yes_no(frame, lt)
        if lt > 1.0:
            q = ease_out_cubic((lt - 1.0) / 0.3)
            paste_center(frame, text_img("Comment YES or NO", 62, WHITE, "ExtraBold"), W / 2, 1420 + (1 - q) * 60, alpha=q)


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
           "-movflags", "+faststart", "reel7_hextall.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=HERE)
    for i in range(nf):
        t = i / FPS
        k = max(j for j, sg in enumerate(segs) if sg[0] <= t + 1e-6)
        a, b, kind = segs[k]
        lt = t - a
        frame = Image.new("RGBA", (W, H), (5, 10, 25, 255))
        draw(frame, kind, lt, b - a)
        if t > 0.05:
            if lt < 0.07:
                frame = ra.glitch(frame, 18)
            if lt < 0.1:
                frame.alpha_composite(Image.new("RGBA", (W, H), (220, 245, 255, int(150 * (1 - lt / 0.1)))))
        frame = ra.apply_shake(frame, *ra.shake_offset(lt))
        d = ImageDraw.Draw(frame)
        d.rectangle((0, H - 12, W, H), fill=(0, 0, 0, 140))
        d.rectangle((0, H - 12, int(W * t / total), H), fill=ICE + (255,))
        proc.stdin.write(frame.convert("RGB").tobytes())
        if i == 18:
            frame.convert("RGB").save(os.path.join(HERE, "reel7_thumbnail.jpg"), quality=92)
    proc.stdin.close()
    proc.wait()
    print("fertig: reel7_hextall.mp4")


if __name__ == "__main__":
    main()
