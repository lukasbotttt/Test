"""Reel 6: "A ZAMBONI DRIVER WON AN NHL GAME" – wilde wahre Story + Ja/Nein-Frage.

Aufruf: python3 reel6_zamboni.py  ->  reel6_zamboni.mp4
Fakten:
- David Ayres (42), Eismaschinen-Fahrer/Arena-Mitarbeiter, sprang am 22.02.2020 als Notfall-Goalie
  für Carolina ein, hielt 8 von 10 Schüssen, Carolina schlug Toronto 6:3.
- Lester Patrick (44), Trainer der NY Rangers, ging im Stanley-Cup-Finale 1928 (Spiel 2) ins Tor
  und gewann 2:1 nach Verlängerung.
Fotos: Ayres – JFVoll, CC BY-SA 4.0 (Wikimedia Commons); Patrick – gemeinfrei.
Clips: Pexels (Артём Старшинов, Tima Miroshnichenko).
"""
import math
import os
import subprocess

from PIL import Image, ImageDraw, ImageOps

import make_hockey_reel as m
import reel3_cup_day as r3
import reel4_legends2 as r4
import reel4b_action as ra
import reel5_sniper as r5
from make_hockey_reel import ICE, WHITE, W, H, clamp, ease_out_back, ease_out_cubic, paste_center, text_img

FPS = 30
HERE = m.HERE
r3.VOICE = os.path.join(HERE, "voice", "reel6.mp3")
r4.SENTENCES = ["A Zamboni driver won an NHL game.",
                "Forty-two-year-old David Ayres came in as emergency goalie and beat the Maple Leafs.",
                "And in 1928, a forty-four-year-old coach did it in the Stanley Cup Final.",
                "Could YOU stop an NHL shot?"]
TAIL = 2.2
GREEN, RED = (40, 220, 120), (235, 45, 60)
ra.FACES["ayres.jpg"] = (0.78, 0.22, 1.6)
AYRES = ("ayres.jpg", "DAVID AYRES, 42", "Photo: JFVoll / CC BY-SA 4.0")
ZAMBONI = ("11159532-hd_720_1280_25fps.mp4", 3.0)
GOALIE = ("6848153-hd_1080_1920_25fps.mp4", 9.0)  # Goalie hält


def zoom_clip(frame, clip, lt, dur, z0=2.2, fy=0.58):
    """Clip mit starkem Zoom auf einen Bildbereich (Eismaschine ist im Original klein)."""
    frames = ra.clip_frames(clip[0], clip[1], dur)
    img = Image.fromarray(frames[min(int(lt * FPS), len(frames) - 1)])
    z = z0 + 0.3 * lt / dur
    big = img.resize((int(W * z), int(H * z)), Image.BILINEAR)
    cx = (big.width - W) // 2
    cy = int(clamp(fy * big.height - H / 2, 0, big.height - H))
    frame.paste(big.crop((cx, cy, cx + W, cy + H)), (0, 0))


def vintage(frame, lt, dur):
    """Lester-Patrick-Foto (gemeinfrei, s/w) mit Sepia, Vignette und Push-in."""
    im = Image.open(os.path.join(r4.PHOTOS, "patrick.jpg")).convert("L")
    im = ImageOps.colorize(im, (25, 18, 10), (245, 225, 190))
    z = 1.05 + 0.15 * lt / dur
    s = max(W / im.width, H / im.height) * z
    big = im.resize((int(im.width * s), int(im.height * s)), Image.BICUBIC)
    cx = (big.width - W) // 2
    cy = int(clamp(0.25 * big.height - H * 0.3, 0, big.height - H))
    frame.paste(big.crop((cx, cy, cx + W, cy + H)), (0, 0))


