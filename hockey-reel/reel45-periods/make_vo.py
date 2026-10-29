"""Sprecher (Kokoro am_michael, lokal) für Reel 45 „Why does hockey have 3 periods?“ – ein WAV pro Zeile in audio/vo/.

Ruhiger Stil: Grundtempo 1,2, nicht gestaucht, kurze Sätze (ein Gedanke pro Bild).
Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("q", "Why does hockey have three periods?"),
    ("halves", "Until nineteen ten, games had two halves of thirty minutes."),
    ("snow", "But snow kept piling up on the ice, and there was no Zamboni yet."),
    ("fix", "So the top league switched to three periods of twenty minutes."),
    ("breaks", "Two breaks to clean the ice, instead of one. And it's still that way today."),
    ("cta", "Should hockey switch to four quarters?"),
    ("drop", "Yes or no?"),
]

if __name__ == "__main__":
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "audio", "vo", "vo"), speed=1.2)
