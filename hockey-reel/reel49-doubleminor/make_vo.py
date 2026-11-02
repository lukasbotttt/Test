"""Sprecher (Kokoro am_michael, lokal) für Reel 49 „Why is this 4 minutes?“ (Double Minor, hoher Stock) – ein WAV pro Zeile.

Ruhiger Stil: Grundtempo 1,2, nicht gestaucht, kurze Sätze (ein Gedanke pro Bild).
Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("q", "Why is this four minutes?"),
    ("normal", "A high stick is usually a two-minute penalty."),
    ("blood", "But if it injures the player, like drawing blood, it's a double minor."),
    ("four", "Two plus two. Four minutes."),
    ("review", "Since twenty nineteen, the referee can check the video."),
    ("mate", "If it was his own teammate's stick, the penalty is gone."),
    ("cta", "Four minutes for a high stick. Too harsh?"),
    ("drop", "Yes or no?"),
]

if __name__ == "__main__":
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "audio", "vo", "vo"), speed=1.2)
