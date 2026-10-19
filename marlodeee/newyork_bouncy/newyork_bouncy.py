"""Bouncy-Hardcore-Instrumental für den Bootleg „Ich war noch niemals in New York“ (@marlodeee).

Synthetisiert komplett in numpy: verzerrte Hardcore-Kick, Offbeat-Bounce-Bass, Hats, Clap,
Hoover-Lead (eigene Melodie), Screech, Riser, Snare-Roll, Pad. Das Original-Vocal ist NICHT
enthalten: Es wird freigestellt (z. B. Ultimate Vocal Remover) und laut cue_sheet.md angelegt.

Aufruf: python3 newyork_bouncy.py [--bpm 175] [--key 0]
  --key verschiebt die Tonart in Halbtönen (0 = f-Moll), passend zur Tonart des Acapellas.
Ausgabe: newyork_bouncy.wav / .mp3, stems/*.wav, cue_sheet.md
"""
import argparse
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
HERE = Path(__file__).resolve().parent
rng = np.random.default_rng(175)

# Arrangement in Takten (4/4): (Name, Takte)
SECTIONS = [("Intro", 8), ("Build", 8), ("Drop 1", 16), ("Break", 8), ("Build 2", 4),
            ("Drop 2", 16), ("Outro", 4)]


# ---------------------------------------------------------------- DSP-Helfer
def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def fft_filter(x, lo=None, hi=None):
    n = len(x)
    f = np.fft.rfft(x)
    fr = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(fr)
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(fr, 1e-3)) ** 4)
    if hi:
        g *= 1 / np.sqrt(1 + (fr / hi) ** 4)
    return np.fft.irfft(f * g, n)


def sweep_lp(x, f0, f1, blk=4096):
    """Tiefpass mit über die Länge gleitender Grenzfrequenz (Overlap-Add)."""
    n = len(x)
    hop = blk // 2
    win = np.hanning(blk)
    fr = np.fft.rfftfreq(blk, 1 / SR)
    pad = np.concatenate([x, np.zeros(blk)])
    out = np.zeros(n + blk)
    for s in range(0, n, hop):
        k = s / max(n - 1, 1)
        fc = f0 * (f1 / f0) ** k
        g = 1 / np.sqrt(1 + (fr / fc) ** 4)
        out[s:s + blk] += np.fft.irfft(np.fft.rfft(pad[s:s + blk] * win) * g, blk)
    return out[:n]


def saw(phase):
    return 2 * (phase - np.floor(phase + 0.5))


def osc_saw(freq_curve):
    ph = np.cumsum(freq_curve) / SR
    return saw(ph)


def env_ad(n, a, d):
    t = np.arange(n) / SR
    return np.clip(t / max(a, 1e-4), 0, 1) * np.exp(-t / d)


# ---------------------------------------------------------------- Instrumente
def kick(hard=True):
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    f = 48 + 260 * np.exp(-t * 38) + 60 * np.exp(-t * 9)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (5.0 if hard else 7.5))
    click = rng.standard_normal(n) * np.exp(-t * 900) * 0.6
    k = body + click
    if hard:  # Hardcore-Verzerrung
        k = np.tanh(k * 6.0) * 0.9
        k = fft_filter(k, hi=9000)
    return k * np.clip((0.40 - t) / 0.05, 0, 1)


