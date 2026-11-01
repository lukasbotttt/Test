"""Sprecher (Kokoro am_michael, lokal) für Reel 48 „Miracle on Ice“ (Kino-Trailer) – ein WAV pro Zeile in audio/vo/.

Trailer-Stimme: Tempo 1,05 (ruhiger als die Regel-Erklärer), kurze Sätze, Pausen kommen aus dem Schnitt.
Lautschrift-Fix: Eruzione = ˌɛɹuːziˈoʊni („air-oo-zee-OH-nee“).
Aufruf: python3 make_vo.py   (Modell liegt in hockey-reel/voice/kokoro/, nicht im Git)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tts_kokoro  # noqa: E402

VO_LINES = [
    ("lost", "They lost, ten to three."),
    ("again", "Thirteen days later, they met again."),
    ("soviet", "The Soviet Union. Four Olympic golds in a row."),
    ("kids", "The Americans? College kids."),
    ("placid", "Lake Placid. February twenty-second, nineteen eighty."),
    ("d1", "Down one to nothing."),
    ("d2", "Down two to one."),
    ("d3", "Down three to two."),
    ("tie", "They tie it."),
    ("ten", "Then, with exactly ten minutes left, the captain."),
    ("mike", "Mike Eruzione."),
    ("hold", "Four to three. Now hold on."),
    ("c5", "Five."), ("c4", "Four."), ("c3", "Three."), ("c2", "Two."), ("c1", "One."),
    ("title", "They called it, the Miracle on Ice."),
    ("gold", "Two days later, they beat Finland for gold."),
    ("cta", "Do you believe in miracles?"),
    ("drop", "Yes or no?"),
]
FIXES = {"ɪɹˈuːzˈaɪəni": "ˌɛɹuːziˈoʊni"}

if __name__ == "__main__":
    tts_kokoro.synth(VO_LINES, os.path.join(HERE, "audio", "vo", "vo"), speed=1.05, fixes=FIXES)
