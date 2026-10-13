"""Reel 23 mit kommerziell nutzbarer Stimme (Kokoro "Michael", Apache-2.0) statt Piper "Ryan".

Bild bleibt identisch: Jeder Kokoro-Satz wird höchstens auf die Lücke bis zum nächsten Einsatz gestaucht
(Spracherkennungs-Test: so bleibt alles verständlich), dann wird nur die Tonspur neu gemischt und mit dem
fertigen Video zusammengeführt.
Aufruf: python3 reel23_icing_kokoro.py [stimme] -> reel23_icing_k.mp4
"""
import os
import subprocess
import sys

import reel23_icing as R
import tts_kokoro as K

LINES = [
    ("q", "What is icing in hockey?"),
    ("half", "You shoot it from your own half,"),
    ("past", "past their goal line, untouched."),
    ("call", "Icing."),
    ("zone", "Faceoff in your zone. And no line change."),
    ("race", "Since 2013, it is a race to the dots."),
    ("def", "Defender first? Icing."),
    ("att", "Attacker first? Play on."),
    ("pk", "Short-handed? You can ice it."),
    ("cta", "Which rule should I explain next?"),
]

# Höchstlänge pro Satz im fertigen Mix (s) = Lücke bis zum nächsten Satz bzw. Rewind
WINDOW = {"q": 1.2, "half": 1.27, "past": 1.45, "call": 0.6, "zone": 1.98, "race": 2.35, "def": 1.22,
          "att": 1.3, "pk": 1.28, "cta": 1.75}
SPEED = 1.15


def main():
    os.chdir(R.HERE)
    voice = sys.argv[1] if len(sys.argv) > 1 else "am_michael"
    fit = {k: w * R.TEMPO for k, w in WINDOW.items()}                 # vor dem 1,1x-Tempo im Mix
    durs = K.synth(LINES, os.path.join("voice", "reel23k"), voice, SPEED, fit=fit)
    print(f"Stimme {voice}, Grundtempo {SPEED}")
    for k, _ in LINES:
        print(f"  {k:5s} {durs[k] / R.TEMPO:.2f}s im Mix (Fenster {WINDOW[k]:.2f}s)")
    R.VO_PREFIX = "reel23k"
    R.make_audio("audio_icing_k.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel23_icing.mp4", "-i", "audio_icing_k.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-14:TP=-1.0:LRA=9", "-ar", "44100", "-shortest",
                    "-movflags", "+faststart", "reel23_icing_k.mp4"], check=True)
    print("fertig: reel23_icing_k.mp4")


if __name__ == "__main__":
    main()
