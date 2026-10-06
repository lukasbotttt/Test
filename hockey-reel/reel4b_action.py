"""Reel 4b: "Forgotten Legends Part 2" – ACTION-Version.

Gleicher Sprecher/Inhalt wie reel4_legends2, aber mit:
- Action-Clip als allererstes Bild (Skater bremst mit Eisspray auf die Kamera zu)
- kurzen Action-Einschüben (Schuss-Nahaufnahme, Stickhandling) in jeder Sprechpause
- Zoom-Schnitt von Ganzkörper auf Gesicht in jeder Spieler-Szene
- Kamera-Wackeln, RGB-Glitch und Blitz bei jedem Schnitt, Text-"Slams"
- Impact-Sounds auf jedem Schnitt, lauterer Beat
Aufruf: python3 reel4b_action.py  ->  reel4b_action.mp4
Clips: Pexels (kostenlose Lizenz) – Tima Miroshnichenko, Ron Lach.
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageChops, ImageDraw

import make_hockey_reel as m
import reel3_cup_day as r3
import reel4_legends2 as r4
from make_hockey_reel import ICE, WHITE, W, H, clamp, ease_out_back, ease_out_cubic, paste_center, text_img

FPS = 30
HERE = m.HERE
SR = 44100
# Gesichtsposition (x, y) relativ zum Foto, für den Zoom-Schnitt
FACES = {"datsyuk.jpg": (0.60, 0.14, 1.9), "forsberg.jpg": (0.63, 0.22, 2.0),
         "selanne.jpg": (0.45, 0.17, 1.5), "bure.jpg": (0.53, 0.12, 1.8)}  # (x, y, Zoom)
# Action-Einschübe: (Clip, Startzeit im Clip)
INSERTS = [("6848067-hd_720_1280_25fps.mp4", 1.0),   # Schläger trifft Puck (Nahaufnahme)
           ("6848071-hd_720_1280_25fps.mp4", 3.0),   # Stickhandling
           ("8970326-hd_1080_2048_25fps.mp4", 7.4),  # Skater bremst
           ("6848067-hd_720_1280_25fps.mp4", 17.0)]  # Schläger/Puck Nahaufnahme
OPENER = ("8970326-hd_1080_2048_25fps.mp4", 6.3)
rnd = random.Random(5)


# ---------------------------------------------------------------- Effekte
def slam(frame, txt, size, color, cx, cy, lt, delay=0.0):
    p = (lt - delay) / 0.14
    if p <= 0:
        return
    sc = 1.0 + 1.2 * (1 - ease_out_cubic(p))  # von groß auf normal "aufschlagen"
    paste_center(frame, text_img(txt, size, color), cx, cy, scale=sc, alpha=clamp(p * 2))


def shake_offset(lt, strength=28, dur=0.28):
    if lt > dur:
        return 0, 0
    k = (1 - lt / dur) ** 2 * strength
    return int(math.sin(lt * 97) * k), int(math.cos(lt * 83) * k)


def apply_shake(frame, dx, dy):
    if dx == 0 and dy == 0:
        return frame
    z = 1.06
    big = frame.resize((int(W * z), int(H * z)), Image.BILINEAR)
    ox = (big.width - W) // 2 + dx
    oy = (big.height - H) // 2 + dy
    return big.crop((ox, oy, ox + W, oy + H))


def glitch(frame, amount):
    r, g, b, a = frame.split()
    r = ImageChops.offset(r, amount, 0)
    b = ImageChops.offset(b, -amount, 0)
    return Image.merge("RGBA", (r, g, b, a))


def face_zoom(frame, name, lt):
    """Nahaufnahme aufs Gesicht (Zoom-Schnitt)."""
    im = Image.open(os.path.join(r4.PHOTOS, name)).convert("RGB")
    fx, fy, z0 = FACES[name]
    z = z0 + 0.15 * lt
    s = max(W / im.width, H / im.height) * z
    big = im.resize((int(im.width * s), int(im.height * s)), Image.BILINEAR)
    cx = int(clamp(fx * big.width - W / 2, 0, big.width - W))
    cy = int(clamp(fy * big.height - H * 0.33, 0, big.height - H))
    frame.paste(big.crop((cx, cy, cx + W, cy + H)), (0, 0))


# ---------------------------------------------------------------- Timeline
def build_segments(spans, total):
    starts = [s[0] for s in spans]
    ends = [s[1] for s in spans]
    segs = [(0.0, 0.6, "opener", None)]
    cut1 = max(ends[0] + 0.1, starts[1] - 0.45)
    segs.append((0.6, cut1, "collage", None))
    for i in range(4):  # Spieler i in Satz i+1
        ins_start = cut1 if i == 0 else max(ends[i] + 0.08, starts[i + 1] - 0.55)
        if i > 0:
            segs.append((prev_end, ins_start, "player", r4.PLAYERS[i - 1]))
        segs.append((ins_start, starts[i + 1] - 0.06, "insert", INSERTS[i]))
        prev_end = starts[i + 1] - 0.06
    vs_start = max(ends[4] + 0.08, starts[5] - 0.3)
    segs.append((prev_end, vs_start, "player", r4.PLAYERS[3]))
    segs.append((vs_start, total, "versus", None))
    return [s for s in segs if s[1] - s[0] > 0.05]


_clip_cache = {}


def clip_frames(name, start, dur):
    key = (name, start, round(dur, 2))
    if key not in _clip_cache:
        _clip_cache[key] = r3.read_clip(name, start, dur)
    return _clip_cache[key]


def draw_segment(frame, kind, data, lt, dur):
    if kind in ("opener", "insert"):
        name, st = OPENER if kind == "opener" else data
        frames = clip_frames(name, st, dur)
        img = Image.fromarray(frames[min(int(lt * FPS), len(frames) - 1)])
        z = 1.15 + 0.25 * lt / dur  # schneller Push-in
        big = img.resize((int(W * z), int(H * z)), Image.BILINEAR)
        ox, oy = (big.width - W) // 2, (big.height - H) // 2
        frame.paste(big.crop((ox, oy, ox + W, oy + H)), (0, 0))
        r4.speed_lines_overlay = None
        if kind == "opener":
            frame.alpha_composite(Image.new("RGBA", (W, H), (5, 10, 25, 70)))
            slam(frame, "FORGOTTEN", 190, WHITE, W / 2, 820, lt, 0.05)
            slam(frame, "LEGENDS", 230, ICE, W / 2, 1040, lt, 0.2)
    elif kind == "collage":
        r4.hook(frame, lt)
    elif kind == "player":
        name, nm, fact, cred, focus = data
        if lt < dur * 0.45:
            r4.place(frame, name, 0, 0, W, H, 1.0 + 0.12 * lt / dur, focus)
        else:
            face_zoom(frame, name, lt - dur * 0.45)
        frame.alpha_composite(r4.SHADE)
        slam(frame, nm, 150, WHITE, W / 2, 1230, lt, 0.0)
        slam(frame, fact, 84, ICE, W / 2, 1380, lt, 0.35)
        r4.credit(frame, cred)
    else:
        versus_action(frame, lt)


BEAT = 60 / 128


def versus_action(frame, lt):
    # Fotos fliegen von links/rechts rein, danach pumpen sie im Beat (abwechselnd links/rechts)
    p = ease_out_cubic(lt / 0.25)
    ph = (lt % BEAT) / BEAT
    bump = 0.06 * math.exp(-ph * 6)
    beat_no = int(lt / BEAT)
    zl = 1.0 + 0.05 * lt + (bump if beat_no % 2 == 0 else 0)
    zr = 1.0 + 0.05 * lt + (bump if beat_no % 2 == 1 else 0)
    tmp = Image.new("RGBA", (W, H), (5, 10, 25, 255))
    r4.place(tmp, r4.PLAYERS[0][0], 0, 0, 540, H, zl, 0.3)
    r4.place(tmp, r4.PLAYERS[1][0], 540, 0, 540, H, zr, 0.3)
    left, right = tmp.crop((0, 0, 540, H)), tmp.crop((540, 0, W, H))
    frame.paste(left, (int(-540 * (1 - p)), 0))
    frame.paste(right, (540 + int(540 * (1 - p)), 0))
    frame.alpha_composite(r4.SHADE)
    d = ImageDraw.Draw(frame)
    glow = 8 + int(4 * math.sin(lt * 10))
    d.line((540, 0, 540, H), fill=ICE, width=glow)
    pulse = 1 + 0.08 * math.sin(lt * 9)
    r = 95 * ease_out_back((lt - 0.2) / 0.25) * pulse
    if r > 5:
        d.ellipse((W / 2 - r, 820 - r, W / 2 + r, 820 + r), fill=(5, 10, 25), outline=ICE, width=8)
        paste_center(frame, text_img("VS", 110, WHITE), W / 2, 823, scale=clamp(r / 95))
    slam(frame, "DATSYUK", 92, ICE, 270, 1110, lt, 0.3)
    slam(frame, "FORSBERG", 92, ICE, 810, 1110, lt, 0.45)
    slam(frame, "WHO'S BETTER?", 140, WHITE, W / 2, 1270, lt, 0.6)
    if lt > 1.0:
        q = ease_out_cubic((lt - 1.0) / 0.3)
        paste_center(frame, text_img("Comment your pick", 60, WHITE, "ExtraBold"), W / 2, 1410 + (1 - q) * 60, alpha=q)
        y = 1480 + abs(math.sin(lt * 6)) * 26
        d.polygon([(W / 2 - 36, y), (W / 2 + 36, y), (W / 2, y + 46)], fill=ICE + (255,))
    r4.credit(frame, "Photos: A. Chernyadyev CC BY-SA 3.0 · H. Dahlström CC BY 2.0")


# ---------------------------------------------------------------- Audio
def mix(voice, cuts, total):
    n = int(total * SR)
    out = np.zeros(n)
    out[: min(n, len(voice))] += voice[:n] * 1.0
    m.SCENES = list(zip(cuts[:-1], cuts[1:]))
    while len(m.SCENES) < 5:
        m.SCENES.append((total + 1, total + 2))
    m.DURATION = total
    m.make_audio(os.path.join(HERE, "beat.wav"))
    with wave.open(os.path.join(HERE, "beat.wav")) as w:
        beat = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    out[: min(n, len(beat))] += beat[:n] * 0.3
    t = np.arange(int(0.45 * SR)) / SR
    rng = np.random.default_rng(4)
    boom = (np.sin(2 * np.pi * (38 + 90 * np.exp(-t * 18)) * t) * np.exp(-t * 7) * 0.55
            + rng.standard_normal(len(t)) * np.exp(-t * 45) * 0.25)
    for c in cuts[1:-1]:
        s = int(c * SR)
        e = min(n, s + len(boom))
        out[s:e] += boom[: e - s]
    out /= max(1.0, np.max(np.abs(out)) * 1.05)
    with wave.open(os.path.join(HERE, "audio_mix.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- Main
def main():
    voice = r3.load_voice()  # r4 hat r3.VOICE auf voice/reel4.mp3 gesetzt
    spans = r4.sentence_spans(r3.speech_segments(voice))
    total = spans[-1][1] + r4.TAIL
    segs = build_segments(spans, total)
    for s in segs:
        print(f"{s[0]:5.2f}-{s[1]:5.2f} {s[2]}")
    cuts = [s[0] for s in segs] + [total]
    mix(voice, cuts, total)

    nf = int(round(total * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", "audio_mix.wav", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", "reel4b_action.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=HERE)
    for i in range(nf):
        t = i / FPS
        k = max(j for j, s in enumerate(segs) if s[0] <= t + 1e-6)
        a, b, kind, data = segs[k]
        lt = t - a
        frame = Image.new("RGBA", (W, H), (5, 10, 25, 255))
        draw_segment(frame, kind, data, lt, b - a)
        # Zoom-Schnitt innerhalb der Spieler-Szene zählt auch als Schnitt
        cut_lt = lt
        if kind == "player" and lt >= (b - a) * 0.45:
            cut_lt = lt - (b - a) * 0.45
        if kind == "versus" and t >= spans[6][0]:
            cut_lt = t - spans[6][0]
        if k > 0 or kind == "opener":
            if cut_lt < 0.07 and t > 0.05:
                frame = glitch(frame, 18)
            if cut_lt < 0.1 and t > 0.05:
                frame.alpha_composite(Image.new("RGBA", (W, H), (220, 245, 255, int(150 * (1 - cut_lt / 0.1)))))
            frame = apply_shake(frame, *shake_offset(cut_lt))
        d = ImageDraw.Draw(frame)
        d.rectangle((0, H - 12, W, H), fill=(0, 0, 0, 140))
        d.rectangle((0, H - 12, int(W * t / total), H), fill=ICE + (255,))
        proc.stdin.write(frame.convert("RGB").tobytes())
        if i == 10:
            frame.convert("RGB").save(os.path.join(HERE, "reel4b_thumbnail.jpg"), quality=92)
    proc.stdin.close()
    proc.wait()
    print("fertig: reel4b_action.mp4")


if __name__ == "__main__":
    main()
