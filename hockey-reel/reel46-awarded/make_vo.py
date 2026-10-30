"""Sprecher (Kokoro am_michael, lokal) für Reel 46 „A goal without a shot?“ – ein WAV pro Zeile in audio/vo/.

Ruhiger Stil: Grundtempo 1,2, nicht gestaucht, kurze Sätze (ein Gedanke pro Bild).
Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("q", "How do you score a goal without a shot?"),
    ("rule", "If the goalie is pulled, and a player on a breakaway gets fouled, the referee just awards the goal."),
    ("story", "In twenty twenty-five, Ryan McLeod got slashed on his way to an empty net."),
    ("hat", "Goal awarded. Hat trick complete."),
    ("zero", "His team had zero shots in that period, and still scored."),
    ("cta", "Should that count as a goal?"),
    ("drop", "Yes or no?"),
]
FIXES = {}

if __name__ == "__main__":
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "audio", "vo", "vo"), speed=1.2, fixes=FIXES or None)
