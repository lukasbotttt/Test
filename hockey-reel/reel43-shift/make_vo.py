"""Sprecher (Kokoro am_michael, lokal) für Reel 43 „Why only 40 seconds?“ – ein WAV pro Zeile in audio/vo/.

Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("q", "Why do NHL players only play about forty seconds at a time?"),
    ("sprint", "Because every shift is an all-out sprint."),
    ("gassed", "Thirty to forty seconds at full speed, and you're exhausted."),
    ("mistakes", "Stay out longer, and the mistakes pile up."),
    ("proof", "The Flyers cut their forwards' shifts from forty-four to forty-one seconds."),
    ("goals", "And they allowed fewer goals."),
    ("cta", "How many seconds would you last?"),
    ("drop", "Drop a number."),
]


if __name__ == "__main__":
    prefix = os.path.join(HERE, "audio", "vo", "vo")
    tts_kokoro.synth(VO_LINES, prefix, speed=1.2)       # ruhige Version: Grundtempo 1,2, nicht gestaucht
