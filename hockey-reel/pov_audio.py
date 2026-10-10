"""Leiser Ton wie vom Handy aufgenommen: Raumrauschen, Trackpad-Klicks und der Soundtrack der
Animation, der aus Laptop-Lautsprechern kommt (bandbegrenzt, etwas Raumhall)."""
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100


class Mix:
    def __init__(self, dur, seed=5):
        self.n = int(dur * SR)
        self.room = np.zeros(self.n)      # direkt am Handy (Klicks, Raum)
        self.lap = np.zeros(self.n)       # aus den Laptop-Lautsprechern
        self.rng = np.random.default_rng(seed)

    def t(self, sec):
        return np.arange(int(sec * SR)) / SR

    def put(self, buf, sig, at, vol=1.0):
        st = int(round(at * SR))
        if st < 0:
            sig, st = sig[-st:], 0
        e = min(self.n, st + len(sig))
        if st < self.n and e > st:
            buf[st:e] += sig[: e - st] * vol

    # ------------------------------------------------------------- Klänge
    def click(self):
        x = self.t(0.05)
        nz = self.rng.standard_normal(len(x))
        return (np.sin(2 * np.pi * 2400 * x) * 0.5 + nz * 0.6) * np.exp(-x * 260) * 0.5

    def key_tap(self):
        x = self.t(0.04)
        nz = self.rng.standard_normal(len(x))
        return (np.sin(2 * np.pi * 1800 * x) * 0.3 + nz * 0.5) * np.exp(-x * 320) * 0.25

    def chime(self, f, dur=1.4, vol=0.5):
        x = self.t(dur)
        sig = np.sin(2 * np.pi * f * x) + 0.35 * np.sin(2 * np.pi * f * 2.01 * x) * np.exp(-x * 3) + 0.15 * np.sin(2 * np.pi * f * 3.0 * x) * np.exp(-x * 6)
        return sig * np.minimum(x / 0.004, 1) * np.exp(-x * 3.2) * vol

    def pluck(self, f, dur=0.6, vol=0.4):
        x = self.t(dur)
        sig = sum(np.sin(2 * np.pi * f * h * x) / h ** 1.4 for h in (1, 2, 3, 4))
        return sig * np.minimum(x / 0.003, 1) * np.exp(-x * 7) * vol

    def whoosh(self, dur=0.4, vol=0.5, rise=True):
        x = self.t(dur)
        nz = self.rng.standard_normal(len(x))
        sos_lo = butter(2, [300, 1800], "bandpass", fs=SR, output="sos")
        sos_hi = butter(2, [1800, 6000], "bandpass", fs=SR, output="sos")
        lo, hi = sosfilt(sos_lo, nz), sosfilt(sos_hi, nz)
        m = x / dur if rise else 1 - x / dur
        env = np.sin(np.pi * x / dur) ** 2
        return (lo * (1 - m) + hi * m) * env * vol * 2.2

    def pop(self, f=900, vol=0.35):
        x = self.t(0.12)
        fr = f * (1 + 1.5 * np.exp(-x * 60))
        return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-x * 35) * vol

    def thud(self, vol=0.6):
        x = self.t(0.35)
        fr = 90 + 160 * np.exp(-x * 30)
        return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-x * 12) * vol

    def shimmer(self, dur=1.2, vol=0.3):
        x = self.t(dur)
        sig = sum(np.sin(2 * np.pi * f * x + k) for k, f in enumerate((2093, 2637, 3136, 3951)))
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * 9 * x)
        return sig / 4 * trem * np.minimum(x / 0.4, 1) * np.exp(-x * 2.0) * vol

    def pad(self, freqs, dur, vol=0.25, attack=0.6, release=1.0):
        x = self.t(dur)
        sig = np.zeros(len(x))
        for f in freqs:
            for det in (-0.003, 0.0, 0.003):
                sig += np.sin(2 * np.pi * f * (1 + det) * x + self.rng.uniform(0, 6.28))
        sig /= len(freqs) * 3
        env = np.minimum(x / attack, 1) * np.clip((dur - x) / release, 0, 1)
        return sig * env * (1 + 0.08 * np.sin(2 * np.pi * 0.4 * x)) * vol

    # ------------------------------------------------------------- Ausgabe
    def render(self, path, lap_gain=1.0, room_gain=1.0, target_peak=0.5):
        # Laptop-Lautsprecher: Hochpass ~250 Hz, Tiefpass ~6 kHz, kleine Resonanz, kurzer Raumhall
        sos = butter(2, [250, 6500], "bandpass", fs=SR, output="sos")
        lap = sosfilt(sos, self.lap)
        lap = np.tanh(lap * 1.4) / 1.4
        irl = int(0.5 * SR)
        ix = np.arange(irl) / SR
        ir = self.rng.standard_normal(irl) * np.exp(-ix * 9)
        ir /= np.sqrt(np.sum(ir ** 2))
        lap = lap + fftconvolve(lap, ir)[: self.n] * 0.22
        # Raumton (leises Rauschen, Brummen)
        x = np.arange(self.n) / SR
        tone = self.rng.standard_normal(self.n)
        tone = sosfilt(butter(2, [80, 3000], "bandpass", fs=SR, output="sos"), tone) * 0.006
        tone += np.sin(2 * np.pi * 50 * x) * 0.0015
        room = sosfilt(butter(2, 120, "highpass", fs=SR, output="sos"), self.room) + tone
        mix = lap * lap_gain + room * room_gain
        mix = mix / (np.max(np.abs(mix)) + 1e-9) * target_peak
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((mix * 32767).astype(np.int16).tobytes())
