"""Sprecher (Kokoro am_michael, lokal) für Reel 47 „Why didn't this goal count?“ (hoher Stock) – ein WAV pro Zeile.

Ruhiger Stil: Grundtempo 1,2, nicht gestaucht, kurze Sätze (ein Gedanke pro Bild).
Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("q", "Why didn't this goal count?"),
    ("answer", "The stick was too high."),
    ("rule", "If an attacker touches the puck above the crossbar, about four feet up, the goal is waved off."),
    ("point", "What matters is where the puck hits the stick."),
    ("twist", "But if a defender knocks it into his own net with a high stick? It counts."),
    ("cta", "Fair rule?"),
    ("drop", "Yes or no?"),
]

if __name__ == "__main__":
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "audio", "vo", "vo"), speed=1.2)
