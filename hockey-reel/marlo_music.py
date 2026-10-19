#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARLODEEE hype reel - music (original, synthesised from scratch in code).

150 BPM hard techno / hard trance in A minor, exactly 16.0 s (705600 samples,
44.1 kHz, stereo, 16 bit).  One beat = 17640 samples (0.4 s), one bar = 70560.

Timeline (matches the shared contract of the reel):
    bars 1-2  (0.0 - 3.2 s)   INTRO   kick on every beat from sample 0, sub/rumble, minimal hats
    bars 3-4  (3.2 - 6.0 s)   BUILD   hats + clap (2 & 4), noise riser, snare roll 1/8 -> 1/16 -> 1/32,
                                       pitch-rising supersaw lead
    gap       (6.0 - 6.4 s)   GAP     no kick / bass, only riser tail + reverse crash + hanging reverb
    bars 5-8  (6.4 - 12.8 s)  DROP    impact exactly at 6.4 s, 4/4 kick, rolling 16th bounce bass,
                                       open hats, clap/rim, supersaw stabs + arp (+ lead in bars 7-8)
    bars 9-10 (12.8 - 16.0 s) OUTRO   filter closes, hats fade, kick continues, pitch-fall fill in the
                                       last beat so the file loops back into the t = 0 kick

Public API
    make_audio(path, events_path=None) -> dict   renders the track, writes the WAV (and optionally the
                                                  events JSON) and returns the events dict
    get_events() -> dict                          event times only (cheap, no audio rendering)
    render_float() -> (np.ndarray (705600, 2), dict)   mastered float signal + events (no file written)
    SR, DUR, NS, BPM, BEAT_S, BEAT, BAR, STEP     constants
