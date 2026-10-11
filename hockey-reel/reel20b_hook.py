"""Reel 20b: Hook-Version von THE PUCK pt. 2 – startet direkt im Puck-Flug, ~6 s, nahtloser Loop.

Ablauf (140 BPM):
  Frame 0  Puck schießt schon ins Bild, Zeile "HOCKEY IN 8 WORDS"
  8 Beats  SNAP SLAP WRIST BACKHAND DANGLE DEKE TOE DRAG SNIPE – jeder Flug wischt die nächste Fläche frei
  6 Beats  Puck bremst in der Mitte: "WHICH ONE / IS YOURS?" – dann schießt er rechts raus (Loop: am
           Anfang kommt er links wieder rein)
Nutzt die Szenen und den Renderer aus reel20_puck2.py. Aufruf: python3 reel20b_hook.py
"""
import math
import os
import subprocess
import time
import wave

import numpy as np
from PIL import Image, ImageDraw
from scipy.signal import fftconvolve

import puck3d as P3
import reel15_puck as R15
import reel20_puck2 as P2
from reel15_puck import c01, e_out, e_in

W, H, FPS, B = P2.W, P2.H, P2.FPS, P2.B
T0 = 8 * B + 0.035                     # Frame 0: Puck mitten im Bild, "SNAP" halb freigewischt
Q = 16 * B                             # Puck kommt in der Mitte an
T_EXIT, T_LAUNCH, T_GONE = 21.2 * B, 21.5 * B, 21.95 * B
PERIOD = 14.25 * B                     # Loop-Länge: am Ende fliegt der Puck wie in Frame 0 von links rein
DUR = PERIOD
BLACK, WHITE, OR = P2.BLACK, P2.WHITE, P2.OR


# ---------------------------------------------------------------- Szenen anpassen
def plain_white():
    return P2.solid(WHITE)


def question_scene(t):
    bt = t / B
    img = P2.solid(WHITE)
    po = c01((t - T_EXIT) / (0.3 * B))
    P2.reveal_c(img, P2.headline("WHICH ONE", 176, BLACK), W / 2, 520, c01((bt - 17) / 0.35), po)
    P2.reveal_c(img, P2.headline("IS YOURS?", 176, BLACK), W / 2, 1390, c01((bt - 18) / 0.35), po)
    opts = R15.line_img("COMMENT YOUR PICK", 40, 800, OR, track=6)
    P2.reveal_c(img, opts, W / 2, 1515, c01((bt - 19) / 0.35), po)
    return img


P2.product_end = plain_white
P2.question_scene = question_scene


