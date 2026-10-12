"""Kostenlose Sprachausgabe (Piper, Stimme "Ryan", lokal) – ein WAV pro Satz + Dauer.

Stimme: rhasspy/piper-voices en_US-ryan-high (Datensatz CC BY-NC-SA 4.0 -> nur nicht-kommerziell).
Modell liegt in voice/piper/ (nicht im Git, ~120 MB; Download: huggingface.co/rhasspy/piper-voices).
"""
import json
import os
import subprocess
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "voice", "piper", "en_US-ryan-high.onnx")


def synth(lines, out_prefix, length_scale=0.9):
    """lines: Liste von (key, text). Schreibt <out_prefix>_<key>.wav, gibt {key: dauer} zurück."""
    durs = {}
    for key, text in lines:
        path = f"{out_prefix}_{key}.wav"
        subprocess.run(["python3", "-m", "piper", "-m", MODEL, "--length-scale", str(length_scale),
                        "--sentence-silence", "0.0", "-f", path], input=text.encode(), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with wave.open(path) as w:
            durs[key] = w.getnframes() / w.getframerate()
    with open(out_prefix + "_timing.json", "w") as f:
        json.dump(durs, f, indent=1)
    return durs
