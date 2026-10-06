"""Reel 3: "A day with the Stanley Cup" – echte Clips + Sprecher + Wort-für-Wort-Untertitel.

Aufruf: python3 reel3_cup_day.py  ->  reel3_cup_day.mp4
Benötigt: clips/*.mp4 (Pexels, kostenlose Lizenz), voice/reel3.mp3 (vidIQ-Voiceover).
Fakten: Jeder Spieler des Siegerteams bekommt einen Tag mit dem Stanley Cup; Spieler haben
Müsli daraus gegessen; Sylvain Lefebvre ließ 1996 seine Tochter darin taufen.
"""
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw

import make_hockey_reel as m
from make_hockey_reel import ICE, WHITE, W, H, clamp, ease_out_back, ease_out_cubic, paste_center, text_img

FPS = 30
HERE = m.HERE
VOICE = os.path.join(HERE, "voice", "reel3.mp3")
CLIPS = os.path.join(HERE, "clips")
SENTENCES = [
    "Every player who wins the Stanley Cup gets one full day with it.",
    "Guys have eaten cereal out of it.",
    "One player even baptized his daughter in it.",
    "So what would YOU do with it?",
]
# Clip pro Satz: (Datei, Startzeit im Clip)
SHOTS = [("6848153-hd_1080_1920_25fps.mp4", 0.8),
         ("6848143-hd_1080_1920_25fps.mp4", 2.4),
         ("6848153-hd_1080_1920_25fps.mp4", 8.6),
         ("8970326-hd_1080_2048_25fps.mp4", 4.6)]
TAIL = 1.6  # Sekunden nach dem letzten Wort (Frage bleibt stehen)
SR = 44100


# ---------------------------------------------------------------- Audio / Timing
def load_voice():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", VOICE, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def speech_segments(v):
    """Findet Sprechabschnitte (getrennt durch Pausen) über die Lautstärke in 10-ms-Fenstern."""
    win = SR // 100
    n = len(v) // win
    rms = np.sqrt((v[: n * win].reshape(n, win) ** 2).mean(1))
    on = rms > max(0.02, rms.max() * 0.08)
    segs, start, quiet = [], None, 0
    for i, s in enumerate(on):
        if s:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet >= 18:  # 180 ms Pause = Satzende
                segs.append((start / 100, (i - quiet + 1) / 100))
                start, quiet = None, 0
    if start is not None:
        segs.append((start / 100, n / 100))
    return segs


def word_timings(segs):
    """Gruppiert Sprechabschnitte zu Sätzen (größte Pausen = Satzgrenzen) und verteilt die Wörter
    proportional zur Buchstabenzahl auf die reine Sprechzeit des Satzes."""
    n = len(SENTENCES)
    gaps = sorted(range(len(segs) - 1), key=lambda i: segs[i + 1][0] - segs[i][1], reverse=True)
    cuts = sorted(gaps[: n - 1])
    groups, prev = [], 0
    for c in cuts + [len(segs) - 1]:
        groups.append(segs[prev:c + 1])
        prev = c + 1
    words = []
    for si, (sent, parts) in enumerate(zip(SENTENCES, groups)):
        speech = sum(b - a for a, b in parts)

        def to_time(x):  # x = Anteil der Sprechzeit -> echte Zeit (Pausen überspringen)
            rest = x * speech
            for a, b in parts:
                if rest <= b - a:
                    return a + rest
                rest -= b - a
            return parts[-1][1]

        toks = sent.split()
        weights = [len(t) + 2 for t in toks]
        acc = 0
        for tok, wgt in zip(toks, weights):
            a = to_time(acc / sum(weights))
            acc += wgt
            words.append((si, tok, a, to_time(acc / sum(weights))))
    return [(g[0][0], g[-1][1]) for g in groups], words


# ---------------------------------------------------------------- Video
def read_clip(name, start, dur):
    """Liest dur Sekunden ab start, skaliert/croppt auf 1080x1920, 30 fps."""
    vf = f"fps={FPS},scale={W}:-2,crop={W}:{H},eq=contrast=1.08:saturation=1.15"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", f"{dur + 0.2:.2f}",
                          "-i", os.path.join(CLIPS, name), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W, 3)
    need = int(round(dur * FPS))
    if len(frames) < need:  # zur Not letztes Bild halten
        frames = np.concatenate([frames, np.repeat(frames[-1:], need - len(frames), 0)])
    return frames[:need]


def shade_overlay():
    """Abdunklung oben und in der Mitte, damit Text auf hellem Eis lesbar bleibt."""
    y = np.linspace(0, 1, H)[:, None]
    a = 0.55 * np.clip(1 - y / 0.35, 0, 1) + 0.38 * np.exp(-((y - 0.6) / 0.16) ** 2) + 0.15
    a = np.repeat(np.clip(a, 0, 0.8), W, 1)
    ov = Image.new("RGBA", (W, H), (5, 10, 25, 0))
    ov.putalpha(Image.fromarray((a * 255).astype(np.uint8)))
    return ov


SHADE = shade_overlay()


