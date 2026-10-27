# Reel 43 · „Why only 40 seconds?“ (@bladesandpucks) – Frame-Tabelle

1080 × 1920 · 30 fps · 18,5 s (F0–554) · 120 BPM (Beat = 15 F) · Schnitte F105 / F255 / F315 / F465 · keine Bilder:
alles Vektor/CSS/SVG in HyperFrames. Ton = Beat + SFX + Sprecher (Kokoro `am_michael`, Tempo 1,25 × 1,08) als eine Mischung.
Ergebnis: `renders/reel43_shift.mp4` (mit Sprecher) und `renders/reel43_shift_novo.mp4` (nur Musik + SFX), beide −14 LUFS.

## Fakten + Quellen
- Typischer NHL-Wechsel ≈ 35–45 s Spielzeit — NHL.com (Seattle Kraken, „The FYI on TOI: Shorter Shifts Win“, 10.01.2024).
- „…for 30 to 40 seconds, you're going to get tired and it's time for a change.“ / „the longer your shifts, the more mistakes
  you end up making“ — JT Brown (Ex-NHL-Stürmer, 365 Spiele; Kraken-TV-Analyst), gleicher Artikel.
- Flyers-Stürmer: Ø ca. 44 s pro Wechsel 2018-19 → ca. 41 s 2019-20; Team ließ weniger Tore und Konter zu —
  NHL.com (Philadelphia Flyers, Bill Meltzer, „Inside the numbers: Shorter shifts matter“, 12.04.2020).

## Sprecher (Einsätze global)
| Start | Zeile |
|---|---|
| 0,10 s | Why do NHL players only play about forty seconds at a time? |
| 3,60 s | Because every shift is an all-out sprint. Thirty to forty seconds at full speed, and you're exhausted. |
| 8,60 s | Stay out longer, and the mistakes pile up. |
| 10,60 s | The Flyers cut their forwards' shifts from forty-four to forty-one seconds, and allowed fewer goals. |
| 15,60 s | How many seconds would you last? Drop a number. |

## Bild
| Frames | Szene | Bild / Motion | Ton |
|---|---|---|---|
| F0 | S1 Hook | **„WHY ONLY 40 SECONDS?“** ab Bild 0 (40 rot, RGB-Split), Neon-Stoppuhr schlägt aus Kamerarichtung ein (3 → 1) | Bass-Drop + Glitch |
| F0–104 | S1 | 3D-Neon-Eisfläche rast heran; Zeiger + Anzeige 00:00 → 00:40 (F80, rot + Blitz); Uhr kommt langsam näher | Ticks auf den Beats, Buzzer F80 |
| F36 | S1 | „TYPICAL NHL SHIFT: 35–45 SEC“ | |
| F99–111 | Übergang | Glitch-Schnitt | Glitch-Swoosh |
| F105–254 | S2 Sprint | Speed-Streifen, Akku + SHIFT CLOCK + ENERGY, EKG-Linie (Puls wird schneller) | |
| F110 / F140 / F150 | S2 | „EVERY SHIFT IS AN“ → „ALL-OUT“ → **„SPRINT“**-Slam | Slam F150 |
| F158 | S2 | Zitat-Karte JT Brown (NHL.com) | |
| F175–215 | S2 | **„30–40 SEC“** (gelb) + „AT FULL SPEED“; Uhr 0:30 → 0:40, Akku 70 % → 0 % | Riser |
| F239 | S2 | **„EXHAUSTED“** (rot), rote Vignette pulsiert, Akku blinkt | Herzschlag ×2, Beat setzt aus |
| F254–256 | Übergang | harter Schnitt mit rotem Blitz + Zoom-Stoß | Fehler-Ton |
| F255–314 | S3 Mistakes | Risse im Eis, „STAY OUT / LONGER…“, rote X-Kacheln fallen und stapeln sich, **„MISTAKES PILE UP“** (F292/F299) | Fehler-Ton F292/300/308 |
| F309–321 | Übergang | Snap-Swoosh nach rechts mit Motion-Blur | Whoosh L → R |
| F315–464 | S4 Proof | Pille „PHILADELPHIA FLYERS“ (F320), gestrichelte Balken-Rahmen (F326), Balken 44 s (F359–369) und 41 s (F380–390, Achse ab 0), Badge **„−3 SEC“** (F399), **„✓ FEWER GOALS ALLOWED“** (F432–437), Quelle | Slam 44, Ding 41, Slam FEWER |
| F459–471 | Übergang | Glitch-Schnitt | Glitch-Swoosh |
| F465–554 | S5 CTA | „HOW MANY SECONDS / WOULD YOU LAST?“, Uhr würfelt Zahlen → „??“ (F510), Bubble **„DROP A NUMBER“** (F494, Puls F514), Pfeil + Kommentarfeld, @BLADESANDPUCKS | Sub-Impact F525 |

## Bauen
```
python3 make_vo.py        # Sprecher (Kokoro, lokal)
python3 make_audio.py     # Beat, SFX, Mischungen mix_vo.wav / mix_novo.wav
npm run render            # -> renders/reel43_shift_raw.mp4
ffmpeg -i renders/reel43_shift_raw.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k renders/reel43_shift.mp4
ffmpeg -i renders/reel43_shift_raw.mp4 -i audio/mix_novo.wav -map 0:v -map 1:a -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k -shortest renders/reel43_shift_novo.mp4
```
