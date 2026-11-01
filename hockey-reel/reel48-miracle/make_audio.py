"""Filmscore + Sounddesign für Reel 48 „Miracle on Ice“ (Kino-Trailer), komplett synthetisch (lizenzfrei, deterministisch).

Bausteine: Drone, Supersaw-Flächen (Streicher/Chor-artig), Trailer-„Braam“, Taiko, Uhr-Ticken, Puls-Ostinato, Herzschlag,
Riser, Klavier, Glocken, Publikum, Arena-Horn, Becken, Sub-Boom – mit Faltungshall auf dem Musik-Bus.
Dramaturgie: Moll (D) bis zum Ausgleich, völlige Stille vor „Mike Eruzione“, Dur nach dem 4:3, Countdown, Horn, Titel.

Ausgabe: audio/mix_vo.wav (fertige Mischung mit Sprecher), audio/mix_novo.wav, audio/score.wav
Vorher: python3 make_vo.py. Aufruf: python3 make_audio.py
"""
import os
import wave

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
DUR = 44.0
rng = np.random.default_rng(48)

# Sprecher-Einsätze (s) – müssen zu index.html / SKRIPT.md passen
VO_START = {"lost": 0.30, "again": 2.30, "soviet": 5.00, "kids": 8.90, "placid": 11.30,
            "d1": 15.70, "d2": 17.30, "d3": 18.80, "tie": 20.40, "ten": 21.80, "mike": 25.00, "hold": 26.90,
            "c5": 29.60, "c4": 30.35, "c3": 31.10, "c2": 31.85, "c1": 32.60,
            "title": 33.90, "gold": 36.50, "cta": 39.60, "drop": 41.60}
T_SILENCE = 24.55          # alles bricht weg …
T_GOAL = 26.25             # … Einschlag 4:3
T_HORN = 33.30             # Schlusssirene
FLIPS = [15.62, 17.22, 18.72, 20.32]   # Anzeigetafel-Wechsel (kurz vor der jeweiligen Zeile)
MEDALS = [6.45, 6.80, 7.15, 7.50]


# ----------------------------------------------------------------- Grundlagen
def tt(sec):
    return np.arange(int(sec * SR)) / SR


def noise(sec):
    return rng.standard_normal(int(sec * SR))


def filt(x, kind, f, order=2):
    sos = butter(order, f, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def env(n, a, r, total=None):
    """Hüllkurve: Attack a s, Release r s (am Ende)."""
    x = np.arange(n) / SR
    d = n / SR if total is None else total
    return np.clip(x / max(a, 1e-4), 0, 1) * np.clip((d - x) / max(r, 1e-4), 0, 1)


def saw(f, x, phase=0.0):
    return 2 * ((f * x + phase) % 1) - 1


def put(buf, sig, at, vol=1.0, pan=0.0):
    sig = np.asarray(sig, np.float64)
    st = int(round(at * SR))
    if st >= len(buf):
        return
    e = min(len(buf), st + len(sig))
    if sig.ndim == 2:
        buf[st:e] += sig[: e - st] * vol
        return
    gl, gr = np.cos((pan + 1) * np.pi / 4) * 1.41, np.sin((pan + 1) * np.pi / 4) * 1.41
    buf[st:e, 0] += sig[: e - st] * vol * gl
    buf[st:e, 1] += sig[: e - st] * vol * gr


def nt(name):
    """Notenname -> Hz (A4 = 440)."""
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    n, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o - 4)) / 12)


# ----------------------------------------------------------------- Instrumente
def supersaw(freqs, dur, cutoff=1800, a=1.2, r=1.5, detune=0.004, voices=5):
    x = tt(dur)
    sig = np.zeros_like(x)
    for f in freqs:
        for v in range(voices):
            d = 1 + detune * (v - (voices - 1) / 2) / ((voices - 1) / 2)
            sig += saw(f * d, x, rng.random())
    sig /= len(freqs) * voices
    sig = filt(sig, "low", cutoff, 2)
    return sig * env(len(x), a, r)


