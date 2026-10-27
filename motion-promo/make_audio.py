"""Beat (120 BPM) und alle Soundeffekte für den Motion-Promo synthetisch erzeugen (lizenzfrei, deterministisch).

Ausgabe: audio/music_120bpm.wav + audio/sfx/*.wav (+ stille VO-Platzhalter audio/vo/s1..s4.wav, falls nicht vorhanden).
Aufruf: python3 make_audio.py
"""
import math
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
BPM = 120
BEAT = 60 / BPM
DUR = 15.0
rng = np.random.default_rng(7)


def tt(sec):
    return np.arange(int(sec * SR)) / SR


def lp(x, k):
    c = np.cumsum(np.concatenate([np.zeros(k), x]))
    return (c[k:] - c[:-k]) / k


def hp(x, k):
    return x - lp(x, k)


def noise(sec):
    return rng.standard_normal(int(sec * SR))


def write(path, sig, stereo=None):
    """Mono-Signal (sig) oder fertiges Stereo-Array (stereo) als 16-bit-WAV, auf -1 dBFS normalisiert."""
    sig = np.asarray(stereo if stereo is not None else np.stack([sig, sig], 1), np.float64)
    peak = np.max(np.abs(sig)) + 1e-9
    sig = sig / peak * 0.89
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((sig * 32767).astype(np.int16).tobytes())


# ----------------------------------------------------------------- Bausteine
def kick(vol=1.0):
    x = tt(0.45)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(45 + 170 * np.exp(-x * 30)) / SR) * np.exp(-x * 7) * 3.2) * vol


def clap(vol=1.0):
    x = tt(0.3)
    return hp(noise(0.3), 2) * (np.exp(-x * 26) + 0.5 * np.exp(-np.abs(x - 0.012) * 300)) * 0.8 * vol


def hat(vol=0.1):
    return hp(noise(0.05), 1) * np.exp(-tt(0.05) * 140) * vol


def sub808(freq, dur, vol=0.9):
    x = tt(dur)
    f = freq * (1 + 0.8 * np.exp(-x * 14))
    return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.8) * np.minimum(x / 0.003, 1) * np.exp(-x * 1.2) * vol


def saw_stab(freqs, dur, vol=0.3):
    x = tt(dur)
    s = sum((2 * ((f * x) % 1) - 1) for f in freqs) / len(freqs)
    return lp(s, 6) * np.exp(-x * 9) * vol


def put(buf, sig, at, vol=1.0, pan=0.0):
    st = int(round(at * SR))
    if st >= len(buf):
        return
    e = min(len(buf), st + len(sig))
    gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
    buf[st:e, 0] += sig[: e - st] * vol * gl
    buf[st:e, 1] += sig[: e - st] * vol * gr


# ----------------------------------------------------------------- Musik
def music():
    n = int(DUR * SR)
    buf = np.zeros((n, 2))
    roots = [36.71, 36.71, 32.70, 41.20]          # D1, D1, C1, E1 – je Takt (2 s)
    nb = int(DUR / BEAT)
    for b in range(nb):
        t = b * BEAT
        bar = b // 4
        pos = b % 4
        scene_break = 13 <= b <= 13               # 6,5 s: kurzer Atemzug vor dem Herzschlag
        if not scene_break:
            put(buf, kick(1.0), t)
        if pos in (1, 3):
            put(buf, clap(0.7), t)
        for k in range(4):                        # 16tel-Hats, offbeat lauter
            put(buf, hat(0.11 if k == 2 else 0.05), t + k * BEAT / 4, pan=0.25)
        if pos == 0:
            put(buf, sub808(roots[bar % 4], BEAT * 3.5), t)
        if pos == 0 and bar % 2 == 0:
            put(buf, saw_stab([293.66, 349.23, 440.0], 0.4), t, pan=-0.2)
    return buf


# ----------------------------------------------------------------- SFX
def bass_drop():
    x = tt(1.6)
    body = np.tanh(np.sin(2 * np.pi * np.cumsum(30 + 140 * np.exp(-x * 9)) / SR) * np.exp(-x * 1.8) * 4)
    return body + hp(noise(1.6), 2) * np.exp(-x * 30) * 0.6


def glitch_swoosh():
    x = tt(0.45)
    sw = hp(lp(noise(0.45), 4), 30) * np.sin(np.pi * x / 0.45) ** 2
    gate = (np.sin(2 * np.pi * 38 * x) > -0.2).astype(float)
    bits = np.sign(np.sin(2 * np.pi * (900 + 2600 * x / 0.45) * x)) * gate * np.exp(-x * 5) * 0.35
    return sw + bits


