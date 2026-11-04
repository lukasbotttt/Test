"""Sprecher (Kokoro am_michael, lokal) für Reel 50 „Why is HE in the box?“ (Torwart-Strafe sitzt ein Mitspieler ab) – ein WAV pro Zeile.

Ruhiger Stil: Grundtempo 1,2, nicht gestaucht, kurze Sätze (ein Gedanke pro Bild).
Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("q", "Why is he in the box? The goalie took the penalty."),
    ("stay", "When a goalie gets a penalty, he stays in his net."),
    ("mate", "A teammate who was on the ice sits in the box for him."),
    ("coach", "And the coach picks who goes."),
    ("hist", "Until nineteen thirty-two, the goalie had to sit in the box himself."),
    ("gear", "A skater had to play goal, with no goalie gear."),
    ("cta", "Should the goalie sit in the box too?"),
    ("drop", "Yes or no?"),
]

if __name__ == "__main__":
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "audio", "vo", "vo"), speed=1.2)