def caption(frame, words, t):
    """Zeigt 2–3 Wörter rund um das aktuelle Wort; aktuelles Wort in ICE mit Pop."""
    cur = None
    for i, (si, tok, a, b) in enumerate(words):
        if a <= t < b + 0.12:
            cur = i
    if cur is None:
        return
    si = words[cur][0]
    same = [i for i, w in enumerate(words) if w[0] == si]
    pos = same.index(cur)
    start = (pos // 3) * 3
    group = same[start:start + 3]
    toks = [words[i][1].upper().strip(".,?") if words[i][1] != "YOU" else "YOU" for i in group]
    size = 118
    imgs = [text_img(tk, size, ICE if gi == cur else WHITE) for tk, gi in zip(toks, group)]
    total = sum(im.width for im in imgs) - 60 * (len(imgs) - 1)
    while total > 1010 and size > 70:
        size -= 8
        imgs = [text_img(tk, size, ICE if gi == cur else WHITE) for tk, gi in zip(toks, group)]
        total = sum(im.width for im in imgs) - 60 * (len(imgs) - 1)
    x = W / 2 - total / 2
    for im, gi in zip(imgs, group):
        sc = 1.0
        if gi == cur:
            sc = 0.85 + 0.15 * ease_out_back((t - words[gi][2]) / 0.15)
        paste_center(frame, im, x + im.width / 2, 1150, scale=sc)
        x += im.width - 60


def render(words, segs, total):
    # Szenengrenzen: jeder Satz beginnt mit neuem Clip (leicht vor dem Satz)
    bounds = [0.0] + [max(0.0, s[0] - 0.08) for s in segs[1:]] + [total]
    shots = []
    for (name, st), a, b in zip(SHOTS, bounds[:-1], bounds[1:]):
        shots.append((a, b, read_clip(name, st, b - a)))
    nf = int(round(total * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", "audio_mix.wav", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", "reel3_cup_day.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=HERE)
    q_start = segs[-1][0]
    for i in range(nf):
        t = i / FPS
        k = max(j for j, (a, _, _) in enumerate(shots) if a <= t + 1e-6)
        a, b, frames = shots[k]
        lt = t - a
        arr = frames[min(int(lt * FPS), len(frames) - 1)]
        img = Image.fromarray(arr)
        z = 1.0 + 0.05 * (lt / max(b - a, 0.1))  # langsamer Push-in
        if lt < 0.12 and k > 0:
            z += 0.08 * (1 - lt / 0.12)  # Zoom-Punch beim Schnitt
        if z > 1.001:
            big = img.resize((int(W * z), int(H * z)), Image.BILINEAR)
            ox, oy = (big.width - W) // 2, (big.height - H) // 2
            img = big.crop((ox, oy, ox + W, oy + H))
        frame = img.convert("RGBA")
        frame.alpha_composite(SHADE)

        # Hook-Titel oben (die ersten Sekunden)
        if t < segs[0][1] + 0.3:
            p = ease_out_back(t / 0.3)
            paste_center(frame, text_img("THE STANLEY CUP", 120, WHITE), W / 2, 380, scale=p)
            paste_center(frame, text_img("RULE NOBODY KNOWS", 104, ICE), W / 2, 510, scale=ease_out_back((t - 0.15) / 0.3))
        if t >= q_start:  # Frage als Abschluss
            lt2 = t - q_start
            paste_center(frame, text_img("WHAT WOULD", 150, WHITE), W / 2, 400, scale=ease_out_back(lt2 / 0.3))
            paste_center(frame, text_img("YOU DO?", 190, ICE), W / 2, 570,
                         scale=ease_out_back((lt2 - 0.15) / 0.3), angle=math.sin(t * 5) * 1.5)
            if t > segs[-1][1]:
                lt3 = t - segs[-1][1]
                paste_center(frame, text_img("Comment below", 62, WHITE, "ExtraBold"), W / 2,
                             1300 + (1 - ease_out_cubic(lt3 / 0.3)) * 80, alpha=clamp(lt3 / 0.3))
                d = ImageDraw.Draw(frame)
                y = 1380 + abs(math.sin(t * 6)) * 28
                d.polygon([(W / 2 - 38, y), (W / 2 + 38, y), (W / 2, y + 48)], fill=ICE + (255,))
        if t < segs[-1][1] + 0.1 and t < q_start or (q_start <= t < segs[-1][1] + 0.1):
            caption(frame, words, t)
        d = ImageDraw.Draw(frame)
        d.rectangle((0, H - 12, W, H), fill=(0, 0, 0, 140))
        d.rectangle((0, H - 12, int(W * t / total), H), fill=ICE + (255,))
        proc.stdin.write(frame.convert("RGB").tobytes())
        if i == int(1.2 * FPS):
            frame.convert("RGB").save(os.path.join(HERE, "reel3_thumbnail.jpg"), quality=92)
    proc.stdin.close()
    proc.wait()
    return bounds


def mix_audio(voice, bounds, total):
    n = int(total * SR)
    out = np.zeros(n)
    out[: min(n, len(voice))] += voice[:n] * 1.0
    # leiser Beat aus dem Basis-Reel
    # Schnitte als "Szenen" für Whoosh-Zeitpunkte; 5. Szene hinter dem Ende (keine Torhupe)
    m.SCENES = list(zip(bounds[:-1], bounds[1:])) + [(total + 1, total + 2)]
    m.DURATION = total
    m.make_audio(os.path.join(HERE, "beat.wav"))
    with wave.open(os.path.join(HERE, "beat.wav")) as w:
        beat = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    out[: min(n, len(beat))] += beat[:n] * 0.22
    out /= max(1.0, np.max(np.abs(out)) * 1.05)
    with wave.open(os.path.join(HERE, "audio_mix.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def main():
    voice = load_voice()
    segs, words = word_timings(speech_segments(voice))
    total = segs[-1][1] + TAIL
    print("Sätze:", [(round(a, 2), round(b, 2)) for a, b in segs], "Länge:", round(total, 2))
    bounds = [0.0] + [max(0.0, s[0] - 0.08) for s in segs[1:]] + [total]
    mix_audio(voice, bounds, total)
    render(words, segs, total)
    print("fertig: reel3_cup_day.mp4")


if __name__ == "__main__":
    main()
