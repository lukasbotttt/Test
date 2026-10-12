"""TikTok-Version von Reel 22: Voiceover (vidIQ, Stimme "Liam") Satz für Satz auf die Szenen gelegt, Musik geduckt.

Aufruf: python3 reel22_vo_mix.py voice/reel22.mp3 -> reel22_trapezoid_vo.mp4
"""
import os
import subprocess
import sys
import wave

import numpy as np

import reel22_trapezoid as R

SR = 44100
# Startzeit pro Satz (s) – passend zu den Einblendungen im Video
STARTS = [0.12, 2.7, 3.5, 4.55, 7.75, 9.7, 11.35]


def read_wav(path):
    with wave.open(path) as w:
        n, ch = w.getnframes(), w.getnchannels()
        a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, ch)


def segments(vo, thr_db=-38, min_gap=0.22):
    """Sätze anhand von Pausen trennen."""
    env = np.abs(vo)
    k = int(0.02 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    loud = env > 10 ** (thr_db / 20)
    segs, start, quiet = [], None, 0
    for i, l in enumerate(loud):
        if l:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet > min_gap * SR:
                segs.append((start, i - quiet + 1))
                start, quiet = None, 0
    if start is not None:
        segs.append((start, len(vo)))
    return [(max(0, a - int(0.03 * SR)), min(len(vo), b + int(0.06 * SR))) for a, b in segs if b - a > 0.15 * SR]


def main():
    os.chdir(R.HERE)
    src = sys.argv[1]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", str(SR), "vo_tmp.wav"], check=True)
    vo = read_wav("vo_tmp.wav")[:, 0]
    segs = segments(vo)
    print("Sätze gefunden:", len(segs), [round((b - a) / SR, 2) for a, b in segs])
    if len(segs) != len(STARTS):
        raise SystemExit("Satzanzahl passt nicht – Schwelle anpassen")
    R.make_audio("audio_trapezoid.wav")
    mus = read_wav("audio_trapezoid.wav")
    n = len(mus)
    voice = np.zeros(n, np.float32)
    t_next = 0.0
    for (a, b), st in zip(segs, STARTS):
        st = max(st, t_next)                       # nie überlappen
        s0 = int(st * SR)
        clip = vo[a:b]
        e = min(n, s0 + len(clip))
        voice[s0:e] += clip[: e - s0]
        t_next = st + len(clip) / SR + 0.05
        print(f"  Satz bei {st:.2f}s – {st + len(clip) / SR:.2f}s")
    voice /= np.max(np.abs(voice)) + 1e-9
    k = int(0.08 * SR)
    venv = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
    duck = 1 - 0.62 * np.clip(venv / 0.08, 0, 1)
    mix = mus * duck[:, None] * 0.8 + voice[:, None] * 0.95
    mix /= np.max(np.abs(mix)) + 1e-9
    mix *= 0.95
    with wave.open("audio_trapezoid_vo.wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel22_trapezoid.mp4", "-i", "audio_trapezoid_vo.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", "reel22_trapezoid_vo.mp4"], check=True)
    os.remove("vo_tmp.wav")
    print("fertig: reel22_trapezoid_vo.mp4")


if __name__ == "__main__":
    main()