def bounce(note, length):
    """Offbeat-Bounce: kurzer, nach unten gezogener Rechteck/Saw-Bass."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = midi_hz(note) * 2 ** ((10 * np.exp(-t * 55)) / 12)
    ph = np.cumsum(f) / SR
    sig = 0.55 * saw(ph) + 0.45 * np.sign(np.sin(2 * np.pi * ph))
    sig = np.tanh(sig * 2.2)
    return sig * env_ad(n, 0.003, length * 0.55)


def clap():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    e = sum(np.exp(-np.maximum(t - d, 0) * 60) * (t >= d) for d in (0, 0.009, 0.018)) / 3
    e += np.exp(-t * 14) * 0.5
    return fft_filter(noise * e, lo=900, hi=7000)


def hat(open_=False):
    n = int((0.16 if open_ else 0.045) * SR)
    t = np.arange(n) / SR
    return fft_filter(rng.standard_normal(n), lo=7000) * np.exp(-t * (18 if open_ else 110))


def snare():
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)
    return (fft_filter(rng.standard_normal(n), lo=1200) * np.exp(-t * 22) + tone * 0.6)


def hoover(note, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    bend = 2 ** ((-7 * np.exp(-t * 30)) / 12)  # Hoover-Ansatz von unten
    out = np.zeros(n)
    for d in (-0.32, -0.18, -0.07, 0.0, 0.08, 0.19, 0.31):
        f = midi_hz(note + d) * bend
        out += osc_saw(f * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t)))
        out += 0.5 * osc_saw(f * 0.5)
    out = np.tanh(out / 3.5 * 1.8)
    return out * env_ad(n, 0.004, max(length * 0.9, 0.08)) * np.clip((length - t) / 0.01, 0, 1)


def screech(note, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    wob = 2 ** ((1.2 * np.sin(2 * np.pi * 9 * t) + 12 * np.exp(-t * 25)) / 12)
    f = midi_hz(note + 12) * wob
    ph = np.cumsum(f) / SR
    sig = saw(ph) + 0.6 * np.sin(2 * np.pi * ph * 3.01)
    sig = np.tanh(sig * 5)
    return sig * env_ad(n, 0.002, length * 0.8)


def pad(notes, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        for d in (-0.1, 0.0, 0.11):
            out += osc_saw(np.full(n, midi_hz(m + d)))
    out /= len(notes) * 3
    e = np.clip(t / 0.25, 0, 1) * np.clip((length - t) / 0.2, 0, 1)
    return out * e


def riser(length):
    n = int(length * SR)
    x = rng.standard_normal(n)
    t = np.arange(n) / SR
    up = sweep_lp(x, 300, 14000) * (t / length) ** 2
    tone = np.sin(2 * np.pi * np.cumsum(220 * 2 ** (3 * t / length)) / SR) * (t / length) ** 3
    return up * 0.8 + tone * 0.25


def impact():
    n = int(2.5 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(35 + 120 * np.exp(-t * 14)) / SR) * np.exp(-t * 1.6)
    crash = fft_filter(rng.standard_normal(n), lo=4000) * np.exp(-t * 2.2) * 0.35
    return boom + crash


# ---------------------------------------------------------------- Komposition
def build(bpm, key):
    beat = 60 / bpm
    bar = 4 * beat
    total_bars = sum(b for _, b in SECTIONS)
    n = int((total_bars * bar + 3) * SR)
    stems = {k: np.zeros(n) for k in ("kick", "bass", "drums", "lead", "fx")}
    starts, b0 = {}, 0
    for name, bars in SECTIONS:
        starts[name] = (b0, bars)
        b0 += bars

    def put(stem, sig, at, gain=1.0):
        s = int(at * SR)
        e = min(n, s + len(sig))
        if 0 <= s < n:
            stems[stem][s:e] += sig[:e - s] * gain

    root = 41 + key  # F2
    prog = [0, -4, -2, -5]  # f – Des – Es – c (Takt für Takt)
    K, KS = kick(True), kick(False)
    CL, HC, HO, SN = clap(), hat(False), hat(True), snare()

    # Lead-Motiv (eigene Melodie): (16tel-Schritt, Halbton relativ zu F4, Länge in 16teln)
    motif = [
        [(0, 0, 2), (3, 0, 2), (6, 3, 2), (8, 7, 3), (11, 5, 2), (14, 3, 2)],
        [(0, 8, 2), (3, 8, 2), (6, 7, 2), (8, 5, 3), (11, 3, 2), (14, 2, 2)],
        [(0, 3, 2), (3, 3, 2), (6, 5, 2), (8, 7, 3), (11, 10, 2), (14, 12, 2)],
        [(0, 7, 6), (8, 5, 2), (10, 3, 2), (12, 2, 2), (14, 0, 2)],
    ]
    lead_root = 65 + key
    six = beat / 4

    def drums_bar(t0, full=True):
        for b in range(4):
            put("kick", K, t0 + b * beat)
            put("bass", bounce(root + cur_bass, beat * 0.5), t0 + b * beat + beat / 2, 0.62)
            put("drums", HO, t0 + b * beat + beat / 2, 0.22)
            if full:
                for s in (1, 3):
                    put("drums", HC, t0 + b * beat + s * six, 0.18)
        if full:
            put("drums", CL, t0 + beat, 0.45)
            put("drums", CL, t0 + 3 * beat, 0.45)

    # ---- Intro: Kick öffnet sich, Bass-Bounce erst ab Takt 5
    b, bars = starts["Intro"]
    intro_k = np.zeros(int(bars * bar * SR) + SR)
    for i in range(bars * 4):
        s = int(i * beat * SR)
        intro_k[s:s + len(K)] += K[:len(intro_k) - s]
    intro_k = sweep_lp(intro_k, 180, 2500)
    put("kick", intro_k, b * bar, 0.5)
    for i in range(bars):
        cur_bass = prog[i % 4]
        if i >= 4:
            for q in range(4):
                put("bass", bounce(root + cur_bass, beat * 0.5), (b + i) * bar + q * beat + beat / 2,
                    0.35 * (i - 3) / 4)
        put("fx", pad([lead_root - 12 + cur_bass, lead_root - 9 + cur_bass + (1 if cur_bass in (-4,) else 0),
                       lead_root - 5 + cur_bass], bar), (b + i) * bar, 0.22)

    # ---- Build: Snare-Roll 8tel -> 16tel -> 32tel, Riser, letzter Schlag leer
    def build_section(name, intensity=1.0):
        nonlocal cur_bass
        b, bars = starts[name]
        t0 = b * bar
        for i in range(bars):
            cur_bass = prog[i % 4]
            for q in range(4):
                if not (i == bars - 1 and q == 3):
                    put("kick", KS, t0 + i * bar + q * beat, 0.8)
            frac = i / bars
            div = 2 if frac < 0.5 else (4 if frac < 0.75 else 8)
            for s in range(4 * div):
                at = t0 + i * bar + s * beat / div
                if i == bars - 1 and s >= 3 * div:
                    break
                put("drums", SN, at, (0.15 + 0.5 * (i * 4 * div + s) / (bars * 4 * div)) * intensity)
        put("fx", riser(bars * bar - beat), t0, 0.32 * intensity)

    cur_bass = 0
    build_section("Build")

    # ---- Drops
    def drop(name, with_screech):
        nonlocal cur_bass
        b, bars = starts[name]
        t0 = b * bar
        put("fx", impact(), t0, 0.55)
        for i in range(bars):
            cur_bass = prog[i % 4]
            drums_bar(t0 + i * bar)
            for step, semi, ln in motif[i % 4]:
                at = t0 + i * bar + step * six
                put("lead", hoover(lead_root + semi, ln * six * 0.95), at, 0.30)
                if with_screech and i % 2 == 1:
                    put("lead", screech(lead_root + semi, ln * six * 0.8), at, 0.11)
            if i % 8 == 7:  # Fill vor jeder Phrase
                for s in range(8):
                    put("drums", SN, t0 + i * bar + 3 * beat + s * beat / 8, 0.25 + s * 0.04)

    drop("Drop 1", False)

    # ---- Break: Pad + leiser Bounce, Platz für das Vocal
    b, bars = starts["Break"]
    for i in range(bars):
        cb = prog[i % 4]
        put("fx", pad([lead_root - 12 + cb, lead_root - 8 + cb, lead_root - 5 + cb, lead_root + cb], bar),
            (b + i) * bar, 0.6)
        if i >= 4:
            for q in range(4):
                put("drums", HC, (b + i) * bar + q * beat + beat / 2, 0.12)

    build_section("Build 2", 1.1)
    drop("Drop 2", True)

    # ---- Outro: Kick + Bass, ausblendend
    b, bars = starts["Outro"]
    for i in range(bars):
        cur_bass = prog[i % 4]
        g = 1 - i / bars
        for q in range(4):
            put("kick", K, (b + i) * bar + q * beat, g)
            put("bass", bounce(root + cur_bass, beat * 0.5), (b + i) * bar + q * beat + beat / 2, 0.6 * g)

    stems["lead"] = fft_filter(stems["lead"], lo=150, hi=9000)
    stems["bass"] = fft_filter(stems["bass"], hi=5000)
    return stems, starts, bar


def write_wav(path, x):
    st = np.stack([x, x], 1) if x.ndim == 1 else x
    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def stereo(x, width=0.0, delay_ms=0.0):
    if width == 0:
        return np.stack([x, x], 1)
    d = int(delay_ms / 1000 * SR)
    r = np.concatenate([np.zeros(d), x[:-d]]) if d else x
    return np.stack([x, x * (1 - width) + r * width], 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bpm", type=float, default=175)
    ap.add_argument("--key", type=int, default=0, help="Halbtöne relativ zu f-Moll")
    a = ap.parse_args()

    stems, starts, bar = build(a.bpm, a.key)
    gains = {"kick": 0.95, "bass": 0.8, "drums": 0.75, "lead": 0.7, "fx": 0.8}
    widths = {"kick": 0, "bass": 0, "drums": 0.3, "lead": 0.5, "fx": 0.6}
    mix = np.zeros((len(stems["kick"]), 2))
    sd = HERE / "stems"
    sd.mkdir(exist_ok=True)
    for k, s in stems.items():
        st = stereo(s * gains[k], widths[k], 13)
        mix += st
        write_wav(sd / f"{k}.wav", st / max(np.abs(st).max(), 1e-9) * 0.89)
    # Master: Soft-Clip + Normalisierung auf -1 dBFS
    mix = np.tanh(mix * 1.1)
    mix *= 0.89 / np.abs(mix).max()
    trim = int((sum(b for _, b in SECTIONS) * bar + 1.5) * SR)
    mix = mix[:trim]
    write_wav(HERE / "newyork_bouncy.wav", mix)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(HERE / "newyork_bouncy.wav"),
                    "-b:a", "256k", str(HERE / "newyork_bouncy.mp3")], check=True)

    # Cue-Sheet für das Vocal
    def ts(bars_):
        s = bars_ * bar
        return f"{int(s // 60)}:{s % 60:05.2f}"

    vocal = {
        "Intro": "Takt 1–8: Strophe/erste Zeile clean, ohne Effekte. Ab Takt 5 kommt der Bounce leise dazu.",
        "Build": "Takt 9–16: „Ich war noch niemals in New York“ als Chop: erst ganze Zeile, dann "
                 "„New York – York – York“ im 16tel-Takt, letzter Schlag Stille.",
        "Drop 1": "Takt 17–32: Refrain-Hook hochgepitcht (+2–3 Halbtöne), auf jeden 2. Takt "
                  "gesetzt, damit der Lead dazwischen atmet.",
        "Break": "Takt 33–40: ruhige Zeile solo („…ich war noch niemals in Hawaii“), viel Hall.",
        "Build 2": "Takt 41–44: kurzer Chop „einfach mal hin“, endet mit Stille.",
        "Drop 2": "Takt 45–60: Refrain voll, Screech kommt jeden 2. Takt dazu.",
        "Outro": "Takt 61–64: letzte Silbe ausklingen lassen.",
    }
    lines = [f"# Cue-Sheet: „Ich war noch niemals in New York“ × Bouncy Hardcore\n",
             f"**{a.bpm:g} BPM · Tonart: f-Moll{f' ({a.key:+d} HT)' if a.key else ''} · "
             f"Länge {ts(sum(b for _, b in SECTIONS))}**\n",
             "| Teil | Takte | Start | Vocal |", "|---|---|---|---|"]
    for name, (b0, bars) in starts.items():
        lines.append(f"| {name} | {b0 + 1}–{b0 + bars} | {ts(b0)} | {vocal[name]} |")
    lines += ["", "## So legst du das Vocal an",
              "1. Acapella freistellen (Ultimate Vocal Remover, Demucs oder rekordbox-Stems).",
              f"2. In Ableton auf {a.bpm:g} BPM warpen (Complex Pro).",
              "3. Tonart prüfen (Mixed In Key / rekordbox). Passt f-Moll nicht, das Instrumental "
              "mit `--key` neu rendern, z. B. `python3 newyork_bouncy.py --key 2`.",
              "4. Vocal: Low-Cut bei ~200 Hz, Sidechain auf die Kick, etwas Hall in Break und Intro.",
              "5. Für das Reel den Drop 1 ab Takt 17 nehmen: Hook-Text ins Bild, Drop nach max. 3 s."]
    (HERE / "cue_sheet.md").write_text("\n".join(lines) + "\n")
    print("fertig:", HERE / "newyork_bouncy.mp3", f"({ts(sum(b for _, b in SECTIONS))})")


if __name__ == "__main__":
    main()