def yes_no(frame, lt):
    d = ImageDraw.Draw(frame)
    for i, (txt, col) in enumerate((("YES", GREEN), ("NO", RED))):
        p = ease_out_back((lt - 0.35 - i * 0.15) / 0.3)
        if p <= 0:
            continue
        cx = 300 + i * 480
        w, h = 380 * p, 170 * p
        pulse = 1 + 0.05 * math.sin(lt * 8 + i * math.pi)
        w, h = w * pulse, h * pulse
        d.rounded_rectangle((cx - w / 2, 1250 - h / 2, cx + w / 2, 1250 + h / 2), radius=int(30 * p), fill=col + (255,))
        if p > 0.3:
            paste_center(frame, text_img(txt, 130, WHITE), cx, 1255, scale=p * pulse)


def build(spans, total):
    s = [a for a, _ in spans]
    e = [b for _, b in spans]
    return [
        (0.0, e[0] + 0.15, "opener"),
        (e[0] + 0.15, s[1] - 0.06, "insert_net"),
        (s[1] - 0.06, e[1] + 0.1, "ayres"),
        (e[1] + 0.1, s[2] - 0.06, "insert_stick"),
        (s[2] - 0.06, e[2] + 0.1, "patrick"),
        (e[2] + 0.1, total, "end"),
    ]


def draw(frame, kind, lt, dur, spans):
    if kind == "opener":
        zoom_clip(frame, ZAMBONI, lt, dur)
        frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 90)))
        ra.slam(frame, "A ZAMBONI DRIVER", 150, ICE, W / 2, 1040, lt, 0.0)
        ra.slam(frame, "WON AN NHL GAME", 130, WHITE, W / 2, 1200, lt, 0.2)
        ra.slam(frame, "(this really happened)", 54, WHITE, W / 2, 1330, lt, 0.6)
    elif kind == "insert_net":
        r5.clip_bg(frame, r5.NET_HIT, lt, dur)
    elif kind == "insert_stick":
        r5.clip_bg(frame, r5.STICK, lt, dur)
    elif kind == "ayres":
        r5.player(frame, lt, dur, AYRES, [("EMERGENCY GOALIE", 84, ICE, 1340, 0.35),
                                          ("8 SAVES · BEAT TORONTO", 72, WHITE, 1460, 1.4)])
        r4.credit(frame, AYRES[2])
    elif kind == "patrick":
        vintage(frame, lt, dur)
        frame.alpha_composite(r4.SHADE)
        ra.slam(frame, "1928 CUP FINAL", 130, WHITE, W / 2, 1200, lt, 0.0)
        ra.slam(frame, "44-YEAR-OLD COACH IN NET", 76, ICE, W / 2, 1340, lt, 0.5)
        ra.slam(frame, "...AND WON IN OT", 80, WHITE, W / 2, 1460, lt, dur * 0.6)
        r4.credit(frame, "Lester Patrick · Photo: public domain")
    else:  # end
        r5.clip_bg(frame, GOALIE, lt, dur)
        frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 110)))
        ra.slam(frame, "COULD YOU", 150, WHITE, W / 2, 900, lt, 0.0)
        ra.slam(frame, "STOP AN NHL SHOT?", 120, ICE, W / 2, 1060, lt, 0.15)
        yes_no(frame, lt)
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
           "-movflags", "+faststart", "reel6_zamboni.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=HERE)
    for i in range(nf):
        t = i / FPS
        k = max(j for j, sg in enumerate(segs) if sg[0] <= t + 1e-6)
        a, b, kind = segs[k]
        lt = t - a
        frame = Image.new("RGBA", (W, H), (5, 10, 25, 255))
        draw(frame, kind, lt, b - a, spans)
        cut_lt = lt
        if kind == "ayres" and lt >= (b - a) * 0.45:
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
        if i == 18:
            frame.convert("RGB").save(os.path.join(HERE, "reel6_thumbnail.jpg"), quality=92)
    proc.stdin.close()
    proc.wait()
    print("fertig: reel6_zamboni.mp4")


if __name__ == "__main__":
    main()