def label(img, t):
    """Hook-Zeile oben (ab Frame 0 sichtbar; verschwindet in der Frage, kommt zum Loop zurück)."""
    bt = t / B
    if t >= T0 + PERIOD - P2.FLY_IN:
        a = 1.0
    elif t < Q + 0.25 * B:
        a = 1.0 - c01((t - Q) / (0.25 * B))
    else:
        a = c01((t - (T_LAUNCH + 0.1 * B)) / (0.25 * B))
    if a <= 0:
        return
    txt = R15.line_img("HOCKEY IN 8 WORDS", 56, 800, WHITE, track=4)
    pill = Image.new("RGBA", (txt.width + 90, txt.height + 50), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle((0, 0, pill.width - 1, pill.height - 1), pill.height // 2,
                                           fill=BLACK + (255,))
    pill.alpha_composite(txt, (45, 25))
    P2.paste_c(img, pill, W / 2, 300, a)


def question_frame(t, fidx):
    img = question_scene(t)
    rows, lens, pk = np.zeros((P2.KSUB, 13)), np.zeros((P2.KSUB, 2)), np.zeros((P2.KSUB, 7))
    vis = False
    for j in range(P2.KSUB):
        tj = t + ((j + 0.5) / P2.KSUB - 0.5) * (0.55 / FPS)
        o = 9 * math.sin((tj - 16.7 * B) * 1.6) * c01((tj / B - 16.7) * 2)
        az = math.degrees(math.atan2(-P2.SHOT_F[2], -P2.SHOT_F[0])) + o
        pos = P2.sph(P2.CENTRE, P2.SHOT_D, az, math.degrees(math.asin(-P2.SHOT_F[1])))
        rows[j] = P2.cam_row(pos, P2.CENTRE, np.array([0.0, 1.0, 0.0]), 40.0)
        p = P2.puck_pos(8, tj) + np.array([0, 0.25 * math.sin((tj - 16.4 * B) * 3.0) * c01((tj / B - 16.4) * 2), 0])
        la = c01((tj - T_LAUNCH) / (T_GONE - T_LAUNCH))
        if la > 0:
            rv = P3.look_at(pos, P2.CENTRE, np.array([0.0, 1.0, 0.0]))[0]
            p = p + rv * 14 * e_in(la, 2.2)
        if np.linalg.norm(p - P2.CENTRE) > 13:
            pk[j] = (0, -500, 0, 0, 0.0, 0.0, tj)
            continue
        pk[j] = (p[0], p[1], p[2], P2.spin_at(8, tj) + 25 * la ** 2, 1.0, 0.0, tj)
        vis = True
    if vis:
        rgbp, cov = P2.render_puck(W, H, rows, lens, pk, fidx + 80)
        lay = P2.layer_from(rgbp, cov)
        img.alpha_composite(P2.soft_shadow(lay, 26, 0.2 * (1 - c01((t - T_LAUNCH) / (0.15 * B)))), (0, 40))
        img.alpha_composite(lay)
    return img


def compose(t_rel, fidx=0):
    t = T0 + t_rel
    if t >= T0 + PERIOD - P2.FLY_IN:                     # Loop-Naht: Anflug von Flug 1 über der weißen Fläche
        img = P2.shot_frame(t - PERIOD, fidx)
    elif t <= Q + P2.FLY_OUT:
        img = P2.shot_frame(t, fidx)
    else:
        img = question_frame(t, fidx)
    label(img, t)
    arr = np.asarray(img.convert("RGB"), np.float32) / 255
    arr = arr + np.random.default_rng(fidx + 3).normal(0, 0.007, arr.shape[:2])[..., None]
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


# ---------------------------------------------------------------- Musik (Trap, 140 BPM, Loop-fähig)
SR = 44100


def make_audio(path):
    n = int(round(DUR * SR))
    rng = np.random.default_rng(21)
    L, Rr = np.zeros(n), np.zeros(n)
    send = np.zeros((n, 2))

    def tt(sec):
        return np.arange(int(sec * SR)) / SR

    def put_(sig, at, vol=1.0, pan=0.0, rev=0.0):
        """at in Szenenzeit T (wie reel20_puck2); wird auf Videozeit verschoben und am Ende umgebrochen (Loop)."""
        st = int(round((at - T0) * SR)) % n
        s = sig * vol
        gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.41, math.sin((pan + 1) * math.pi / 4) * 1.41
        idx = (st + np.arange(len(s))) % n
        np.add.at(L, idx, s * gl)
        np.add.at(Rr, idx, s * gr)
        if rev:
            np.add.at(send[:, 0], idx, s * gl * rev)
            np.add.at(send[:, 1], idx, s * gr * rev)

    def lp(x, k):
        c = np.cumsum(np.concatenate([np.zeros(k), x]))
        return (c[k:] - c[:-k]) / k

    def hp(x, k):
        return x - lp(x, k)

    def noise(sec):
        return rng.standard_normal(int(sec * SR))

    def kick(vol=1.0):
        x = tt(0.38)
        f = 46 + 190 * np.exp(-x * 38)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 8.5)
        return np.tanh(body * 3.0 + hp(noise(0.38), 2) * np.exp(-x * 400) * 0.6) * vol

    def clap(vol=1.0):
        x = tt(0.3)
        env = sum((x >= d) * np.exp(-np.maximum(x - d, 0) * 70) for d in (0.0, 0.009, 0.019, 0.03))
        return hp(lp(noise(0.3), 2), 6) * (env * 0.45 + np.exp(-x * 13) * 0.55) * 0.8 * vol

    def hat(vol=0.16, dec=150):
        return hp(noise(0.05), 1) * np.exp(-tt(0.05) * dec) * vol

    def b808(freq, dur, glide=0.0, f_to=None):
        x = tt(dur)
        f = freq * (1 + glide * np.exp(-x * 10))
        if f_to:
            f = f + (f_to - freq) * np.clip((x - dur * 0.5) / (dur * 0.3), 0, 1)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.6) * np.minimum(x / 0.003, 1) * np.exp(-x * 1.1) * 0.8

    def bell(freq, dur=0.7, vol=0.2):
        x = tt(dur)
        mod = np.sin(2 * np.pi * freq * 3.5 * x) * 2.2 * np.exp(-x * 6)
        return np.sin(2 * np.pi * freq * x + mod) * np.exp(-x * 4.5) * np.minimum(x / 0.002, 1) * vol

    def whoosh(dur=0.4, vol=1.0):
        x = tt(dur)
        nz = noise(dur)
        env = np.exp(-((x / dur - 0.55) ** 2) * 18)
        kx = 40 - 34 * (x / dur)
        return sum(lp(nz, kk) * np.exp(-((kx - kk) ** 2) / 60) for kk in (36, 18, 8, 4)) * env * 1.8 * vol

    def riser(dur, vol=1.0):
        x = tt(dur)
        sw = np.sin(2 * np.pi * np.cumsum(220 + 2400 * (x / dur) ** 2.2) / SR) * (x / dur) ** 3 * 0.18
        return (hp(noise(dur), 3) * (x / dur) ** 2.5 * 0.32 + sw) * vol

    def impact(vol=1.0, f0=38):
        x = tt(1.4)
        f = f0 + 140 * np.exp(-x * 14)
        return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.6) * 2.6) * vol

    def pop(vol=0.3):
        x = tt(0.12)
        return np.sin(2 * np.pi * np.cumsum(900 + 1400 * np.exp(-x * 60)) / SR) * np.exp(-x * 35) * vol

    A1, F1, G1, E1 = 55.0, 43.65, 49.0, 41.2
    roots = [A1, F1, G1, E1]
    mel = [880.0, 1046.5, 1318.5, 1046.5, 987.8, 880.0, 784.0, 659.25]
    # Schüsse (Beat 8–16)
    for b in np.arange(8, 16, 0.5):
        pos = b % 4
        if pos in (0.0, 2.5):
            put_(kick(), b * B)
        if pos in (1.0, 3.0):
            put_(clap(), b * B, rev=0.3)
        put_(hat(0.15 if b % 1 == 0 else 0.1), b * B, pan=0.3)
        if pos == 3.5:
            for j in range(1, 4):
                put_(hat(0.09), b * B + j * B / 6, pan=0.3)
        if pos == 1.5:
            for j in range(4):
                put_(hat(0.07, 220), b * B + j * B / 8, pan=-0.3)
        bar = int((b - 8) // 4)
        if pos == 0.0:
            put_(b808(roots[(bar * 2) % 4], 2.4 * B, 0.6), b * B)
        if pos == 2.5:
            put_(b808(roots[(bar * 2 + 1) % 4], 1.4 * B, 0.4), b * B)
        put_(bell(mel[int(b * 2) % 8], 0.5, 0.075), b * B, pan=-0.2, rev=0.3)
    for k in range(9):
        a = math.radians(P2.SHOTS[k][4])
        put_(whoosh(0.3, 0.85), (8 + k) * B - 0.17)
        put_(whoosh(0.18, 0.4), (8 + k) * B - 0.06, pan=0.7 * math.cos(a))
    # Frage (Beat 16–22.25): Beat läuft halb weiter, Pops auf den Zeilen, Launch -> Loop
    put_(impact(0.9, 40), Q + 0.12, rev=0.35)
    for b in np.arange(16, 22, 0.5):
        pos = b % 4
        if pos in (0.0, 2.5):
            put_(kick(0.9), b * B)
        if pos in (1.0, 3.0):
            put_(clap(0.75), b * B, rev=0.35)
        put_(hat(0.1 if b % 1 == 0 else 0.06), b * B, pan=0.3)
        if pos == 0.0:
            put_(b808(roots[int((b - 16) // 4) * 2 % 4], 2.4 * B, 0.6), b * B)
        put_(bell(mel[int(b * 2 + 3) % 8], 0.6, 0.07), b * B, pan=0.2, rev=0.35)
    for b in (17, 18, 19):
        put_(pop(0.32), b * B, rev=0.3)
    put_(riser(0.9 * B, 0.8), T_LAUNCH - 0.3 * B)
    put_(whoosh(0.35, 1.0), T_LAUNCH + 0.05, pan=0.6)
    # Hall (zyklisch, damit der Loop nahtlos ist)
    irn = int(1.6 * SR)
    xr = np.arange(irn) / SR
    wet = []
    for ch in range(2):
        ir = lp(rng.standard_normal(irn) * np.exp(-xr / 0.4), 6)
        full = fftconvolve(np.concatenate([send[:, ch], send[:, ch]]), ir)[: 2 * n]
        wet.append(full[n:2 * n] * 0.035)
    mix = np.stack([L + wet[0], Rr + wet[1]], 1)
    mix /= np.percentile(np.abs(mix), 99.9) + 1e-9
    mix = np.tanh(mix * 1.15)
    mix = mix / np.max(np.abs(mix)) * 0.95
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    os.chdir(P2.HERE)
    make_audio("audio_puck2b.wav")
    nf = int(round(DUR * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", "audio_puck2b.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart",
           "reel20b_hook.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(nf):
        proc.stdin.write(compose(i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{nf}  {time.time() - t0:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    Image.fromarray(compose(0.0, 9999)).save("reel20b_thumbnail.jpg", quality=92)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "reel20b_hook.mp4", "-c:v", "copy", "-an",
                    "reel20b_hook_ohne_ton.mp4"])
    print("fertig: reel20b_hook.mp4")


if __name__ == "__main__":
    main()