def shutter():
    x = tt(0.25)
    c1 = hp(noise(0.25), 1) * np.exp(-x * 160)
    c2 = np.zeros_like(x)
    k = int(0.07 * SR)
    c2[k:] = hp(noise(0.25), 1)[: len(x) - k] * np.exp(-x[: len(x) - k] * 120) * 0.8
    return c1 + c2 + np.sin(2 * np.pi * 3200 * x) * np.exp(-x * 90) * 0.2


def vinyl_scratch():
    x = tt(0.7)
    pitch = 1 + 0.9 * np.sin(2 * np.pi * 3.2 * x) * np.exp(-x * 1.5)
    src = lp(noise(0.7), 3)
    idx = np.clip(np.cumsum(np.abs(pitch)) / np.max(np.cumsum(np.abs(pitch))) * (len(src) - 1), 0, len(src) - 1).astype(int)
    return hp(src[idx], 8) * np.minimum(x / 0.02, 1) * np.clip((0.7 - x) / 0.2, 0, 1) * 1.4


def heartbeat():
    out = np.zeros(int(1.0 * SR))
    for t0, a in ((0.0, 1.0), (0.28, 0.75)):
        x = tt(0.45)
        th = np.sin(2 * np.pi * np.cumsum(55 + 40 * np.exp(-x * 25)) / SR) * np.exp(-x * 11) * a
        st = int(t0 * SR)
        out[st:st + len(th)] += th
    return np.tanh(out * 2.2)


def whoosh_right():
    x = tt(0.35)
    sig = hp(lp(noise(0.35), 5), 40) * np.sin(np.pi * x / 0.35) ** 2
    l_ = sig * (1 - x / 0.35)
    r_ = sig * (x / 0.35)
    return np.stack([l_, r_], 1)


def riser():
    x = tt(2.0)
    f = 180 + 2600 * (x / 2.0) ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.01) / SR)
    return (hp(noise(2.0), 2) * 0.5 + tone * 0.35) * (x / 2.0) ** 2.4


def laser_zap():
    x = tt(0.5)
    f = 2400 * np.exp(-x * 9) + 160
    return (np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4) * np.exp(-x * 6)


def coin():
    x = tt(0.9)
    a = np.sin(2 * np.pi * 987.8 * x) * (x < 0.08)
    b = np.sin(2 * np.pi * 1318.5 * x) * (x >= 0.08) * np.exp(-(x - 0.08).clip(0) * 5)
    return (np.sign(a) * 0.4 + a * 0.6 + np.sign(b) * 0.3 + b * 0.7) * np.minimum(x / 0.003, 1)


def sub_impact():
    x = tt(1.8)
    body = np.tanh(np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-x * 10)) / SR) * np.exp(-x * 1.6) * 4)
    return body + hp(noise(1.8), 3) * np.exp(-x * 25) * 0.4


def main():
    os.makedirs(os.path.join(HERE, "audio", "sfx"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "audio", "vo"), exist_ok=True)
    write(os.path.join(HERE, "audio", "music_120bpm.wav"), None, stereo=music())
    for name, fn in (("bass_drop", bass_drop), ("glitch_swoosh", glitch_swoosh), ("shutter", shutter),
                     ("vinyl_scratch", vinyl_scratch), ("heartbeat", heartbeat), ("riser", riser),
                     ("laser_zap", laser_zap), ("coin", coin), ("sub_impact", sub_impact)):
        write(os.path.join(HERE, "audio", "sfx", name + ".wav"), fn())
    w = whoosh_right()
    write(os.path.join(HERE, "audio", "sfx", "whoosh_right.wav"), None, stereo=w)
    # stille Platzhalter für die Sprachaufnahmen (werden durch echte Aufnahmen ersetzt)
    for k, d in (("s1", 2.8), ("s2", 3.7), ("s3", 3.9), ("s4", 3.5)):
        p = os.path.join(HERE, "audio", "vo", f"{k}.wav")
        if not os.path.exists(p):
            with wave.open(p, "wb") as wv:
                wv.setnchannels(1)
                wv.setsampwidth(2)
                wv.setframerate(SR)
                wv.writeframes(np.zeros(int(d * SR), np.int16).tobytes())
    print("fertig")


if __name__ == "__main__":
    main()
