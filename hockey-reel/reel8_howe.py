"""Reel 8: "Hockey stories that sound fake – Part 3": HE PLAYED PRO HOCKEY AT 69.

Aufruf: python3 reel8_howe.py  ->  reel8_howe.mp4
Fakten: Gordie Howe spielte 1979/80 mit 51/52 Jahren für die Hartford Whalers in der NHL – zusammen
mit seinen Söhnen Mark und Marty. Am 3.10.1997 spielte er mit 69 Jahren einen Wechsel (eine Schicht)
für die Detroit Vipers (IHL) und wurde so zum einzigen Profi, der in sechs Jahrzehnten gespielt hat.
Fotos: Chex-Sammelkarte (Red Wings) – gemeinfrei; Howe älter – Arnie Lee, CC BY 3.0 (Wikimedia Commons).
"""
import math
import os
import subprocess

from PIL import Image, ImageDraw

import make_hockey_reel as m
import reel3_cup_day as r3
import reel4_legends2 as r4
import reel4b_action as ra
import reel5_sniper as r5
import reel6_zamboni as r6
import reel7_hextall as r7
from make_hockey_reel import ICE, WHITE, W, H, ease_out_back, ease_out_cubic, paste_center, text_img

FPS = 30
HERE = m.HERE
r3.VOICE = os.path.join(HERE, "voice", "reel8.mp3")
r4.SENTENCES = ["This guy played pro hockey at sixty-nine.",
                "Gordie Howe played in the NHL at fifty-two, alongside his own sons.",
                "Then at sixty-nine, he took one more shift.",
                "Could YOU?"]
TAIL = 2.4
CARD = ("howe_card.jpg", (0.0, 0.0, 1.0, 0.8))
OLD = ("howe_old.jpg", (0.0, 0.0, 1.0, 0.75))
CREDIT_CARD = "Photo: Chex trading card / public domain"
CREDIT_OLD = "Photo: Arnie Lee / CC BY 3.0"


def stick_icon(d, cx, cy, s, col=WHITE):
    """Gezeichnetes Hockeyschläger-Symbol (Ersatz für das Emoji)."""
    d.line((cx - 18 * s, cy - 40 * s, cx + 6 * s, cy + 26 * s), fill=col + (255,), width=int(9 * s))
    d.polygon([(cx + 2 * s, cy + 22 * s), (cx + 34 * s, cy + 22 * s), (cx + 36 * s, cy + 34 * s),
               (cx + 2 * s, cy + 34 * s)], fill=col + (255,))
    d.ellipse((cx - 30 * s, cy + 24 * s, cx - 12 * s, cy + 34 * s), fill=(20, 20, 24, 255))


def drop_a_stick(frame, lt, y=1470):
    p = ease_out_back((lt - 1.1) / 0.3)
    if p <= 0:
        return
    left = text_img("DROP A", 64, WHITE, "Black")
    right = text_img("IF YOU DIDN'T KNOW THIS", 52, WHITE, "ExtraBold")
    gap = 90
    total = left.width + gap + right.width - 60
    x = W / 2 - total / 2
    paste_center(frame, left, x + left.width / 2, y, scale=p)
    d = ImageDraw.Draw(frame)
    bob = math.sin(lt * 7) * 6
    stick_icon(d, x + left.width - 10 + gap / 2, y - 4 + bob, 1.05 * p, ICE)
    paste_center(frame, right, x + left.width + gap - 30 + right.width / 2, y + 4, scale=p)


def build(spans, total):
    s = [a for a, _ in spans]
    e = [b for _, b in spans]
    return [
        (0.0, e[0] + 0.15, "opener"),
        (e[0] + 0.15, s[1] - 0.06, "insert_stick"),
        (s[1] - 0.06, e[1] + 0.12, "card"),
        (e[1] + 0.12, s[2] - 0.06, "insert_net"),
        (s[2] - 0.06, e[2] + 0.12, "old"),
        (e[2] + 0.12, total, "end"),
    ]


def draw(frame, kind, lt, dur):
    if kind == "opener":
        r5.clip_bg(frame, ra.OPENER, lt, dur)
        frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 90)))
        ra.slam(frame, "HE PLAYED PRO HOCKEY", 110, WHITE, W / 2, 980, lt, 0.0)
        ra.slam(frame, "AT 69", 260, ICE, W / 2, 1170, lt, 0.2)
        ra.slam(frame, "Hockey stories that sound fake · Pt. 3", 46, WHITE, W / 2, 1340, lt, 0.5)
    elif kind == "insert_stick":
        r5.clip_bg(frame, r5.STICK, lt, dur)
    elif kind == "insert_net":
        r5.clip_bg(frame, r5.NET_HIT, lt, dur)
    elif kind == "card":
        r7.photo(frame, CARD, lt, dur, 1.0, 1.15, 0.15)
        frame.alpha_composite(r4.SHADE)
        ra.slam(frame, "GORDIE HOWE", 150, WHITE, W / 2, 1200, lt, 0.0)
        ra.slam(frame, "NHL AT 52", 100, ICE, W / 2, 1340, lt, 0.3)
        ra.slam(frame, "...WITH HIS OWN SONS", 70, WHITE, W / 2, 1450, lt, dur * 0.55)
        r4.credit(frame, CREDIT_CARD)
    elif kind == "old":
        r7.photo(frame, OLD, lt, dur, 1.0, 1.15, 0.2)
        frame.alpha_composite(r4.SHADE)
        ra.slam(frame, "AT 69:", 150, WHITE, W / 2, 1200, lt, 0.0)
        ra.slam(frame, "ONE MORE SHIFT", 110, ICE, W / 2, 1340, lt, 0.25)
        ra.slam(frame, "(1997 · 6 DECADES AS A PRO)", 52, WHITE, W / 2, 1450, lt, 0.6)
        r4.credit(frame, CREDIT_OLD)
    else:  # end
        r5.clip_bg(frame, r6.GOALIE, lt, dur)
        frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 110)))
        ra.slam(frame, "COULD YOU", 150, WHITE, W / 2, 880, lt, 0.0)
        ra.slam(frame, "PLAY AT 69?", 140, ICE, W / 2, 1040, lt, 0.15)
        r6.yes_no(frame, lt)
        drop_a_stick(frame, lt)


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
           "-movflags", "+faststart", "reel8_howe.mp4"]
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
            frame.convert("RGB").save(os.path.join(HERE, "reel8_thumbnail.jpg"), quality=92)
    proc.stdin.close()
    proc.wait()
    print("fertig: reel8_howe.mp4")


if __name__ == "__main__":
    main()