def choir(freqs, dur, a=1.0, r=1.6):
    """Chor-artige Fläche: Supersaw durch zwei Formant-Bänder („aah“)."""
    base = supersaw(freqs, dur, cutoff=4000, a=a, r=r, detune=0.006, voices=4)
    f1 = filt(base, "band", [600, 1000], 2)
    f2 = filt(base, "band", [1100, 1500], 2) * 0.6
    return (f1 + f2) * 2.2


def drone(dur, root=nt("D1"), vol=1.0, a=2.0, r=2.0):
    x = tt(dur)
    sig = (np.sin(2 * np.pi * root * x) + 0.6 * np.sin(2 * np.pi * root * 1.5 * x + 0.3) +
           0.35 * saw(root * 2, x) * 0.5)
    sig = filt(sig, "low", 260, 2)
    lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.12 * x)
    return sig * lfo * env(len(x), a, r) * vol


def braam(root=nt("D1"), dur=3.2, major=False):
    """Trailer-„Braam“: verzerrte Blechbläser-Wand, Filter öffnet sich und schließt langsam."""
    x = tt(dur)
    third = root * (2 ** (4 / 12) if major else 2 ** (3 / 12)) * 2
    parts = [(root, 1.0), (root * 1.5, 0.8), (root * 2, 0.9), (third, 0.45), (root * 3, 0.35)]
    sig = sum(saw(f, x, rng.random()) * g + saw(f * 1.004, x, rng.random()) * g * 0.7 for f, g in parts)
    dark = filt(sig, "low", 220, 2)
    bright = filt(sig, "low", 1400, 2)
    m = np.clip(x / 0.12, 0, 1) * np.exp(-x * 1.4)                    # Filter-Hüllkurve
    sig = dark * (1 - m) + bright * m
    sig = np.tanh(sig * 1.6)
    sub = np.sin(2 * np.pi * root * x) * 0.8
    return (sig * 0.7 + sub) * env(len(x), 0.03, 1.4)


def taiko(vol=1.0):
    x = tt(1.2)
    body = np.sin(2 * np.pi * np.cumsum(55 + 75 * np.exp(-x * 18)) / SR) * np.exp(-x * 4.5)
    skin = filt(noise(1.2), "low", 900, 2) * np.exp(-x * 28) * 0.8
    return np.tanh((body + skin) * 1.8) * vol


def tick(vol=1.0):
    x = tt(0.07)
    return (np.sin(2 * np.pi * 2600 * x) * 0.5 + filt(noise(0.07), "high", 2500, 2) * 0.7) * np.exp(-x * 160) * vol


def pluck(f, dur=0.22):
    x = tt(dur)
    s = saw(f, x) + saw(f * 1.006, x)
    return filt(s, "low", 900, 2) * np.exp(-x * 14)


def heartbeat(vol=1.0):
    out = np.zeros(int(0.9 * SR))
    for t0, a in ((0.0, 1.0), (0.26, 0.7)):
        x = tt(0.45)
        th = np.sin(2 * np.pi * np.cumsum(48 + 38 * np.exp(-x * 24)) / SR) * np.exp(-x * 10) * a
        st = int(t0 * SR)
        out[st:st + len(th)] += th
    return np.tanh(out * 2.4) * vol


def riser(dur=2.0):
    x = tt(dur)
    k = (x / dur) ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(120 + 1600 * k) / SR) * 0.4
    hiss = filt(noise(dur), "high", 1500, 2) * 0.5
    return (tone + hiss) * k


def piano(f, dur=3.0, vol=1.0):
    x = tt(dur)
    s = np.zeros_like(x)
    for n, a in ((1, 1.0), (2, 0.45), (3, 0.22), (4, 0.12), (5, 0.06)):
        fn = f * n * (1 + 0.0004 * n * n)
        s += np.sin(2 * np.pi * fn * x) * a * np.exp(-x * (1.1 + 0.5 * n))
    hammer = filt(noise(dur), "band", [800, 3000], 2) * np.exp(-x * 120) * 0.08
    return (s + hammer) * np.minimum(x / 0.004, 1) * vol


