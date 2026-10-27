"""Ton für Reel 43 „Why only 40 seconds?“: Beat (120 BPM) + SFX synthetisch (lizenzfrei, deterministisch), dazu der Sprecher.

Ausgabe:
  audio/music_120bpm.wav, audio/sfx/*.wav   – Einzelspuren
  audio/mix_vo.wav                          – fertige Mischung mit Sprecher (Musik unter der Stimme abgesenkt)
  audio/mix_novo.wav                        – gleiche Mischung ohne Sprecher (Text-Version)
Vorher: python3 make_vo.py. Aufruf: python3 make_audio.py
"""
import math
import os
import wave

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
BPM = 120
BEAT = 60 / BPM
DUR = 18.5
rng = np.random.default_rng(43)

# Sprecher-Einsätze (s) und SFX-Zeitpunkte – Frame-Tabelle in SKRIPT.md
VO_START = {"q": 0.10, "sprint": 3.60, "mistakes": 8.60, "proof": 10.60, "cta": 15.60}
SFX = [  # (name, zeit, lautstärke)
    ("bass_drop", 0.0, 0.8), ("glitch_swoosh", 0.0, 0.45),
    ("tick", 0.5, 0.35), ("tick", 1.0, 0.35), ("tick", 1.5, 0.35), ("tick", 2.0, 0.35),
    ("tick", 2.25, 0.3), ("tick", 2.5, 0.4), ("tick", 2.625, 0.3), ("tick", 2.75, 0.4), ("tick", 2.875, 0.3),
    ("buzzer", 2.67, 0.5),                                          # Uhr springt auf 00:40
    ("glitch_swoosh", 3.3, 0.55),                                   # Schnitt S1 -> S2 (F105)
    ("slam", 5.0, 0.7),                                             # SPRINT
    ("riser", 6.0, 0.4),                                            # 30–40 SEC … voller Sprint
    ("heartbeat", 7.95, 0.85), ("heartbeat", 8.45, 0.6),            # EXHAUSTED
    ("error", 8.5, 0.5),                                            # roter Schnitt S2 -> S3 (F255)
    ("error", 9.73, 0.45), ("error", 10.0, 0.45), ("error", 10.27, 0.45),  # MISTAKES PILE UP
    ("whoosh_right", 10.38, 0.6),                                   # Snap S3 -> S4 (F315)
    ("slam", 12.3, 0.5),                                            # 44
    ("coin", 13.0, 0.45),                                           # 41
    ("slam", 14.55, 0.7),                                           # FEWER GOALS ALLOWED
    ("glitch_swoosh", 15.3, 0.55),                                  # Schnitt S4 -> S5 (F465)
    ("sub_impact", 17.5, 0.85),                                     # DROP A NUMBER
]


def tt(sec):
    return np.arange(int(sec * SR)) / SR


def lp(x, k):
    c = np.cumsum(np.concatenate([np.zeros(k), x]))
    return (c[k:] - c[:-k]) / k


def hp(x, k):
    return x - lp(x, k)


def noise(sec):
    return rng.standard_normal(int(sec * SR))


def to_stereo(sig):
    sig = np.asarray(sig, np.float64)
    return sig if sig.ndim == 2 else np.stack([sig, sig], 1)


def write(path, sig, peak=0.89):
    """Mono- oder Stereo-Signal als 16-bit-Stereo-WAV, auf `peak` normalisiert."""
    sig = to_stereo(sig)
    sig = sig / (np.max(np.abs(sig)) + 1e-9) * peak
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
    sig = np.asarray(sig)
    st = int(round(at * SR))
    if st >= len(buf):
        return
    e = min(len(buf), st + len(sig))
    if sig.ndim == 2:
        buf[st:e] += sig[: e - st] * vol
        return
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
        breath = b in (16, 17)                    # 8,0–9,0 s: Atemzug bei EXHAUSTED (nur Herzschlag)
        if not breath:
            put(buf, kick(1.0), t)
            if pos in (1, 3):
                put(buf, clap(0.7), t)
            for k in range(4):                    # 16tel-Hats, offbeat lauter
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


def tick():
    """Stoppuhr-Klick: kurzer, heller Holz-/Metall-Klick."""
    x = tt(0.06)
    return (np.sin(2 * np.pi * 2900 * x) * 0.6 + hp(noise(0.06), 1) * 0.5) * np.exp(-x * 220)


def buzzer():
    """Kurzer Zeit-um-Ton (Rechteck, 0,35 s)."""
    x = tt(0.35)
    sq = np.sign(np.sin(2 * np.pi * 220 * x)) * 0.5 + np.sign(np.sin(2 * np.pi * 330 * x)) * 0.3
    return lp(sq, 4) * np.minimum(x / 0.005, 1) * np.clip((0.35 - x) / 0.05, 0, 1)


