"""Reel (1080x1920, 30 fps) zum Bouncy-Instrumental: Build -> Drop -> abrupter Stopp mit Endkarte.

Audio-reaktiv: echtes Spektrum aus dem Mix, Kick-Punch, Shake, Strobe, Laser.
Voraussetzung: newyork_bouncy.py wurde ausgeführt (newyork_bouncy.wav liegt daneben).
Aufruf: python3 reel_bouncy.py  ->  reel_bouncy.mp4 (+ reel_bouncy_cover.jpg)
"""
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ANTON = str(HERE.parent.parent / "hockey-reel" / "fonts" / "Anton.ttf")
INTER = "/usr/share/fonts/opentype/inter/Inter-{}.otf"
W, H, FPS = 1080, 1920, 30
BPM = 175
BEAT = 60 / BPM
BAR = 4 * BEAT
T0 = 14 * BAR            # Ausschnitt startet 2 Takte vor dem Drop
DROP = 2 * BAR           # Drop-Zeitpunkt im Reel
DROP_END = DROP + 8 * BAR
END = DROP_END + 1.6     # Endkarte in Stille
RED = np.array([229, 37, 47], np.float32)
WHITE = np.array([244, 241, 236], np.float32)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


# ---------------------------------------------------------------- Audio
def load_audio():
    with wave.open(str(HERE / "newyork_bouncy.wav")) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    seg = x[int(T0 * sr):int((T0 + DROP_END) * sr)]
    fade = int(0.006 * sr)  # harter Schnitt ohne Knackser
    seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
    seg = np.concatenate([seg, np.zeros((int((END - DROP_END) * sr), 2), np.float32)])
    return seg, sr