def bell(f, dur=4.0, vol=1.0):
    x = tt(dur)
    s = sum(np.sin(2 * np.pi * f * k * x) * a * np.exp(-x * d)
            for k, a, d in ((1, 1.0, 0.9), (2.76, 0.5, 1.6), (5.4, 0.25, 2.8), (8.93, 0.12, 4.0)))
    return s * np.minimum(x / 0.002, 1) * vol


def crowd(dur, vol=1.0, swell=0.4):
    """Publikum: breitbandiges Rauschen + „Jubel“-Formant, unruhige Lautstärke, Stereo."""
    x = tt(dur)
    out = []
    for ch in range(2):
        base = filt(noise(dur), "band", [250, 3200], 2)
        cheer = filt(noise(dur), "band", [700, 1600], 2) * 1.4
        mod = 0.7 + 0.3 * np.sin(2 * np.pi * (0.6 + 0.2 * ch) * x + ch) * np.sin(2 * np.pi * 0.21 * x + 1.3)
        out.append((base + cheer) * mod)
    sig = np.stack(out, 1) * (np.clip(x / swell, 0, 1) ** 1.5)[:, None]
    return sig * vol


def horn(dur=1.8):
    """Arena-Sirene (Spielende 1980): tiefer Rechteck-Akkord mit leichtem Vibrato."""
    x = tt(dur)
    vib = 1 + 0.003 * np.sin(2 * np.pi * 5 * x)
    s = sum(np.sign(np.sin(2 * np.pi * np.cumsum(f * vib) / SR)) * a for f, a in ((185.0, 0.6), (233.1, 0.45), (277.2, 0.35)))
    return filt(s, "low", 1800, 2) * env(len(x), 0.03, 0.25)


def cymbal(dur=3.5):
    x = tt(dur)
    return filt(noise(dur), "high", 4500, 2) * np.exp(-x * 1.3) * np.minimum(x / 0.003, 1)


def sub_boom(dur=2.5):
    x = tt(dur)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(30 + 70 * np.exp(-x * 8)) / SR) * np.exp(-x * 1.4) * 3)


def whoosh(dur=0.6):
    x = tt(dur)
    return filt(noise(dur), "band", [300, 2500], 2) * np.sin(np.pi * x / dur) ** 2


def wind(dur):
    x = tt(dur)
    w = filt(noise(dur), "band", [150, 900], 2) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.17 * x) ** 2)
    return w * env(len(x), 1.0, 1.0)


def reverb(sig, secs=2.6, mix=0.35):
    """Faltungshall mit exponentiell abklingendem, gefiltertem Rauschen (Stereo)."""
    n = int(secs * SR)
    x = np.arange(n) / SR
    out = np.zeros((len(sig) + n - 1, 2))
    for ch in range(2):
        ir = filt(noise(secs), "low", 6000, 1) * np.exp(-x * 6.9 / secs)
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        out[:, ch] = fftconvolve(sig[:, ch], ir)
    out = out[: len(sig)]
    return sig * (1 - mix) + out * mix * 1.4


