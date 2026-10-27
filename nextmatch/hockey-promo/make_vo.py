"""Sprecher (Kokoro am_michael, lokal) für den NEXT-MATCH-Hockey-Promo -> audio/vo/s1..s4.wav (48 kHz, Tempo 1,08x).

Aufruf: python3 make_vo.py   (danach Wortzeiten mit faster-whisper prüfen)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "hockey-reel"))
import tts_kokoro  # noqa: E402

LINES = [
    ("s1", "Stop scrolling. This changes your game day."),
    ("s2", "Your game day graphics? Boring. And boring kills your reach."),
    ("s3", "Next Match turns every game into motion that hits different."),
    ("s4", "Comment GAMEDAY, and get a free sample for your club!"),
]


def main():
    tmp = os.path.join(HERE, "audio", "vo", "_raw")
    tts_kokoro.synth(LINES, tmp, speed=1.25)
    for k, _ in LINES:
        src = f"{tmp}_{k}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", "atempo=1.08", "-ar", "48000", "-ac", "1",
                        os.path.join(HERE, "audio", "vo", f"{k}.wav")], check=True)
        os.remove(src)
    os.remove(tmp + "_timing.json")
    print("fertig")


if __name__ == "__main__":
    main()