Running `python3 marlo_music.py` writes audio_marlo.wav and marlo_music_events.json next to this file.
"""
import os
import sys
import json
import math
import wave

import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d
import numba as nb

HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = bool(os.environ.get("NUMBA_CACHE_DIR"))


def njit(f):
    return nb.njit(cache=_CACHE)(f)


# ===================================================================== timeline
SR = 44100
BPM = 150
BEAT = 17640            # 0.4 s
STEP = 4410             # 1/16 note
BAR = 70560             # 1.6 s
NS = 705600             # 16.0 s
DUR = 16.0
BEAT_S = 0.4
GAP_BEAT = 15           # 6.0 - 6.4 s
TARGET_LUFS = -9.4
CEIL_DB = -1.3          # true-peak ceiling of the final limiter (dBTP)
SYNTH_CEIL = 0.55       # peak ceiling of the synth bus before the master (kick stem peaks at 0.84)

KICK_BEATS = [k for k in range(40) if k != GAP_BEAT]
CLAP_BEATS = [9, 11, 13] + [17, 19, 21, 23, 25, 27, 29, 31] + [33, 35, 37]
CHORD_BAR = {0: "Am", 1: "Am", 2: "Am", 3: "F", 4: "Am", 5: "F", 6: "C", 7: "G", 8: "F", 9: "G"}


def chord_at_beat(k):
    bar = k // 4
    if bar == 3 and k >= 14:
        return "G"
    return CHORD_BAR[bar]


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


CHORDS = {
    "Am": dict(root=45, stab=[57, 60, 64, 69], arp=[69, 72, 76, 81]),
    "F": dict(root=41, stab=[53, 57, 60, 65], arp=[65, 69, 72, 77]),
    "C": dict(root=48, stab=[55, 60, 64, 67], arp=[67, 72, 76, 79]),
    "G": dict(root=43, stab=[55, 59, 62, 67], arp=[67, 71, 74, 79]),
}

# lead hook for bars 7-8 (0-based bars 6, 7): (step, midi, length in steps)
LEAD_HOOK = {
    6: [(0, 79, 3), (3, 76, 3), (6, 79, 2), (8, 81, 3), (11, 79, 3), (14, 76, 2)],
    7: [(0, 74, 3), (3, 71, 3), (6, 74, 2), (8, 76, 3), (11, 74, 3), (14, 71, 2)],
}
ARP_PAT = [0, 2, 3, 2, 1, 2, 3, 2, 0, 2, 3, 2, 1, 3, 2, 1]
# chord-stab rhythm per bar (0-based bar -> [(16th step, velocity)])
STAB_STEPS = {
    4: [(3, 1.0), (6, 1.0), (11, 0.9), (14, 1.0)],
    5: [(3, 1.0), (6, 1.0), (11, 0.9), (14, 1.0)],
    6: [(2, 0.7), (6, 0.8), (10, 0.7), (14, 0.8)],
    7: [(2, 0.7), (6, 0.8), (10, 0.7), (14, 0.8)],
    8: [(3, 0.5), (11, 0.4)],
}


def snare_roll_times():
    """14 hits: 1/8 in beat 12 (4.8 s), 1/16 in beat 13, 1/32 in beat 14 (stops at 6.0 s)."""
    out = []
    for i in range(2):
        out.append((12 * BEAT + i * (BEAT // 2)))
    for i in range(4):
        out.append((13 * BEAT + i * (BEAT // 4)))
    for i in range(8):
        out.append((14 * BEAT + i * (BEAT // 8)))
    return out


def get_events():
    """Key event times in seconds (no audio rendering needed)."""
    bar_s = [round(b * 1.6, 6) for b in range(10)]
    ev = dict(
        bpm=BPM, sample_rate=SR, duration=DUR, samples=NS, beat=BEAT_S, bar=1.6, step16=0.1,
        key="A minor", chords_per_bar=[CHORD_BAR[b] for b in range(10)],
        bar_starts=bar_s,
        kick_times=[round(k * BEAT_S, 6) for k in KICK_BEATS],
        kick_missing_beats=[GAP_BEAT],
        clap_times=[round(k * BEAT_S, 6) for k in CLAP_BEATS],
        intro_start=0.0, intro_end=3.2,
        build_start=3.2, riser_start=3.2, crash_build_start=3.2,
        snare_roll_start=4.8, snare_roll_times=[round(s / SR, 6) for s in snare_roll_times()],
        build_lead_start=4.0, build_lead_end=6.0,
        reverse_crash_start=5.2, reverse_crash_end=6.4,
        gap_start=6.0, gap_end=6.4, drop=6.4, impact=6.4,
        lead_start=9.6, outro_start=12.8,
        crash_times=[0.0, 3.2, 6.4, 9.6, 12.8],
        fill_snare_times=[round(23 * BEAT_S + i * 0.1, 6) for i in range(4)],
        stab_times=[6.4] + [round((bar * 16 + st) * STEP / SR, 6) for bar in STAB_STEPS for st, _ in STAB_STEPS[bar]],
        lead_note_times=[round((bar * 16 + st) * STEP / SR, 6) for bar in LEAD_HOOK for st, _, _ in LEAD_HOOK[bar]],
        bass_roll_start=6.4,
        hook_stab_times=[0.0, 1.6],
        fill_start=15.6, fill_zap_start=round((NS - int(0.22 * SR)) / SR, 6), loop_point=16.0,
        text_cue_beats=dict(hard_techno=3.2, hard_trance=4.0, melodic=4.8, marlodeee_glitch=5.6),
        open_hat_times=[round(((b * 4 + beat) * 4 + 2) * STEP / SR, 6)
                        for b in range(4, 8) for beat in range(4)],
    )
    return ev


# ===================================================================== helpers
def db(x):
    return 10.0 ** (x / 20.0)


def pan_gains(p):
    a = (p + 1.0) * math.pi / 4.0
    return math.cos(a) * math.sqrt(2.0), math.sin(a) * math.sqrt(2.0)


def put(buf, sig, start, gain=1.0, pan=0.0):
    """Add sig (mono or stereo) into buf (NS, 2) at sample index start (clipped to the buffer)."""
    start = int(start)
    m = len(sig)
    if start >= NS or start + m <= 0:
        return
    s0 = max(0, -start)
    e = min(m, NS - start)
    seg = sig[s0:e]
    d0 = start + s0
    if seg.ndim == 1:
        gl, gr = pan_gains(pan)
        buf[d0:d0 + len(seg), 0] += seg * (gain * gl)
        buf[d0:d0 + len(seg), 1] += seg * (gain * gr)
    else:
        buf[d0:d0 + len(seg)] += seg * gain


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def _sos(kind, fc, order):
    fc = float(min(max(fc, 5.0), SR * 0.47))
    return signal.butter(order, fc, kind, fs=SR, output="sos")


def hp(x, fc, order=2):
    return signal.sosfilt(_sos("highpass", fc, order), x, axis=0)


def lp(x, fc, order=2):
    return signal.sosfilt(_sos("lowpass", fc, order), x, axis=0)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x, axis=0)


def peq(x, f0, gain_db, q):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / SR
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    b = np.array([1 + al * A, -2 * c, 1 - al * A])
    a = np.array([1 + al / A, -2 * c, 1 - al / A])
    return signal.sosfilt(np.concatenate([b / a[0], a / a[0]])[None, :], x, axis=0)


def shelf(x, f0, gain_db, high=True, S=1.0):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / SR
    c, s = math.cos(w0), math.sin(w0)
    al = s / 2 * math.sqrt((A + 1 / A) * (1 / S - 1) + 2)
    t = 2 * math.sqrt(A) * al
    if high:
        b = [A * ((A + 1) + (A - 1) * c + t), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - t)]
        a = [(A + 1) - (A - 1) * c + t, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - t]
    else:
        b = [A * ((A + 1) - (A - 1) * c + t), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - t)]
        a = [(A + 1) + (A - 1) * c + t, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - t]
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return signal.sosfilt(np.concatenate([b, a])[None, :], x, axis=0)


def taper(x, n=48):
    """cosine fade over the last n samples (in place) so that every rendered note ends at zero."""
    m = min(n, len(x))
    x[-m:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, m)))[(slice(None),) + (None,) * (x.ndim - 1)]
    return x


def gate_env(n, att, dur, rel):
    t = np.arange(n) / SR
    a = np.minimum(t / max(att, 1e-5), 1.0)
    r = np.where(t < dur, 1.0, np.exp(-(t - dur) / (rel / 4.0)))
    return taper(a * r, 64)


def ramp(t, t0, t1, a, b, curve=1.0):
    s = np.clip((t - t0) / (t1 - t0), 0.0, 1.0) ** curve
    return a + (b - a) * s


# ===================================================================== numba DSP
@njit
def _svf(x, fc, k1, k2, mode, poles, drive):
    n = x.shape[0]
    y = np.empty(n)
    ic1 = np.zeros(4)
    ic2 = np.zeros(4)
    for i in range(n):
        f = fc[i]
        if f < 20.0:
            f = 20.0
        if f > 19000.0:
            f = 19000.0
        g = math.tan(math.pi * f / 44100.0)
        s = x[i]
        if drive > 0.0:
            s = math.tanh(s * drive) / drive
        for p in range(poles):
            k = k1 if p == 0 else k2
            a1 = 1.0 / (1.0 + g * (g + k))
            a2 = g * a1
            a3 = g * a2
            s_in = s
            v3 = s_in - ic2[p]
            v1 = a1 * ic1[p] + a2 * v3
            v2 = ic2[p] + a2 * ic1[p] + a3 * v3
            ic1[p] = 2.0 * v1 - ic1[p]
            ic2[p] = 2.0 * v2 - ic2[p]
            if mode == 0:
                s = v2
            elif mode == 1:
                s = v1 * k
            else:
                s = s_in - k * v1 - v2
        y[i] = s
    return y


def svf(x, fc, res=0.3, mode=0, poles=2, drive=0.0, res2=None):
    """TPT state-variable filter. mode 0 lowpass / 1 bandpass (unity peak) / 2 highpass.
    res in 0..0.97 (resonance of the first stage), later stages are Butterworth-ish unless res2 is given."""
    x = np.ascontiguousarray(x, dtype=np.float64)
    fc = np.ascontiguousarray(np.broadcast_to(np.asarray(fc, dtype=np.float64), x.shape))
    k1 = max(2.0 * (1.0 - res), 0.04)
    k2 = 1.41 if res2 is None else max(2.0 * (1.0 - res2), 0.04)
    return _svf(x, fc, k1, k2, mode, poles, float(drive))


def svf2(x, fc, **kw):
    """svf on a stereo (n,2) array."""
    return np.stack([svf(x[:, 0], fc, **kw), svf(x[:, 1], fc, **kw)], 1)


@njit
def _unison(freq, ratios, ph0, gl, gr):
    n = freq.shape[0]
    V = ratios.shape[0]
    out = np.zeros((n, 2))
    ph = ph0.copy()
    for i in range(n):
        fi = freq[i] / 44100.0
        l = 0.0
        r = 0.0
        for v in range(V):
            dt = fi * ratios[v]
            if dt > 0.48:
                dt = 0.48
            p = ph[v]
            s = 2.0 * p - 1.0
            if p < dt:
                t = p / dt
                s -= t + t - t * t - 1.0
            elif p > 1.0 - dt:
                t = (p - 1.0) / dt
                s -= t * t + t + t + 1.0
            l += s * gl[v]
            r += s * gr[v]
            p += dt
            if p >= 1.0:
                p -= 1.0
            ph[v] = p
        out[i, 0] = l
        out[i, 1] = r
    return out


_PH = np.random.default_rng(7).random(96)


def saw_stack(freq, ratios, pan=0.8, seed=0):
    """Band-limited (polyBLEP) saw stack. freq: base frequency per sample (n,), ratios: one entry per voice
    (use Hz with freq=ones for chords). Voices are scattered across the stereo field; mono sum stays solid."""
    ratios = np.asarray(ratios, dtype=np.float64)
    V = len(ratios)
    idx = np.arange(V)
    ph0 = _PH[(idx + seed * 5) % len(_PH)].copy()
    pans = pan * (2.0 * ((idx * 0.6180339887 + 0.137 + 0.31 * seed) % 1.0) - 1.0)
    a = (pans + 1.0) * math.pi / 4.0
    norm = math.sqrt(2.0) / math.sqrt(V)
    return _unison(np.ascontiguousarray(freq, dtype=np.float64), ratios, ph0,
                   np.cos(a) * norm, np.sin(a) * norm)


@njit
def _bus_comp(x, thr, ratio, att, rel, knee):
    n = x.shape[0]
    y = np.empty_like(x)
    gout = np.empty(n)
    ac = 1.0 - math.exp(-1.0 / (att * 44100.0))
    rc = 1.0 - math.exp(-1.0 / (rel * 44100.0))
    env = 0.0
    for i in range(n):
        lvl = max(abs(x[i, 0]), abs(x[i, 1]))
        if lvl > env:
            env += (lvl - env) * ac
        else:
            env += (lvl - env) * rc
        d = 20.0 * math.log10(env + 1e-9)
        over = d - thr
        if over <= -knee / 2.0:
            gr = 0.0
        elif over >= knee / 2.0:
            gr = over * (1.0 - 1.0 / ratio)
        else:
            gr = (over + knee / 2.0) ** 2 / (2.0 * knee) * (1.0 - 1.0 / ratio)
        g = 10.0 ** (-gr / 20.0)
        y[i, 0] = x[i, 0] * g
        y[i, 1] = x[i, 1] * g
        gout[i] = g
    return y, gout


@njit
def _release_smooth(g, rc):
    n = g.shape[0]
    out = np.empty(n)
    cur = 1.0
    for i in range(n):
        up = cur + (1.0 - cur) * rc
        cur = g[i] if g[i] < up else up
        out[i] = cur
    return out


def limiter(x, ceil, look_ms=4.0, rel_ms=70.0, tp=True):
    """Look-ahead peak limiter: forward sliding minimum of the required gain, moving-average smoothing over the
    look-ahead window (guarantees the ceiling), then release smoothing."""
    L = (int(look_ms * SR / 1000.0) // 2) * 2          # even, so that the centred filter can be shifted exactly
    pk = np.max(np.abs(x), axis=1)
    if tp:                                                          # 4x oversampled -> true-peak estimate
        up = signal.resample_poly(x, 4, 1, axis=0)
        pk = np.maximum(pk, np.abs(up).max(axis=1).reshape(-1, 4).max(axis=1)[:len(x)])
    gt = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    # mh[j] = min(gt[j : j+L+1])
    pad = np.concatenate([gt, np.ones(L)])
    mh = minimum_filter1d(pad, size=L + 1, origin=-(L // 2), mode="nearest")[:len(gt)]
    p = np.concatenate([np.full(L, mh[0]), mh])
    cs = np.concatenate([[0.0], np.cumsum(p)])
    ma = (cs[L + 1:L + 1 + len(mh)] - cs[:len(mh)]) / (L + 1)
    g = np.minimum(ma, gt)
    rc = 1.0 - math.exp(-1.0 / (rel_ms / 1000.0 * SR))
    g = _release_smooth(np.ascontiguousarray(g), rc)
    limiter.last_gain = g
    return x * g[:, None]


# ---------------------------------------------------------------- loudness (ITU-R BS.1770 / EBU R128)
def _kw_sos():
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / SR)
    Vh = 10 ** (G / 20)
    Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b1 = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a1 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f0 / SR)
    a0 = 1 + K / Q + K * K
    b2 = [1, -2, 1]
    a2 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    return np.array([b1 + a1, b2 + a2])


def lufs(x):
    """integrated loudness (gated), x: (n,2) float"""
    y = signal.sosfilt(_kw_sos(), x, axis=0)
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    cs = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y * y, axis=0)])
    starts = np.arange(0, len(y) - blk + 1, hop)
    z = (cs[starts + blk] - cs[starts]) / blk
    l = -0.691 + 10 * np.log10(np.maximum(z.sum(axis=1), 1e-12))
    keep = l > -70
    if not keep.any():
        return -70.0
    rel = -0.691 + 10 * np.log10(np.mean(z[keep].sum(axis=1))) - 10
    keep = l > max(rel, -70)
    return -0.691 + 10 * np.log10(np.mean(z[keep].sum(axis=1)))


# ===================================================================== reverb / delay
def make_ir(rt60, length, seed, predelay=0.0, hp_hz=200.0, lp_hz=9000.0, damp=0.5, split=1500.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    out = np.zeros((n, 2))
    for c in range(2):
        w = rng.standard_normal(n)
        lo = lp(w, split, 2)
        hi = w - lo
        d_lo = 10 ** (-3.0 * t / rt60)
        d_hi = 10 ** (-3.0 * t / (rt60 * (1.0 - 0.6 * damp)))
        x = lo * d_lo * 1.4 + hi * d_hi * 0.8
        x *= np.minimum(t / 0.004, 1.0)
        # a few early reflections
        for _ in range(7):
            k = int(rng.uniform(0.004, 0.045) * SR)
            x[k] += rng.choice([-1, 1]) * rng.uniform(0.5, 1.0) * np.std(x[:2000]) * 4
        out[:, c] = x
    out = hp(out, hp_hz, 2)
    out = lp(out, lp_hz, 2)
    pd = int(predelay * SR)
    if pd:
        out = np.concatenate([np.zeros((pd, 2)), out])[:n]
    out /= np.sqrt(np.sum(out ** 2, axis=0, keepdims=True))
    return out


def conv_rev(x, ir):
    if x.ndim == 1:
        xl = xr = x
    else:
        xl, xr = x[:, 0], x[:, 1]
    yl = signal.fftconvolve(xl, ir[:, 0])[:NS]
    yr = signal.fftconvolve(xr, ir[:, 1])[:NS]
    return np.stack([yl, yr], 1)


def pingpong(x, time_s, fb, wet, reps=6, lp_hz=5500.0):
    d = int(round(time_s * SR))
    out = np.zeros_like(x)
    for r in range(1, reps + 1):
        sh = r * d
        if sh >= NS:
            break
        src = x[:, ::-1] if r % 2 == 1 else x
        out[sh:] += src[:NS - sh] * (fb ** (r - 1)) * wet
    return lp(out, lp_hz, 2)


# ===================================================================== sound sources
def make_kick():
    """Hard-techno kick: pitch-enveloped body (177 Hz -> A1 = 55 Hz tail), heavy saturation, long clean sub tail,
    pitch-swept click + noise transient on top. Mono, exactly one beat long, silent again before the next beat."""
    L = BEAT
    t = np.arange(L) / SR
    f = 55.0 + 32.0 * np.exp(-t / 0.045) + 90.0 * np.exp(-t / 0.008)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph)
    att = np.sin(np.minimum(t / 0.0007, 1.0) * np.pi / 2)
    drv = np.exp(-np.maximum(t - 0.040, 0) / 0.165)
    y = np.tanh(5.5 * body * drv)
    y = np.tanh(1.7 * y) / np.tanh(1.7)
    y *= (0.62 + 0.38 * np.exp(-t / 0.030)) * np.exp(-t / 0.30)
    y += 0.62 * body * np.exp(-t / 0.23)                         # clean sub tail
    fc = 300.0 + 2400.0 * np.exp(-t / 0.0025)                    # fast pitch-envelope click
    click = np.sin(2 * np.pi * np.cumsum(fc) / SR) * np.exp(-t / 0.004) * 0.55
    click += hp(noise(L, 11), 1800, 2) * np.exp(-t / 0.0011) * 0.5
    y = y * att + click * np.minimum(t / 0.00015, 1.0)
    y = hp(y, 22, 2)
    y *= np.where(t > 0.34, 0.5 + 0.5 * np.cos(np.pi * np.clip((t - 0.34) / 0.06, 0, 1)), 1.0)   # tail is gone before the next beat
    y[-1] = 0.0
    return y / np.max(np.abs(y))


def make_clap(seed=0, vel=1.0):
    L = int(0.36 * SR)
    t = np.arange(L) / SR
    nz = noise(L, 100 + seed)
    x = svf(nz, 1750.0, res=0.5, mode=1, poles=2) * 1.2
    env = np.zeros(L)
    for d, a in ((0.0, 0.85), (0.0095, 0.8), (0.0188, 0.85), (0.028, 0.0)):
        m = t >= d
        env[m] += a * np.exp(-(t[m] - d) / 0.0045)
    tail = np.exp(-np.maximum(t - 0.028, 0) / 0.075) * (t >= 0.028) * 0.9
    env = env + tail
    y = x * env + hp(nz, 6000, 2) * env * 0.12
    y += np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.02) * 0.25
    y = np.tanh(1.8 * y) * np.minimum(t / 0.0003, 1.0)
    y = hp(y, 260, 2)
    taper(y, 200)
    return y * vel / np.max(np.abs(y))


def make_snare(f0=190.0, seed=0, dur=0.16):
    L = int(dur * SR)
    t = np.arange(L) / SR
    tone = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.35 * np.exp(-t / 0.012))) / SR) * np.exp(-t / 0.045)
    nz = noise(L, 300 + seed)
    nb_ = svf(nz, 3300.0, res=0.35, mode=1, poles=2) * np.exp(-t / 0.05) * 1.3
    nh = hp(nz, 7000, 2) * np.exp(-t / 0.035) * 0.35
    y = np.tanh(1.6 * (0.7 * tone + nb_ + nh)) * np.minimum(t / 0.0004, 1.0)
    y = hp(y, 120, 2)
    taper(y, 120)
    return y / np.max(np.abs(y))


def make_rim(vel=1.0):
    L = int(0.07 * SR)
    t = np.arange(L) / SR
    y = np.sin(2 * np.pi * 1820 * t) * np.exp(-t / 0.0055) * 0.45
    y += np.sin(2 * np.pi * np.cumsum(520 * (1 + 0.25 * np.exp(-t / 0.004))) / SR) * np.exp(-t / 0.018) * 0.7
    y += hp(noise(L, 41), 3000, 2) * np.exp(-t / 0.0025) * 0.35
    y = np.tanh(1.5 * y) * np.minimum(t / 0.0002, 1.0)
    taper(y, 80)
    return y * vel / np.max(np.abs(y))


_MET = np.array([205.3, 304.4, 369.6, 522.7, 540.0, 800.0])


def metal(n, scale, seed):
    t = np.arange(n) / SR
    ph0 = np.random.default_rng(seed).random(6)
    x = np.zeros(n)
    for f, p in zip(_MET * scale, ph0):
        x += np.sign(np.sin(2 * np.pi * (f * t + p)))
    return x / 6.0


def hat_closed(vel=1.0, seed=0, dur=0.08):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = 0.75 * noise(n, 500 + seed) + 0.45 * metal(n, 2.6, seed)
    x = hp(x, 6800, 4)
    env = np.minimum(t / 0.0004, 1.0) * np.exp(-t / (0.010 + 0.006 * vel))
    y = x * env
    taper(y, 80)
    return y * vel


def hat_open(vel=1.0, seed=0, dur=0.20):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = 0.7 * noise(n, 700 + seed) + 0.5 * metal(n, 2.3, seed + 3)
    x = hp(x, 5200, 4)
    env = np.minimum(t / 0.0006, 1.0) * (0.35 * np.exp(-t / 0.018) + 0.65 * np.exp(-t / 0.07))
    y = x * env
    taper(y, 1000)
    return y * vel


def shaker(vel=1.0, seed=0, dur=0.09):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = lp(hp(noise(n, 900 + seed), 4200, 2), 12500, 2)
    env = np.minimum(t / 0.004, 1.0) * np.exp(-t / 0.026)
    y = x * env
    taper(y, 200)
    return y * vel


def ride(vel=1.0, seed=0, dur=0.34):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    rng = np.random.default_rng(1100 + seed)
    for f in (3150, 4230, 5470, 6870, 8340, 10100):
        y += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * 0.25
    y += hp(noise(n, 1200 + seed), 7500, 2) * 0.35
    y *= np.minimum(t / 0.0005, 1.0) * (0.4 * np.exp(-t / 0.012) + 0.6 * np.exp(-t / 0.11))
    taper(y, 400)
    return y * vel


def crash(dur=2.6, seed=0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = 0.8 * noise(n, 1300 + seed) + 0.6 * metal(n, 3.1, 5 + seed)
    x = hp(x, 2800, 4)
    env = np.minimum(t / 0.001, 1.0) * (0.45 * np.exp(-t / 0.10) + 0.55 * np.exp(-t / 0.75))
    y = x * env
    taper(y, 2000)
    return y / np.max(np.abs(y))


def rev_crash(dur, seed, rt=0.6):
    """reversed crash (through a bright plate) - swells and ends exactly at its last sample."""
    n = int(dur * SR)
    c = crash(dur, seed=seed)
    wet = signal.fftconvolve(c, make_ir(rt, 0.6, 77 + seed, hp_hz=300, lp_hz=14000)[:, 0])[:n]
    r = wet[::-1].copy()
    r *= np.linspace(0, 1, n) ** 1.6
    r *= np.minimum(np.arange(n) / (0.02 * SR), 1.0)
    return r


def sub_boom(dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 27.5 + 55.0 * np.exp(-t / 0.07) + 40.0 * np.exp(-t / 0.03)       # lands on A0 = exactly one octave under the kick tail
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.tanh(2.4 * np.sin(ph)) * np.exp(-t / 0.30) * np.clip((t - 0.012) / 0.10, 0.0, 1.0) ** 1.6   # swells in under the kick, gone by the next one
    y = hp(y, 20, 2)
    taper(y, 2000)
    return y / np.max(np.abs(y))


def make_stab(notes, dur, vel=1.0, cut0=650.0, cut_amt=6000.0, tau=0.055, res=0.4, spread=0.26, V=7,
              hp_hz=170.0, seed=0, body_tau=0.14):
    n = int((dur + 0.10) * SR)
    t = np.arange(n) / SR
    det = (np.arange(V) - (V - 1) / 2) / ((V - 1) / 2) * spread
    ratios = np.array([float(mtof(m)) * 2 ** (d / 12) for m in notes for d in det])
    s = saw_stack(np.ones(n), ratios, pan=0.9, seed=seed)
    cut = cut0 + cut_amt * np.exp(-t / tau)
    s = svf2(s, cut, res=res, poles=2)
    env = gate_env(n, 0.001, dur, 0.06) * (0.5 + 0.5 * np.exp(-t / body_tau))
    s = s * env[:, None] * vel
    return hp(s, hp_hz, 2)


def make_pluck(freq, dur, vel=1.0, cut0=900.0, cut_amt=4200.0, tau=0.045, res=0.55, seed=0):
    n = int((dur + 0.05) * SR)
    t = np.arange(n) / SR
    ratios = np.array([1.0 * 2 ** (-0.12 / 12), 1.0, 2 ** (0.12 / 12)])
    s = saw_stack(np.full(n, float(freq)), ratios, pan=0.5, seed=seed)
    cut = cut0 + cut_amt * np.exp(-t / tau)
    s = svf2(s, cut, res=res, poles=2)
    env = gate_env(n, 0.0008, dur, 0.02) * np.exp(-t / 0.10)
    return s * env[:, None] * vel


def make_bass_note(freq, dur, vel, cut0, cut_amt, tau, res=0.5, drive=2.2, sub=0.0, seed=0):
    n = int((dur + 0.03) * SR)
    t = np.arange(n) / SR
    f = freq * (1 + 0.05 * np.exp(-t / 0.010))
    s = saw_stack(f, [1.0 * 2 ** (-0.05 / 12), 2 ** (0.05 / 12)], pan=0.0, seed=seed)
    x = 0.5 * (s[:, 0] + s[:, 1])
    cut = cut0 + cut_amt * np.exp(-t / tau)
    y = svf(x, cut, res=res, poles=2, drive=1.2)
    y = np.tanh(drive * y) / np.tanh(drive)
    if sub:
        y += sub * np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = gate_env(n, 0.0025, dur, 0.016) * (0.62 + 0.38 * np.exp(-t / 0.09))
    return y * env * vel


def make_acid(freq, dur, accent, slide_from=None, seed=0):
    n = int((dur + 0.03) * SR)
    t = np.arange(n) / SR
    f = np.full(n, float(freq))
    if slide_from:
        f = freq * (slide_from / freq) ** np.exp(-t / 0.035)
    s = saw_stack(f, [1.0], pan=0.0, seed=seed)
    x = s[:, 0]
    cut = 350.0 + (1500.0 + 2600.0 * accent) * np.exp(-t / (0.09 + 0.05 * accent))
    y = svf(x, cut, res=0.9, poles=2, res2=0.85, drive=1.5)
    y = np.tanh(1.8 * y)
    env = gate_env(n, 0.001, dur, 0.012)
    return y * env * (0.7 + 0.5 * accent)


def riser_amp(t_abs):
    """riser level (linear, 1.0 = loudest) vs absolute time: -32 dB at 3.2 s rising to -10 dB at 6.0 s (build),
    then a quick 10 dB swell across the gap to 0 dB exactly at 6.4 s (drop)."""
    t_abs = np.asarray(t_abs, dtype=float)
    sb = np.clip((t_abs - 3.2) / 2.8, 0, 1)
    sg = np.clip((t_abs - 6.0) / 0.4, 0, 1)
    d = np.where(t_abs < 6.0, -32.0 + 22.0 * sb ** 1.3, -10.0 + 10.0 * sg ** 1.4)
    return 10.0 ** (d / 20.0)


def riser_noise(dur, t0=3.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = t / dur
    out = np.zeros((n, 2))
    fc = 260.0 * (11000.0 / 260.0) ** (s ** 1.25)
    for c in range(2):
        w = noise(n, 1500 + c)
        y = svf(w, fc, res=0.82, mode=1, poles=2) * 0.45
        y += hp(w, 3000.0, 2) * s ** 3 * 0.35
        out[:, c] = y
    return out * riser_amp(t0 + t)[:, None]


def downsweep(dur=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = t / dur
    fc = 13000.0 * (260.0 / 13000.0) ** (s ** 0.7)
    out = np.zeros((n, 2))
    for c in range(2):
        w = noise(n, 1600 + c)
        out[:, c] = svf(w, fc, res=0.7, mode=1, poles=2) * np.exp(-t / 0.28) * np.minimum(t / 0.002, 1.0)
    taper(out, 1500)
    return out / np.max(np.abs(out))


def pitch_zap(dur=0.22):
    """short pitch-fall fill: falls from ~3 kHz to ~70 Hz and lands (silent) exactly at the loop point."""
    n = int(dur * SR)
    s = np.arange(n) / n
    f = 70.0 + 2900.0 * (1.0 - s) ** 3.2
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.tanh(2.2 * np.sin(ph)) * 0.8 + 0.4 * np.sin(ph * 0.5)
    env = np.minimum(s / 0.04, 1.0) * (1.0 - s) ** 0.8
    nz = hp(noise(n, 1700), 2500, 2) * (1 - s) ** 3 * 0.35
    y = (y + nz) * env
    return y / np.max(np.abs(y))


# ===================================================================== sidechain curves
def duck_curve(kick_beats, depth, tau, look=0.004, from_beat=0, virtual_end=0.03, rec=0.4, shape="exp", power=1.6):
    """Sidechain gain curve: dips to (1-depth) on each kick (4 ms look-ahead), then recovers.
    shape "exp": 1 - depth*exp(-t/tau);  shape "ramp": power-law ramp that reaches 1.0 after `tau` seconds (rolling-bass
    style pump: the first 16th after the kick is nearly muted, the later ones bloom).
    A virtual kick at the loop point (16.0 s) ducks the last `virtual_end` seconds."""
    g = np.ones(NS)
    Lk = int(look * SR)
    n_rec = int(rec * SR)
    tt = np.arange(n_rec) / SR
    if shape == "exp":
        post = 1.0 - depth * np.exp(-tt / tau)
    else:
        post = (1.0 - depth) + depth * np.minimum(tt / tau, 1.0) ** power
    pre = 1.0 - depth * 0.5 * (1.0 - np.cos(np.pi * np.arange(Lk) / Lk))
    seg = np.concatenate([pre, post])
    for k in kick_beats:
        if k < from_beat:
            continue
        a = k * BEAT - Lk
        lo, hi = max(a, 0), min(a + len(seg), NS)
        g[lo:hi] = np.minimum(g[lo:hi], seg[lo - a:hi - a])
    if virtual_end:
        Lv = int(virtual_end * SR)
        pv = 1.0 - depth * 0.5 * (1.0 - np.cos(np.pi * np.arange(Lv) / Lv))
        g[NS - Lv:] = np.minimum(g[NS - Lv:], pv)
    return g


# ===================================================================== arrangement / render
def render_stems():
    """Synthesises every stem. Returns dict of stereo (NS,2) float arrays and the events dict."""
    ev = get_events()
    T = np.arange(NS) / SR
    z = lambda: np.zeros((NS, 2))
    kick, sub, bass, rim_b = z(), z(), z(), z()
    clap_b, snare_b, hats, perc = z(), z(), z(), z()
    stab, arp, pad, lead, acid = z(), z(), z(), z(), z()
    fx, boom_b, riser = z(), z(), z()
    plate_in, hall_in, fx_in = z(), z(), z()

    # ------------------------------------------------------------------ kick (every beat except the gap)
    K = make_kick()
    kick_mono = np.zeros(NS)
    for k in KICK_BEATS:
        kick_mono[k * BEAT:k * BEAT + BEAT] += K
    kick[:, 0] = kick[:, 1] = kick_mono

    # ------------------------------------------------------------------ rumble (kick -> low-passed reverb)
    ir_r = make_ir(0.85, 1.7, 31, predelay=0.006, hp_hz=30.0, lp_hz=1000.0, damp=0.0, split=300.0)
    ir_r = lp(ir_r, 130.0, 2)
    ir_r = hp(ir_r, 34.0, 2)
    rum = signal.fftconvolve(kick_mono, ir_r[:, 0])[:NS]
    rum = lp(hp(rum, 36.0, 2), 150.0, 2)
    rum /= np.max(np.abs(rum))
    rum = rum * np.interp(T, [0, 5.75, 5.98, 6.4, 6.401, 16], [1, 1, 0, 0, 1, 1])
    rumble = np.stack([rum, rum], 1)

    # ------------------------------------------------------------------ sub (intro / build off-beat sub, drop boom)
    def sub_note(freq, dur, vel):
        n = int((dur + 0.02) * SR)
        t = np.arange(n) / SR
        f = freq * (1 + 0.5 * np.exp(-t / 0.02))
        y = np.tanh(1.8 * np.sin(2 * np.pi * np.cumsum(f) / SR))
        return y * gate_env(n, 0.003, dur, 0.02) * vel
    for bar in range(0, 4):
        for beat in range(4):
            kb = bar * 4 + beat
            if kb >= GAP_BEAT:
                continue
            put(sub, sub_note(55.0, 0.17, 0.8), (kb * 4 + 2) * STEP)

    # ------------------------------------------------------------------ rolling bounce bass (drop + outro, build tease)
    for bar in range(2, 10):
        root = mtof(CHORDS[CHORD_BAR[bar]]["root"])
        for beat in range(4):
            kb = bar * 4 + beat
            if kb == GAP_BEAT:
                continue
            chord = chord_at_beat(kb)
            root = float(mtof(CHORDS[chord]["root"]))
            for pos in range(4):
                t0 = (kb * 4 + pos) * STEP
                tsec = t0 / SR
                if bar == 2:
                    # build bar 1: only off-beat 8th bass, filter closed
                    if pos != 2:
                        continue
                    nt = make_bass_note(root, 0.16, 0.8, 300, 500, 0.05, seed=pos)
                    put(bass, nt, t0)
                    continue
                if bar == 3:
                    if beat == 3:
                        continue
                    if pos == 0:
                        continue
                    s = (tsec - 4.8) / 1.2
                    cut0 = 300 + 1600 * s
                    f_ = root * (2.0 if pos == 2 else 1.0)
                    nt = make_bass_note(f_, 0.085, 0.75 + 0.25 * s, cut0, 1200 + 1500 * s, 0.05, seed=pos)
                    put(bass, nt, t0)
                    continue
                if bar == 9:
                    if pos != 2 or beat >= 3:
                        continue
                    nt = make_bass_note(root * 2, 0.17, 0.55, 260, 500, 0.05, seed=pos)
                    put(bass, nt, t0)
                    continue
                if pos == 0:
                    continue
                f_ = root * (2.0 if pos == 2 else 1.0)
                if beat == 3 and pos == 3:
                    f_ = root * 1.5                                   # fifth, turnaround
                vel = {1: 0.95, 2: 1.0, 3: 0.9}[pos]
                gain = 1.0 if bar < 8 else 0.85
                cut0 = {1: 330, 2: 520, 3: 380}[pos]
                amt = {1: 900, 2: 3300, 3: 1500}[pos]
                dd = 0.088 if pos != 2 else 0.095
                nt = make_bass_note(f_, dd, vel * gain, cut0, amt, 0.045, seed=pos)
                put(bass, nt, t0)

    # ------------------------------------------------------------------ drums: clap / rim / snare roll
    clap_t = [k * BEAT for k in CLAP_BEATS]
    for i, t0 in enumerate(clap_t):
        kb = t0 // BEAT
        if kb < 16:
            v = 0.65 + 0.12 * (kb - 9) / 2.0
        elif kb < 32:
            v = 1.0
        else:
            v = {33: 0.8, 35: 0.6, 37: 0.45}[kb]
        c = make_clap(seed=i, vel=v)
        put(clap_b, c, t0, 1.0, pan=0.0)
        put(plate_in, c, t0, 0.55 * v, pan=0.0)
    for kb in [17, 19, 21, 23, 25, 27, 29, 31, 33, 35]:
        put(rim_b, make_rim(0.6), kb * BEAT, 1.0, pan=0.12)
        put(plate_in, make_rim(0.6), kb * BEAT, 0.4)
    for bar in (6, 7):
        put(rim_b, make_rim(0.35), (bar * 16 + 14) * STEP, 1.0, pan=-0.3)
    put(rim_b, make_rim(0.35), (1 * 16 + 14) * STEP, 1.0, pan=-0.2)          # intro bar 2 ghost

    sr_times = snare_roll_times()
    for i, t0 in enumerate(sr_times):
        s = i / (len(sr_times) - 1)
        sn = make_snare(f0=170 + 190 * s, seed=i, dur=0.13)
        v = 0.38 + 0.62 * s
        put(snare_b, sn, t0, v)
        put(plate_in, sn, t0, 0.7 * v)

    # ------------------------------------------------------------------ hats / shaker / ride
    def hat_plan(bar, beat, pos):
        """-> list of (kind, vel)"""
        out = []
        if bar == 0:
            if pos == 2:
                out.append(("c", 0.33))
        elif bar == 1:
            if pos == 2:
                out.append(("c", 0.42))
            if pos in (1, 3) and beat in (1, 3):
                out.append(("c", 0.16))
        elif bar == 2:
            if pos in (1, 3):
                out.append(("c", 0.5 if pos == 1 else 0.38))
            if pos == 2:
                out.append(("o", 0.5 + 0.06 * beat))
            out.append(("s", 0.3 + 0.07 * beat + (0.12 if pos == 2 else 0)))
        elif bar == 3:
            if beat < 3:
                s = ((beat * 4 + pos) / 12.0)
                out.append(("c", 0.45 + 0.5 * s))
                out.append(("s", 0.5 + 0.4 * s))
        elif 4 <= bar <= 7:
            if pos == 1:
                out.append(("c", 0.5))
            if pos == 3:
                out.append(("c", 0.62))
            if pos == 2:
                out.append(("o", 0.8))
                if bar >= 6:
                    out.append(("r", 0.42))
            if pos == 0 and bar >= 6:
                out.append(("c", 0.2))
            out.append(("s", {0: 0.5, 1: 0.28, 2: 0.78, 3: 0.3}[pos]))
        elif bar == 8:
            if pos == 1:
                out.append(("c", 0.36))
            if pos == 3:
                out.append(("c", 0.42))
            if pos == 2:
                out.append(("o", 0.5))
            out.append(("s", {0: 0.28, 1: 0.18, 2: 0.4, 3: 0.2}[pos]))
        elif bar == 9:
            if beat < 2:
                if pos == 2:
                    out.append(("o", 0.34 - 0.1 * beat))
                if pos in (1, 3):
                    out.append(("c", 0.2 - 0.08 * beat))
        return out

    hcount = 0
    hrng = np.random.default_rng(21)
    for bar in range(10):
        for beat in range(4):
            kb = bar * 4 + beat
            if kb == GAP_BEAT:
                continue
            for pos in range(4):
                t0 = (kb * 4 + pos) * STEP
                for kind, v in hat_plan(bar, beat, pos):
                    hcount += 1
                    v = v * (1.0 + 0.14 * (hrng.random() - 0.5))            # subtle velocity humanisation (grid stays exact)
                    pan = 0.28 * (1 if (pos + beat) % 2 == 0 else -1)
                    if kind == "c":
                        h = hat_closed(v, seed=hcount)
                        put(hats, h, t0, 1.0, pan=pan)
                    elif kind == "o":
                        h = hat_open(v, seed=hcount)
                        put(hats, h, t0, 1.0, pan=-pan)
                        put(plate_in, h, t0, 0.25)
                    elif kind == "s":
                        h = shaker(v, seed=hcount)
                        put(perc, h, t0, 1.0, pan=-pan * 1.4)
                    elif kind == "r":
                        h = ride(v, seed=hcount)
                        put(perc, h, t0, 1.0, pan=0.35)
                        put(plate_in, h, t0, 0.2)

    # ------------------------------------------------------------------ pad / drone
    for bar in range(10):
        a0 = bar * BAR
        a1 = a0 + BAR
        if bar == 3:
            seg_len = int(1.2 * SR)                      # ends at 6.0 s (beats 12-14 only)
        else:
            seg_len = BAR
        if bar == 3:
            # chord changes F -> G at beat 14
            parts = [("F", 0, 2 * BEAT), ("G", 2 * BEAT, BEAT)]
        else:
            parts = [(CHORD_BAR[bar], 0, seg_len)]
        for ch, off, ln in parts:
            notes = CHORDS[ch]["stab"]
            n = ln
            V = 5
            det = (np.arange(V) - 2) / 2.0 * 0.15
            ratios = np.array([float(mtof(m)) * 2 ** (d / 12) for m in notes for d in det])
            s = saw_stack(np.ones(n), ratios, pan=0.9, seed=3)
            tsec = (a0 + off + np.arange(n)) / SR
            if bar < 2:
                cut = 380 + 260 * (tsec / 3.2)
                lvl = 0.35 + 0.2 * tsec / 3.2
            elif bar < 4:
                cut = ramp(tsec, 3.2, 6.0, 500, 4500, 1.5)
                lvl = ramp(tsec, 3.2, 6.0, 0.55, 0.9)
            elif bar < 8:
                cut = 1500 + 0 * tsec
                lvl = 0.8 + 0 * tsec
            else:
                cut = 1500 + 0 * tsec
                lvl = ramp(tsec, 12.8, 15.4, 0.75, 0.1)
            s = svf2(s, cut, res=0.25, poles=2)
            e = np.minimum(np.arange(n) / (0.004 * SR), 1.0)
            e = np.minimum(e, np.minimum((n - np.arange(n)) / (0.01 * SR), 1.0))
            s = hp(s, 170.0, 2) * (e * lvl)[:, None]
            put(pad, s, a0 + off)

    # ------------------------------------------------------------------ chord stabs
    def add_stab(t0, chord, dur_steps, vel, **kw):
        s = make_stab(CHORDS[chord]["stab"], dur_steps * STEP / SR, vel, **kw)
        put(stab, s, t0)
        put(hall_in, s, t0, 0.5)

    # intro hook: A minor stab on the very first sample, again at the start of bar 2
    add_stab(0, "Am", 1.6, 0.9, cut0=500, cut_amt=5200, tau=0.05)
    add_stab(BAR, "Am", 1.2, 0.6, cut0=450, cut_amt=3500, tau=0.05)
    # build accents on the word beats (3.2 / 4.0 / 4.8 / 5.6 s)
    add_stab(8 * BEAT, "Am", 2.2, 0.9, cut0=600, cut_amt=5500)
    add_stab(10 * BEAT, "Am", 2.2, 0.8, cut0=700, cut_amt=5500)
    add_stab(12 * BEAT, "F", 2.2, 0.85, cut0=800, cut_amt=5500)
    for i in range(4):                                                  # glitch stutter at 5.6 s
        add_stab(14 * BEAT + i * (BEAT // 8), "G", 0.9 - 0.12 * i, 0.9 - 0.1 * i, cut0=900, cut_amt=5000)
    # drop
    add_stab(16 * BEAT, "Am", 4.0, 1.15, cut0=900, cut_amt=7000, tau=0.09, body_tau=0.3)
    for bar in range(4, 9):
        ch = CHORD_BAR[bar]
        for st_, v in STAB_STEPS[bar]:
            add_stab((bar * 16 + st_) * STEP, ch, 1.5, v * 0.95)

    # ------------------------------------------------------------------ arpeggio
    for bar in range(2, 9):
        for step in range(16):
            kb = bar * 4 + step // 4
            if kb == GAP_BEAT:
                continue
            if bar == 3 and kb >= 15:
                continue
            t0 = (bar * 16 + step) * STEP
            tsec = t0 / SR
            chord = chord_at_beat(kb)
            ntones = CHORDS[chord]["arp"]
            midi = ntones[ARP_PAT[step]]
            accent = (1.0 if step % 4 == 2 else 0.68) * (1.0 + 0.10 * (hrng.random() - 0.5))
            if bar == 2:
                cb, lvl = ramp(tsec, 3.2, 4.8, 500, 1200), ramp(tsec, 3.2, 4.8, 0.35, 0.55)
            elif bar == 3:
                cb, lvl = ramp(tsec, 4.8, 6.0, 1200, 5200), ramp(tsec, 4.8, 6.0, 0.55, 0.9)
            elif bar < 8:
                cb, lvl = 1500.0, 1.0
            else:
                cb, lvl = 1500.0, ramp(tsec, 12.8, 14.4, 0.7, 0.2)
            if bar in (6, 7):
                lvl *= 0.85
            p = make_pluck(float(mtof(midi)), 0.085, vel=lvl * accent, cut0=cb, cut_amt=1800 + 2600 * accent,
                           seed=step)
            put(arp, p, t0)
            put(hall_in, p, t0, 0.45)

    # ------------------------------------------------------------------ melodic lead (bars 7-8) + build lead
    for bar, notes in LEAD_HOOK.items():
        for st_, midi, ln in notes:
            t0 = (bar * 16 + st_) * STEP
            dur = ln * STEP / SR * 0.95
            n = int((dur + 0.12) * SR)
            t = np.arange(n) / SR
            vib = 1 + 0.0035 * np.sin(2 * np.pi * 5.6 * t) * np.minimum(t / 0.15, 1.0)
            f0 = float(mtof(midi))
            det = np.linspace(-0.17, 0.17, 7)
            L1 = saw_stack(f0 * vib, 2 ** (det / 12), pan=0.8, seed=1)
            L2 = saw_stack(2 * f0 * vib, 2 ** (det[1:-1] / 12), pan=0.5, seed=2)
            x = L1 + 0.32 * L2
            cut = 2600 + 4200 * np.exp(-t / 0.12)
            x = svf2(x, cut, res=0.3, poles=2)
            e = gate_env(n, 0.003, dur, 0.09)
            x = hp(x * e[:, None], 220, 2)
            put(lead, x, t0, 1.0)
            put(hall_in, x, t0, 0.55)

    # pitch-rising lead in the build (4.0 -> 6.0 s)
    tl0, tl1 = int(4.0 * SR), int(6.0 * SR)
    n = tl1 - tl0
    s = np.arange(n) / n
    f = 220.0 * 2 ** (2.0 * s ** 1.5)
    det = np.linspace(-0.22, 0.22, 7)
    x = saw_stack(f, 2 ** (det / 12), pan=0.9, seed=4)
    cut = 900 * (9000 / 900) ** (s ** 1.2)
    x = svf2(x, cut, res=0.35, poles=2)
    amp = (0.25 + 0.75 * s ** 1.3) * np.minimum(np.arange(n) / (0.05 * SR), 1.0)
    amp *= np.minimum((n - np.arange(n)) / (0.03 * SR), 1.0)
    x = hp(x * amp[:, None], 250, 2)
    put(lead, x, tl0, 0.9)
    put(hall_in, x, tl0, 0.4)

    # ------------------------------------------------------------------ acid line (drop bars 5-6, optional colour)
    if True:                                                           # set False to drop the acid colour
        acid_pat = [(0, 0), (3, 0), (4, 12), (7, 0), (8, 0), (10, 7), (12, 0), (14, 99)]
        for bar in (4, 5):
            root = CHORDS[CHORD_BAR[bar]]["root"] + 12
            sev = {"Am": 10, "F": 11, "C": 11, "G": 10}[CHORD_BAR[bar]]        # 7th of the A-minor scale
            for st_, semi in acid_pat:
                f_ = float(mtof(root + (sev if semi == 99 else semi)))
                t0 = (bar * 16 + st_) * STEP
                a = 1.0 if st_ in (3, 10, 14) else 0.0
                a_ = make_acid(f_, 0.085, a, seed=st_)
                put(acid, a_, t0, 0.8, pan=0.25)

    # ------------------------------------------------------------------ FX: riser, reverse crash, impact
    r0 = int(3.2 * SR)
    r_len = int(6.4 * SR) - r0
    rn = riser_noise(r_len / SR, 3.2)
    rn *= np.minimum((r_len - np.arange(r_len)) / (0.003 * SR), 1.0)[:, None]
    put(riser, rn, r0, 1.0)
    # tonal air whistle riser
    tt = np.arange(r_len) / SR
    sw = tt / (r_len / SR)
    fw = 500.0 * (6000.0 / 500.0) ** sw
    wh = np.sin(2 * np.pi * np.cumsum(fw) / SR) * riser_amp(3.2 + tt) * 0.16
    wh *= np.minimum((r_len - np.arange(r_len)) / (0.003 * SR), 1.0)
    put(riser, wh, r0, 1.0, pan=0.0)

    cr = crash(2.6, seed=1)
    put(fx, cr, int(3.2 * SR), 0.35)                       # build crash
    put(fx_in, cr, int(3.2 * SR), 0.5)
    rc_len = int(1.2 * SR)
    put(fx, rev_crash(1.2, 2), int(6.4 * SR) - rc_len, 2.6, pan=0.0)    # reverse crash ends exactly at 6.4 s

    # impact at 6.4 s: sub boom + crash + snap + shock sweep
    imp = int(6.4 * SR)
    put(boom_b, sub_boom(1.6), imp, 1.2)
    cr2 = crash(3.0, seed=3)
    put(fx, cr2, imp, 1.0)
    put(fx_in, cr2, imp, 0.55)
    snap = hp(noise(int(0.06 * SR), 1800), 800, 2) * np.exp(-np.arange(int(0.06 * SR)) / SR / 0.012)
    put(fx, snap, imp, 0.9)
    ds = downsweep(1.1)
    put(fx, ds, imp, 0.6)
    # fill: pitch fall at the very end (lands, silent, on the loop point)
    zap = pitch_zap(0.22)
    put(fx, zap, NS - len(zap), 0.6)
    # hook hit on the very first beat: short crash tail under the first kick
    put(fx, crash(0.9, seed=5), 0, 0.28)
    # phrase fill into the lead bars: 1/16 snare roll in beat 23 (9.2 s), reverse crash 8.8 -> 9.6, crash on 9.6
    for i in range(4):
        t0 = 23 * BEAT + i * STEP
        sn = make_snare(f0=215 + 35 * i, seed=40 + i, dur=0.12)
        put(snare_b, sn, t0, 0.55 + 0.12 * i)
        put(plate_in, sn, t0, 0.5)
    put(fx, rev_crash(0.8, 6), int(9.6 * SR) - int(0.8 * SR), 1.6)
    put(fx, crash(1.6, seed=7), int(9.6 * SR), 0.30)
    put(fx_in, crash(1.6, seed=7), int(9.6 * SR), 0.30)
    put(fx, downsweep(1.0), int(12.8 * SR), 0.28)
    # small downbeat accent at the start of the outro
    put(fx, crash(1.2, seed=4), int(12.8 * SR), 0.3)

    stems = dict(kick=kick, sub=sub, rumble=rumble, bass=bass, clap=clap_b, rim=rim_b, snare=snare_b, hats=hats,
                 perc=perc, stab=stab, arp=arp, pad=pad, lead=lead, acid=acid, fx=fx, boom=boom_b, riser=riser,
                 plate_in=plate_in, hall_in=hall_in, fx_in=fx_in)
    return stems, ev


# ===================================================================== mix
def _widen(x, delay_ms=11.0, amt=0.7, hp_hz=300.0):
    """Mono-safe widener: adds delayed copy to L and its inverse to R (cancels in the mono sum)."""
    m = 0.5 * (x[:, 0] + x[:, 1])
    d = int(delay_ms * SR / 1000)
    dl = np.concatenate([np.zeros(d), m[:-d]])
    dl = hp(dl, hp_hz, 2) * amt
    out = x.copy()
    out[:, 0] += dl
    out[:, 1] -= dl
    return out


def mix_stems(st):
    kb = KICK_BEATS
    T = np.arange(NS) / SR

    # sidechain curves
    d_bass = duck_curve(kb, 0.94, 0.27, shape="ramp", power=1.5)
    d_pad = duck_curve(kb, 0.85, 0.30, shape="ramp", power=1.3)
    d_stab = duck_curve(kb, 0.62, 0.095)
    d_arp = duck_curve(kb, 0.55, 0.09)
    d_lead = duck_curve(kb, 0.45, 0.09)
    d_rum = duck_curve(kb, 0.97, 0.115, look=0.002)
    d_boom = duck_curve(kb, 0.85, 0.30, from_beat=17)
    d_hat = duck_curve(kb, 0.18, 0.05)

    def outro_filter(x):
        """filter closes over the outro (12.8 -> 15.6 s: 19 kHz -> 170 Hz); music stems fade out by 15.7 s so that only
        the kick and the final fill remain."""
        s0 = int(12.7 * SR)
        n = NS - s0
        tt = np.arange(n) / SR
        sq = np.clip((tt - 0.1) / 2.8, 0, 1)
        cut = 19000 * (170.0 / 19000) ** (sq ** 0.85)
        y = x.copy()
        y[s0:] = svf2(x[s0:], cut, res=0.35, poles=2)
        fade = np.interp(np.arange(NS) / SR, [0, 15.3, 15.7, 16.0], [1, 1, 0, 0])
        return y * fade[:, None]

    bass = hp(st["bass"], 95.0, 2) * d_bass[:, None]          # carve the bass out of the kick's sub region
    bass = outro_filter(bass)
    pad = outro_filter(st["pad"] * d_pad[:, None])
    stab = outro_filter(st["stab"] * d_stab[:, None])
    arp = outro_filter(st["arp"] * d_arp[:, None])
    lead = st["lead"] * d_lead[:, None]
    acid = outro_filter(st["acid"] * d_stab[:, None])
    rumble = st["rumble"] * d_rum[:, None]
    sub = st["sub"] * d_bass[:, None]
    boom = st["boom"] * d_boom[:, None]

    # reverbs
    ir_plate = make_ir(0.85, 1.1, 5, predelay=0.008, hp_hz=350.0, lp_hz=11000.0, damp=0.5)
    ir_hall = make_ir(1.7, 2.2, 6, predelay=0.02, hp_hz=300.0, lp_hz=8500.0, damp=0.6)
    ir_fx = make_ir(2.2, 2.6, 7, predelay=0.01, hp_hz=250.0, lp_hz=12000.0, damp=0.5)
    plate = conv_rev(st["plate_in"], ir_plate)
    hall_src = st["hall_in"] * duck_curve(kb, 0.5, 0.1)[:, None]
    hall = conv_rev(outro_filter(hall_src), ir_hall)
    # hall return: hangs in the air during the gap, then is sucked away before the drop
    gap_env = np.interp(T, [0, 6.0, 6.36, 6.4, 16], [1.0, 1.0, 0.0, 0.0, 1.0])
    hall *= gap_env[:, None]
    fxr = conv_rev(st["fx_in"], ir_fx)

    # delays
    dly_src = arp * 0.9 + lead * 0.9
    dly = pingpong(dly_src, 0.3, 0.4, 0.28)
    dly *= gap_env[:, None]

    # percussion widening
    hats = _widen(st["hats"], 9.0, 0.8, 4000.0) * d_hat[:, None]
    perc = _widen(st["perc"], 14.0, 0.7, 3000.0)

    # stem gains (dB), tuned by measurement
    G = dict(kick=-0.5, rumble=-3.0, sub=-8.0, bass=-4.0, clap=-2.0, rim=-8.0, snare=-3.5, hats=-10.5, perc=-15.5,
             stab=-3.0, arp=-8.0, pad=-12.5, lead=-4.5, acid=-12.5, fx=-8.5, boom=-4.5, riser=-1.0,
             plate=-9.0, hall=-11.0, fxr=-12.0, dly=-12.0)
    mix = np.zeros((NS, 2))
    parts = dict(kick=st["kick"], rumble=rumble, sub=sub, bass=bass, clap=st["clap"], rim=st["rim"],
                 snare=st["snare"], hats=hats, perc=perc, stab=stab, arp=arp, pad=pad, lead=lead, acid=acid,
                 fx=st["fx"], boom=boom, riser=st["riser"], plate=plate, hall=hall, fxr=fxr, dly=dly)
    SYNTH = ("stab", "arp", "pad", "lead", "acid", "hall", "dly")
    synth = np.zeros((NS, 2))
    for k, v in parts.items():
        if k in SYNTH:
            synth += v * db(G[k])
        else:
            mix += v * db(G[k])
    # synth bus limiter: the saw stacks are very peaky (crest ~ 17 dB); tame them so that the kick keeps the peaks
    synth = limiter(synth, SYNTH_CEIL, look_ms=3.0, rel_ms=90.0, tp=False)
    mix += synth
    # macro dynamics: the drop is the biggest section, the build sits a little under it, the outro relaxes
    macro_db = np.interp(T, [0.0, 3.19, 3.2, 6.0, 6.399, 6.4, 12.8, 13.1, 16.0],
                         [-0.6, -0.6, -1.2, -1.0, -1.0, 0.9, 0.9, -1.6, -1.6])
    mix *= db(macro_db)[:, None]
    return mix, parts, G


def master(mix, verbose=False):
    # tone shaping
    y = hp(mix, 27.0, 2)
    y = shelf(y, 85.0, 1.5, high=False)             # a little more sub weight
    y = peq(y, 320.0, -1.5, 0.9)
    y = shelf(y, 7000.0, -3.0, high=True)           # keep the top end club-like (hats/noise were too bright)
    y = lp(y, 16500.0, 2)                           # tame aliasing / content above the codec band
    # mono-ise everything below 150 Hz
    m = 0.5 * (y[:, 0] + y[:, 1])
    s = 0.5 * (y[:, 0] - y[:, 1])
    s = hp(s, 150.0, 2)
    y = np.stack([m + s, m - s], 1)
    # normalise (so that thresholds below are meaningful), then glue compression
    y = y / np.percentile(np.abs(y), 99.9)
    y, gc = _bus_comp(np.ascontiguousarray(y), -9.0, 2.0, 0.014, 0.10, 8.0)
    y = np.tanh(1.15 * y) / np.tanh(1.15)

    ceil = 10 ** (CEIL_DB / 20.0)
    c = ceil * 1.18

    def chain(G):
        z = c * np.tanh(G * y / c)
        z = signal.lfilter([1.0, -1.0], [1.0, -(1.0 - 2 * math.pi * 8.0 / SR)], z, axis=0)   # DC blocker after the clipper
        return limiter(z, ceil)

    G = 1.0
    best = None
    for it in range(10):
        out = chain(G)
        L = lufs(out)
        if verbose:
            gl = 20 * np.log10(limiter.last_gain)
            gcd = 20 * np.log10(gc)
            print(f"  master iter {it}: gain {20*math.log10(G):.2f} dB -> {L:.2f} LUFS | limiter GR mean {-gl.mean():.2f} "
                  f"p95 {-np.percentile(gl, 5):.2f} max {-gl.min():.2f} dB | comp GR mean {-gcd.mean():.2f} max {-gcd.min():.2f} dB")
        best = (out, L, G)
        err = TARGET_LUFS - L
        if abs(err) < 0.03:
            break
        G *= 10 ** (err / 20.0 * 0.85)
    out = best[0]
    # tiny fade at the very end (<= 4 ms) - nothing may ring over the loop start
    nf = int(0.004 * SR)
    out[-nf:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, nf)))[:, None]
    out[-1] = 0.0
    out = np.clip(out, -ceil * 1.0001, ceil * 1.0001)
    return out


def add_frame_envelopes(ev, audio):
    fl = SR // 30
    lows = lp(audio.mean(axis=1), 150.0, 4)
    highs = hp(audio.mean(axis=1), 5000.0, 4)
    rms_all, rms_lo, rms_hi = [], [], []
    for i in range(480):
        a, b = i * fl, (i + 1) * fl
        rms_all.append(float(np.sqrt(np.mean(audio[a:b] ** 2))))
        rms_lo.append(float(np.sqrt(np.mean(lows[a:b] ** 2))))
        rms_hi.append(float(np.sqrt(np.mean(highs[a:b] ** 2))))
    nrm = lambda v: [round(x / (max(v) + 1e-9), 4) for x in v]
    ev["frame_rate"] = 30
    ev["frame_level"] = nrm(rms_all)
    ev["frame_low"] = nrm(rms_lo)
    ev["frame_high"] = nrm(rms_hi)
    return ev


def render_float(verbose=False):
    st, ev = render_stems()
    mix, _, _ = mix_stems(st)
    out = master(mix, verbose=verbose)
    return out, ev


def make_audio(path, events_path=None, verbose=False):
    out, ev = render_float(verbose=verbose)
    ev = add_frame_envelopes(ev, out)
    ev["loudness_lufs_integrated"] = round(float(lufs(out)), 2)
    ev["peak_dbfs"] = round(float(20 * math.log10(np.max(np.abs(out)) + 1e-12)), 2)
    pcm = np.clip(np.round(out * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    if events_path:
        with open(events_path, "w") as f:
            json.dump(ev, f, indent=1)
    return ev


def main():
    out = os.path.join(HERE, "audio_marlo.wav")
    ev_path = os.path.join(HERE, "marlo_music_events.json")
    verbose = "-v" in sys.argv
    ev = make_audio(out, ev_path, verbose=verbose)
    print(f"wrote {out}  ({NS} samples, {ev['loudness_lufs_integrated']} LUFS, peak {ev['peak_dbfs']} dBFS)")
    print(f"wrote {ev_path}")


if __name__ == "__main__":
    main()