def spectra(mono, sr, nb=28):
    n = 2048
    edges = np.geomspace(40, 12000, nb + 1)
    fr = np.fft.rfftfreq(n, 1 / sr)
    idx = [(np.searchsorted(fr, edges[i]), max(np.searchsorted(fr, edges[i + 1]), np.searchsorted(fr, edges[i]) + 1))
           for i in range(nb)]
    out, prev = [], np.zeros(nb)
    win = np.hanning(n)
    for f in range(int(END * FPS)):
        c = int(f / FPS * sr)
        s = mono[max(c - n // 2, 0):max(c - n // 2, 0) + n]
        if len(s) < n:
            s = np.pad(s, (0, n - len(s)))
        mag = np.abs(np.fft.rfft(s * win))
        b = np.array([mag[a:e].mean() for a, e in idx])
        b = np.clip((20 * np.log10(b + 1e-6) + 10) / 50, 0, 1)
        prev = np.maximum(b, prev * 0.78)
        out.append(prev.copy())
    return out


# ---------------------------------------------------------------- Grafik-Helfer
_fonts = {}


def font(path, size):
    if (path, size) not in _fonts:
        _fonts[(path, size)] = ImageFont.truetype(path, size)
    return _fonts[(path, size)]


def text(img, s, cx, cy, size, fnt=ANTON, color=WHITE, alpha=1.0, scale=1.0, track=0, glow=0):
    if alpha <= 0.01:
        return
    size = max(int(size * scale), 8)
    f = font(fnt, size)
    widths = [f.getlength(ch) for ch in s]
    tw = sum(widths) + track * (len(s) - 1)
    pad = 30 + glow * 3
    layer = Image.new("L", (int(tw) + pad * 2, int(size * 1.5) + pad * 2), 0)
    d = ImageDraw.Draw(layer)
    x = pad
    for ch, wc in zip(s, widths):
        d.text((x, layer.height / 2), ch, font=f, fill=255, anchor="lm")
        x += wc + track
    a = np.asarray(layer, np.float32) / 255 * alpha
    ox, oy = int(cx - layer.width / 2), int(cy - layer.height / 2)
    x0, y0 = max(ox, 0), max(oy, 0)
    x1, y1 = min(ox + layer.width, W), min(oy + layer.height, H)
    if x1 <= x0 or y1 <= y0:
        return
    sl = (slice(y0 - oy, y1 - oy), slice(x0 - ox, x1 - ox))
    reg = img[y0:y1, x0:x1]
    if glow:
        g = np.asarray(layer.filter(ImageFilter.GaussianBlur(glow)), np.float32)[sl] / 255 * alpha
        reg += g[..., None] * RED * 0.9
    aa = a[sl][..., None]
    reg[:] = reg * (1 - aa) + np.asarray(color, np.float32) * aa


_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_R = np.sqrt((_xx - W / 2) ** 2 + (_yy - H * 0.47) ** 2)
_VIGN = np.clip(1 - 0.6 * ((_xx - W / 2) ** 2 / (W * 0.75) ** 2 + (_yy - H / 2) ** 2 / (H * 0.6) ** 2), 0.2, 1)[..., None]
_rng = np.random.default_rng(4)
_GRAIN = [_rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(5)]


def kick_env(t):
    """Hüllkurve der Kick (nur im Build-Ende und Drop)."""
    if t < 0 or t >= DROP_END:
        return 0.0
    k = (t % BEAT)
    if t < DROP:
        return 0.35 * math.exp(-k / 0.10)
    return math.exp(-k / 0.11)


def bounce_env(t):
    if t < DROP or t >= DROP_END:
        return 0.0
    k = (t - BEAT / 2) % BEAT
    return math.exp(-k / 0.08)


def lasers(img, t, strength):
    if strength <= 0.02:
        return
    layer = Image.new("L", (W // 2, H // 2), 0)
    d = ImageDraw.Draw(layer)
    ox, oy = W // 4, -20
    for i in range(7):
        a = math.radians(60 + i * 10 + 18 * math.sin(t * 1.7 + i * 0.6))
        x1, y1 = ox + math.cos(a) * 1400, oy + math.sin(a) * 1400
        d.line([(ox, oy), (x1, y1)], fill=int(255 * strength), width=2)
    up = np.asarray(layer.filter(ImageFilter.GaussianBlur(2)).resize((W, H), Image.BILINEAR), np.float32) / 255
    img += up[..., None] * RED * 0.9


def bars(img, spec, strength, y_base):
    nb = len(spec)
    bw = W / (nb * 2)
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    vals = np.concatenate([spec[::-1], spec])
    for i, v in enumerate(vals):
        h = 10 + v * 520 * strength
        x0 = i * bw + 3
        d.rectangle([x0, y_base - h, x0 + bw - 6, y_base], fill=255)
        d.rectangle([x0, y_base + 8, x0 + bw - 6, y_base + 8 + h * 0.35], fill=70)
    a = np.asarray(layer, np.float32) / 255
    glow = np.asarray(layer.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255
    img[:] = img * (1 - a[..., None] * 0.85) + a[..., None] * RED * 0.85
    img += glow[..., None] * RED * 0.5


# ---------------------------------------------------------------- Frame
def render(i, spec):
    t = i / FPS
    ke, be = kick_env(t), bounce_env(t)
    drop = DROP <= t < DROP_END
    img = np.zeros((H, W, 3), np.float32) + np.array([10, 9, 13], np.float32)

    if t < DROP_END:
        # roter Glow aus der Mitte, pumpt mit Kick und Bounce
        build = clamp(t / DROP)
        g = (0.25 + 0.5 * build) if not drop else (0.45 + 0.55 * ke + 0.25 * be)
        img += np.exp(-(_R / (520 + 160 * ke)) ** 2)[..., None] * RED * g
        lasers(img, t, (0.15 * build if not drop else 0.55 + 0.4 * be))
        bars(img, spec[i], 0.45 + 0.55 * build if not drop else 1.0, 1580)

        if not drop:
            # Hook + Countdown auf den letzten drei Schlägen
            al = clamp(t / 0.25)
            text(img, "WIE HART IST", W / 2, 640, 120, INTER.format("Bold"), alpha=al, scale=0.62, track=10)
            text(img, "DIESER DROP?", W / 2, 780, 170, alpha=al, glow=14)
            beat_i = int(t / BEAT)
            if beat_i >= 5:
                n = 8 - beat_i
                if 1 <= n <= 3:
                    ph = (t % BEAT) / BEAT
                    text(img, str(n), W / 2, 1120, 260, alpha=1 - ph * 0.6, scale=1.3 - 0.3 * ease_out(ph * 2))
        else:
            punch = 1 + 0.10 * ke
            text(img, "175", W / 2, 840, 420, scale=punch, glow=24)
            text(img, "BPM", W / 2, 1135, 70, INTER.format("Bold"), WHITE, track=40, scale=1 + 0.04 * be)
            text(img, "BOUNCY HARDCORE", W / 2, 1230, 40, INTER.format("SemiBold"), WHITE, 0.85, track=14)
            # Strobe auf jedem vierten Schlag
            if int((t - DROP) / BEAT) % 4 == 0 and (t - DROP) % BEAT < 0.05:
                img += 120
        text(img, "TAG 26/365", W - 160, 140, 34, INTER.format("Bold"), WHITE, 0.9, track=4)
        # Shake
        if drop:
            dx, dy = int(14 * ke * math.sin(t * 91)), int(14 * ke * math.cos(t * 77))
            img = np.roll(img, (dy, dx), axis=(0, 1))
    else:
        # Endkarte nach abruptem Stopp
        tl = t - DROP_END
        text(img, "1 – 10 ?", W / 2, 820, 230, alpha=clamp(tl / 0.15), scale=1.15 - 0.15 * ease_out(tl / 0.3),
             glow=16)
        text(img, "SCHREIB'S IN DIE KOMMENTARE", W / 2, 1060, 44, INTER.format("SemiBold"), WHITE,
             clamp((tl - 0.2) / 0.3), track=6)
        text(img, "@marlodeee", W / 2, 1180, 46, INTER.format("Bold"), RED, clamp((tl - 0.45) / 0.3), track=3)

    img *= _VIGN
    gr = _GRAIN[i % len(_GRAIN)]
    img += np.repeat(np.repeat(gr, 2, 0), 2, 1)[..., None] * 6
    return np.clip(img, 0, 255).astype(np.uint8)


def main():
    audio, sr = load_audio()
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    apath = HERE / "reel_audio.wav"
    with wave.open(str(apath), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    spec = spectra(audio.mean(1), sr)
    out = HERE / "reel_bouncy.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(apath),
           "-c:v", "libx264", "-preset", "medium", "-crf", "25", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(END * FPS)
    for i in range(n):
        proc.stdin.write(render(i, spec).tobytes())
    proc.stdin.close()
    proc.wait()
    Image.fromarray(render(int((DROP + 0.02) * FPS), spec)).save(HERE / "reel_bouncy_cover.jpg", quality=92)
    print("fertig:", out, f"({END:.1f} s)")


if __name__ == "__main__":
    main()