# ----------------------------------------------------------------- Score
def score():
    n = int(DUR * SR)
    mus = np.zeros((n, 2))       # Musik (bekommt Hall)
    fx = np.zeros((n, 2))        # trockene Effekte

    # A · Kalte Eröffnung (0–4,8): Moll-Drone, Braam + Taiko auf Bild 0, einsames Klavier
    put(mus, drone(4.9, vol=0.9, a=0.05, r=0.6), 0.0)
    put(mus, braam(nt("D1"), 3.4), 0.0, 0.55)
    put(fx, taiko(), 0.0, 0.8)
    for t0, f in ((0.9, "D4"), (1.9, "F4"), (2.9, "A4"), (3.9, "E4")):
        put(mus, piano(nt(f), 3.0), t0, 0.35, pan=-0.2)
    # B · Sowjetunion (4,8–8,7): roter Braam, vier Taiko-Schläge auf die Medaillen
    put(mus, braam(nt("C1"), 3.6), 4.8, 0.6)
    put(fx, taiko(), 4.8, 0.7)
    put(mus, supersaw([nt("C2"), nt("G2"), nt("D#3")], 4.2, cutoff=900, a=0.8, r=1.2), 4.8, 0.35)
    for t0 in MEDALS:
        put(fx, taiko(0.55), t0)
    # C · College-Kids (8,7–11,1): hell, zerbrechlich – hohe Klaviernoten, leiser Puls
    put(mus, supersaw([nt("A#2"), nt("F3"), nt("D4")], 2.8, cutoff=1400, a=0.6, r=1.0), 8.7, 0.22)
    for t0, f in ((8.75, "D5"), (9.35, "F5"), (9.95, "A5"), (10.55, "C6")):
        put(mus, piano(nt(f), 2.0), t0, 0.22, pan=0.3)
    # D · Lake Placid (11,1–15,4): Schnee-Wind, Fläche schwillt an, Glocke auf den Titel, Riser in die Partie
    put(fx, wind(4.6), 11.0, 0.35)
    put(mus, supersaw([nt("D2"), nt("A2"), nt("F3"), nt("C4")], 4.4, cutoff=1200, a=1.4, r=0.8), 11.1, 0.32)
    put(mus, bell(nt("D5"), 4.0), 11.2, 0.25)
    put(mus, riser(1.6), 13.8, 0.28)
    # E · Das Spiel (15,4–24,55): Puls-Ostinato (Achtel, 120 BPM), Uhr-Ticken, Taiko auf jedem Anzeigewechsel
    put(mus, braam(nt("D1"), 3.0), 15.4, 0.5)
    put(mus, drone(T_SILENCE - 15.4, vol=0.8, a=0.4, r=0.05), 15.4)
    t = 15.4
    k = 0
    while t < T_SILENCE - 0.05:
        g = 0.25 + 0.55 * (t - 15.4) / (T_SILENCE - 15.4)        # Crescendo
        f = nt("D2") if (k % 8) not in (6, 7) else nt("F2")
        put(mus, pluck(f), t, g * 0.55)
        if k % 2 == 0:
            put(fx, tick(), t, 0.22 + 0.2 * g)
        t += 0.25
        k += 1
    for t0 in FLIPS:
        put(fx, taiko(0.75), t0)
    put(mus, riser(2.0), T_SILENCE - 2.0, 0.42)
    # F · Stille (24,55–26,25): nur ein Herzschlag vor dem Namen
    put(fx, heartbeat(0.9), 24.62)
    # G · 4:3 (26,25): Sub-Boom, Becken, Dur-Braam, Publikum explodiert; Countdown mit Herzschlag + Ticks
    put(fx, sub_boom(), T_GOAL, 0.95)
    put(fx, cymbal(4.0), T_GOAL, 0.45)
    put(mus, braam(nt("D1"), 3.6, major=True), T_GOAL, 0.6)
    put(mus, supersaw([nt("D2"), nt("A2"), nt("F#3"), nt("A3"), nt("D4")], T_HORN - T_GOAL + 0.4, cutoff=1600, a=0.5, r=0.6),
        T_GOAL + 0.2, 0.38)
    put(fx, crowd(T_HORN - T_GOAL + 1.0, swell=0.25), T_GOAL, 0.55)
    for i, key in enumerate(("c5", "c4", "c3", "c2", "c1")):
        t0 = VO_START[key] - 0.18
        put(fx, heartbeat(0.75 + 0.05 * i), t0)
        put(fx, tick(1.0), t0 + 0.02, 0.5)
    put(mus, riser(3.4), T_HORN - 3.4, 0.3)
    # H · Schlusssirene + Titel (33,3–39,4): Horn, Becken, Jubel-Höhepunkt, Chor in Dur, Glocken auf den Titel
    put(fx, horn(2.2), T_HORN, 0.55)
    put(fx, cymbal(4.5), T_HORN + 0.05, 0.5)
    put(fx, sub_boom(), T_HORN + 0.05, 0.7)
    c = crowd(6.0, swell=0.05)
    cx = np.arange(len(c)) / SR
    c *= (1.0 - 0.72 * np.clip((cx - 0.45) / 0.35, 0, 1))[:, None]       # Jubel-Spitze, dann leiser unter dem Titel-Satz
    put(fx, c, T_HORN, 0.75)
    put(mus, choir([nt("D3"), nt("F#3"), nt("A3"), nt("D4")], 6.4, a=0.8, r=2.0), T_HORN + 0.1, 0.42)
    put(mus, supersaw([nt("D2"), nt("A2"), nt("D3")], 6.4, cutoff=900, a=0.3, r=2.0), T_HORN + 0.1, 0.35)
    for t0, f in ((34.75, "D5"), (34.75, "A5"), (35.35, "F#5")):
        put(mus, bell(nt(f), 4.0), t0, 0.22)
    for t0, f in ((36.6, "A4"), (37.3, "F#4"), (38.0, "D5")):
        put(mus, piano(nt(f), 3.0), t0, 0.3)
    # I · Frage (39,4–44): leise Fläche, Klavier, letzter tiefer Schlag nach „Yes or no?“
    put(mus, supersaw([nt("G2"), nt("D3"), nt("B3")], 2.4, cutoff=1100, a=0.6, r=1.0), 39.4, 0.28)
    put(mus, supersaw([nt("D2"), nt("A2"), nt("F#3"), nt("D4")], 2.6, cutoff=1100, a=0.6, r=1.8), 41.4, 0.3)
    for t0, f in ((39.5, "D5"), (40.4, "B4"), (41.3, "A4")):
        put(mus, piano(nt(f), 2.6), t0, 0.28)
    put(fx, sub_boom(), 42.62, 0.7)
    put(fx, taiko(0.6), 42.62)
    # Übergangs-Whooshes auf die Schnitte
    for t0 in (4.62, 8.52, 10.92, 15.22, 33.2, 39.22):
        put(fx, whoosh(0.5), t0, 0.22)
    mus = reverb(mus, 2.8, 0.38)
    return mus, fx