def slam():
    """Schlag für Wort-Slams: Sub-Thump + Rausch-Knall."""
    x = tt(0.7)
    body = np.tanh(np.sin(2 * np.pi * np.cumsum(48 + 120 * np.exp(-x * 22)) / SR) * np.exp(-x * 5) * 3)
    return body + hp(noise(0.7), 2) * np.exp(-x * 40) * 0.7


def heartbeat():
    out = np.zeros(int(1.0 * SR))
    for t0, a in ((0.0, 1.0), (0.28, 0.75)):
        x = tt(0.45)
        th = np.sin(2 * np.pi * np.cumsum(55 + 40 * np.exp(-x * 25)) / SR) * np.exp(-x * 11) * a
        st = int(t0 * SR)
        out[st:st + len(th)] += th
    return np.tanh(out * 2.2)


def error():
    """Fehler-Ton: zwei tiefe, verzerrte Rechteck-Stöße."""
    x = tt(0.22)
    f = 140 - 40 * x / 0.22
    sq = np.tanh(np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 1.5 + np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR))
    return lp(sq, 3) * np.minimum(x / 0.004, 1) * np.exp(-x * 7)


def whoosh_right():
    x = tt(0.35)
    sig = hp(lp(noise(0.35), 5), 40) * np.sin(np.pi * x / 0.35) ** 2
    return np.stack([sig * (1 - x / 0.35), sig * (x / 0.35)], 1)


def riser():
    x = tt(2.0)
    f = 180 + 2600 * (x / 2.0) ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.01) / SR)
    return (hp(noise(2.0), 2) * 0.5 + tone * 0.35) * (x / 2.0) ** 2.4


def coin():
    x = tt(0.9)
    a = np.sin(2 * np.pi * 987.8 * x) * (x < 0.08)
    b = np.sin(2 * np.pi * 1318.5 * x) * (x >= 0.08) * np.exp(-(x - 0.08).clip(0) * 5)
    return (np.sign(a) * 0.4 + a * 0.6 + np.sign(b) * 0.3 + b * 0.7) * np.minimum(x / 0.003, 1)


def sub_impact():
    x = tt(1.8)
    body = np.tanh(np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-x * 10)) / SR) * np.exp(-x * 1.6) * 4)
    return body + hp(noise(1.8), 3) * np.exp(-x * 25) * 0.4


SFX_FN = {"bass_drop": bass_drop, "glitch_swoosh": glitch_swoosh, "tick": tick, "buzzer": buzzer, "slam": slam,
          "heartbeat": heartbeat, "error": error, "whoosh_right": whoosh_right, "riser": riser, "coin": coin,
          "sub_impact": sub_impact}


# ----------------------------------------------------------------- Mischung
def norm(sig, peak=0.89):
    return to_stereo(sig) / (np.max(np.abs(sig)) + 1e-9) * peak


def voice_track():
    buf = np.zeros((int(DUR * SR), 2))
    for key, t0 in VO_START.items():
        a, sr = sf.read(os.path.join(HERE, "audio", "vo", f"vo_{key}.wav"), dtype="float64")
        if a.ndim == 2:
            a = a.mean(1)
        if sr != SR:                                   # Kokoro liefert 24 kHz -> linear auf 48 kHz
            a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a)
        put(buf, a, t0, 1.0)
    return buf


def duck_curve(vo):
    """Musik unter der Stimme absenken: Hüllkurve (Attack 30 ms, Release 300 ms) -> Gain 1 … 0,32."""
    env = (np.abs(vo).max(1) > 0.02).astype(float)
    k = int(0.3 * SR)
    hold = np.convolve(env, np.ones(k), "same") > 0          # kurze Pausen überbrücken
    g = np.where(hold, 0.32, 1.0)
    return lp(lp(g, int(0.03 * SR)), int(0.03 * SR))[: len(g)]


def main():
    os.makedirs(os.path.join(HERE, "audio", "sfx"), exist_ok=True)
    mus = music()
    write(os.path.join(HERE, "audio", "music_120bpm.wav"), mus)
    sfx_bus = np.zeros((int(DUR * SR), 2))
    for name, fn in SFX_FN.items():
        write(os.path.join(HERE, "audio", "sfx", name + ".wav"), fn())
    for name, t0, vol in SFX:
        put(sfx_bus, norm(SFX_FN[name]()), t0, vol)

    mus_n = norm(mus) * 0.55
    vo = voice_track()
    g = duck_curve(vo)
    with_vo = mus_n * g[:, None] + sfx_bus * (0.55 + 0.45 * g[:, None]) + norm(vo) * 0.95
    without = mus_n * 1.0 + sfx_bus
    write(os.path.join(HERE, "audio", "mix_vo.wav"), with_vo, 0.95)
    write(os.path.join(HERE, "audio", "mix_novo.wav"), without, 0.95)
    print("fertig")


if __name__ == "__main__":
    main()
