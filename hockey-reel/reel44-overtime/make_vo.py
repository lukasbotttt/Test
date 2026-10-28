"""Sprecher (Kokoro am_michael, lokal) für Reel 44 „Why is overtime only 3-on-3?“ – ein WAV pro Zeile in audio/vo/.

Ruhige Version: Grundtempo 1,2, nicht gestaucht, kurze Sätze (ein Gedanke pro Bild).
Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("q", "Why is NHL overtime only three-on-three?"),
    ("reason", "Because too many games were ending in shootouts."),
    ("fourfour", "With four-on-four, only forty-four percent of overtime games ended in overtime."),
    ("switch", "So in twenty fifteen, the NHL took one more skater off the ice."),
    ("space", "More space. More overtime goals."),
    ("seventy", "Now about seventy percent end in overtime."),
    ("cta", "Three-on-three, or shootout?"),
    ("drop", "Comment one word."),
]

if __name__ == "__main__":
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "audio", "vo", "vo"), speed=1.2)