# ----------------------------------------------------------------- Mischung
def norm(sig, peak=0.89):
    return sig / (np.max(np.abs(sig)) + 1e-9) * peak


def voice_track():
    buf = np.zeros((int(DUR * SR), 2))
    for key, t0 in VO_START.items():
        a, sr = sf.read(os.path.join(HERE, "audio", "vo", f"vo_{key}.wav"), dtype="float64")
        if a.ndim == 2:
            a = a.mean(1)
        if sr != SR:
            a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a)
        put(buf, a, t0, 1.0)
    return buf


def duck_curve(vo):
    act = (np.abs(vo).max(1) > 0.02).astype(float)
    k = int(0.25 * SR)
    hold = np.convolve(act, np.ones(k), "same") > 0
    g = np.where(hold, 0.42, 1.0)
    sm = int(0.06 * SR)
    return np.convolve(g, np.ones(sm) / sm, "same")


def write(path, sig, peak=0.95):
    sig = norm(sig, peak)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((sig * 32767).astype(np.int16).tobytes())


def main():
    mus, fx = score()
    vo = voice_track()
    g = duck_curve(vo)[:, None]
    bed = norm(mus) * 0.62 + norm(fx) * 0.6
    write(os.path.join(HERE, "audio", "score.wav"), bed)
    write(os.path.join(HERE, "audio", "mix_vo.wav"), bed * (0.45 + 0.55 * g) + norm(vo) * 0.92)
    write(os.path.join(HERE, "audio", "mix_novo.wav"), bed)
    print("fertig")


if __name__ == "__main__":
    main()
