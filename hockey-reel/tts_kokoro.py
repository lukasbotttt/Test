"""Kostenlose Sprachausgabe mit kommerziell nutzbarer Lizenz (Kokoro-82M, Apache-2.0, lokal).

Ein WAV pro Satz. Mit `fit` (Höchstlänge pro Satz) werden zu lange Sätze gestaucht, damit sie in die
Lücken eines fertigen Videos passen – Bild und Ton bleiben synchron, ohne neu zu rendern.
Modell liegt in voice/kokoro/ (nicht im Git, ~350 MB; Download: github.com/thewh1teagle/kokoro-onnx,
Release "model-files-v1.0": kokoro-v1.0.onnx + voices-v1.0.bin).
"""
import json
import os
import subprocess

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "voice", "kokoro")
_tts = None


def engine():
    global _tts
    if _tts is None:
        from kokoro_onnx import Kokoro
        _tts = Kokoro(os.path.join(DIR, "kokoro-v1.0.onnx"), os.path.join(DIR, "voices-v1.0.bin"))
    return _tts


def say(text, voice="am_michael", speed=1.0, fixes=None):
    """fixes: {falsche Lautschrift: richtige} – z. B. Namensbetonung (Brodeur = broh-DUR)."""
    lang = "en-gb" if voice.startswith("b") else "en-us"
    if fixes:
        ph = engine().tokenizer.phonemize(text, lang)
        for a, b in fixes.items():
            ph = ph.replace(a, b)
        audio, sr = engine().create(ph, voice=voice, speed=speed, lang=lang, is_phonemes=True)
    else:
        audio, sr = engine().create(text, voice=voice, speed=speed, lang=lang)
    return np.asarray(audio, np.float32), sr


def stretch(path, factor):
    """Tempo um `factor` ändern (Tonhöhe bleibt), in-place."""
    tmp = path + ".tmp.wav"
    chain = []
    f = factor
    while f > 2.0 or f < 0.5:                       # atempo kann nur 0.5–2.0 pro Stufe
        step = 2.0 if f > 2.0 else 0.5
        chain.append(f"atempo={step}")
        f /= step
    chain.append(f"atempo={f:.5f}")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-af", ",".join(chain), tmp], check=True)
    os.replace(tmp, path)


def synth(lines, out_prefix, voice="am_michael", speed=1.0, fit=None, fixes=None):
    """lines: Liste von (key, text). fit: {key: höchstdauer} -> nur stauchen. Gibt {key: dauer} zurück."""
    durs = {}
    for key, text in lines:
        path = f"{out_prefix}_{key}.wav"
        audio, sr = say(text, voice, speed, fixes)
        sf.write(path, audio, sr)
        d = len(audio) / sr
        if fit and key in fit and d > fit[key]:
            stretch(path, d / fit[key])
            d = sf.info(path).duration
        durs[key] = d
    with open(out_prefix + "_timing.json", "w") as f:
        json.dump(durs, f, indent=1)
    return durs
