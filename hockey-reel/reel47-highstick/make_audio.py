"""Ton für Reel 47 „Why didn't this goal count?“ (hoher Stock): Beat (120 BPM) + SFX synthetisch (lizenzfrei, deterministisch), dazu der Sprecher.

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
DUR = 21.0
rng = np.random.default_rng(47)

# Sprecher-Einsätze (s) und SFX-Zeitpunkte – Frame-Tabelle in SKRIPT.md (SFX nie auf Schlüsselwörtern)
VO_START = {"q": 0.10, "answer": 2.70, "rule": 4.70, "point": 10.70, "twist": 13.20, "cta": 17.70, "drop": 18.70}
SFX = [  # (name, zeit, lautstärke)
    ("bass_drop", 0.0, 0.8), ("horn", 0.0, 0.22),                  # Torlampe brennt …
    ("error", 1.47, 0.45),                                          # … NO GOAL (nach der Frage)
    ("glitch_swoosh", 2.3, 0.5),                                    # Schnitt S1 -> S2 (F75)
    ("crack", 2.6, 0.4),                                            # Puck trifft den hohen Schläger
    ("whoosh_right", 5.75, 0.3),                                    # Torlatten-Linie erscheint
    ("error", 10.05, 0.4),                                          # = NO GOAL (nach "waved off")
    ("whoosh_right", 10.3, 0.55),                                   # Snap S2 -> S3 (F315)
    ("tick", 11.55, 0.3), ("coin", 12.7, 0.35),                     # Kontakt unten -> Tor zählt
    ("slam", 12.97, 0.45),                                          # Blitz-Schnitt S3 -> S4 (F390)
    ("crack", 15.7, 0.4),                                           # Verteidiger schlägt ihn rein
    ("coin", 17.02, 0.38),                                          # IT COUNTS (nach dem Wort)
    ("glitch_swoosh", 17.3, 0.5),                                   # Schnitt S4 -> S5 (F525)
    ("sub_impact", 19.55, 0.75),                                    # YES OR NO? (nach dem Wort)
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






def slam():
    """Schlag für Wort-Slams: Sub-Thump + Rausch-Knall."""
    x = tt(0.7)
    body = np.tanh(np.sin(2 * np.pi * np.cumsum(48 + 120 * np.exp(-x * 22)) / SR) * np.exp(-x * 5) * 3)
    return body + hp(noise(0.7), 2) * np.exp(-x * 40) * 0.7






def whoosh_right():
    x = tt(0.35)
    sig = hp(lp(noise(0.35), 5), 40) * np.sin(np.pi * x / 0.35) ** 2
    return np.stack([sig * (1 - x / 0.35), sig * (x / 0.35)], 1)






def sub_impact():
    x = tt(1.8)
    body = np.tanh(np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-x * 10)) / SR) * np.exp(-x * 1.6) * 4)
    return body + hp(noise(1.8), 3) * np.exp(-x * 25) * 0.4








def tick():
    """Klick (Lampe / Stoppuhr)."""
    x = tt(0.06)
    return (np.sin(2 * np.pi * 2900 * x) * 0.6 + hp(noise(0.06), 1) * 0.5) * np.exp(-x * 220)




def coin():
    x = tt(0.9)
    a = np.sin(2 * np.pi * 987.8 * x) * (x < 0.08)
    b = np.sin(2 * np.pi * 1318.5 * x) * (x >= 0.08) * np.exp(-(x - 0.08).clip(0) * 5)
    return (np.sign(a) * 0.4 + a * 0.6 + np.sign(b) * 0.3 + b * 0.7) * np.minimum(x / 0.003, 1)

def horn():
    """Tor-Horn: tiefer Akkord mit leichtem Vibrato, 0,9 s."""
    x = tt(0.9)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * x)
    s = sum(np.sign(np.sin(2 * np.pi * np.cumsum(f * vib) / SR)) * a for f, a in ((155.6, 0.5), (196.0, 0.35), (233.1, 0.3)))
    return lp(s, 10) * np.minimum(x / 0.04, 1) * np.clip((0.9 - x) / 0.15, 0, 1)




def crack():
    """Schläger-Schlag/Bruch: harter Knack mit kurzem Splittern."""
    x = tt(0.4)
    k = hp(noise(0.4), 1) * np.exp(-x * 60)
    wood = np.sin(2 * np.pi * np.cumsum(420 + 300 * np.exp(-x * 30)) / SR) * np.exp(-x * 25) * 0.7
    return k + wood

def error():
    """Fehler-Ton: zwei tiefe, verzerrte Rechteck-Stöße."""
    x = tt(0.22)
    f = 140 - 40 * x / 0.22
    sq = np.tanh(np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 1.5 + np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR))
    return lp(sq, 3) * np.minimum(x / 0.004, 1) * np.exp(-x * 7)


SFX_FN = {"bass_drop": bass_drop, "glitch_swoosh": glitch_swoosh, "slam": slam, "whoosh_right": whoosh_right,
          "sub_impact": sub_impact, "tick": tick, "coin": coin, "horn": horn, "crack": crack, "error": error}


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
