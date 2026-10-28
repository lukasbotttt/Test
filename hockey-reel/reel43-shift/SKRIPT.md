# Reel 43 v2 · „Why only 40 seconds?“ (@bladesandpucks) – ruhige Version

1080 × 1920 · 30 fps · 26,0 s (F0–779) · 120 BPM (Beat = 15 F) · Schnitte F135 / F360 / F450 / F645 · keine Bilder:
alles Vektor/CSS/SVG in HyperFrames. Ton = Beat + SFX + Sprecher (Kokoro `am_michael`, Tempo 1,2, nicht gestaucht) als eine Mischung.
Ergebnis: `renders/reel43v2_shift.mp4` (−14 LUFS).

**Warum v2:** v1 (18,5 s, `renders/reel43_shift.mp4`, gepostet 27.10.) war zu überladen – Feedback „man kommt beim Lesen
nicht mit“, TikTok: 1 s 70 % · 3 s 48 % · Ø 7,4 s gesehen. Regeln für v2 (und folgende Videos):
- **ein Text-Block pro Bild**, jeder steht mind. 0,5 s + 0,3 s pro Wort (HyperFrames-Craft-Check: 0 Warnungen)
- keine Zusatz-Labels, Zitate, Quellenzeilen, Mini-Zähler im Bild – Quellen gehören in Caption/Anpinn-Kommentar
- Sprecher langsamer, in kurzen Sätzen mit Pausen; weniger Wackler/RGB-Split, nur auf Schlüsselwörtern

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
| 4,70 s | Because every shift is an all-out sprint. |
| 7,70 s | Thirty to forty seconds at full speed, and you're exhausted. |
| 12,20 s | Stay out longer, and the mistakes pile up. |
| 15,20 s | The Flyers cut their forwards' shifts from forty-four to forty-one seconds. |
| 19,30 s | And they allowed fewer goals. |
| 21,70 s | How many seconds would you last? |
| 23,60 s | Drop a number. |

## Bild (ein Gedanke pro Bild)
| Frames | Bild | Text | Ton |
|---|---|---|---|
| F0–134 | Neon-Eisfläche, Stoppuhr schlägt ein und läuft auf 00:40 (F86) | **WHY ONLY 40 SECONDS?** (ab Bild 0) | Bass-Drop, Ticks, Buzzer F86 |
| F129–141 | Glitch-Schnitt | | Glitch-Swoosh |
| F135–224 | Speed-Streifen | **ALL-OUT SPRINT** (Puls auf „sprint“ F188) | Slam |
| F225–306 | Akku fährt hoch und läuft leer (grün → gelb → rot) | **30–40 SEC** | Riser |
| F307–359 | Akku leer, blinkt, rote Herzschlag-Vignette | **EXHAUSTED** | Herzschlag ×2, Beat setzt aus |
| F359–361 | roter Blitz-Schnitt + Zoom-Stoß | | Fehler-Ton |
| F360–449 | Risse, rote X-Kacheln fallen und stapeln sich | **MISTAKES PILE UP** | Fehler-Ton F402/411/421 |
| F444–456 | Snap-Swoosh nach rechts | | Whoosh |
| F450–644 | Pille, leere Balken-Rahmen → 44 s (F506) → 41 s (F530), Achse ab 0 | **PHILADELPHIA FLYERS** · 44s / 41s · **−3 SEC** (F548) · **✓ FEWER GOALS ALLOWED** (F580) | Slam, Ding, Slam |
| F639–651 | Glitch-Schnitt | | Glitch-Swoosh |
| F645–779 | Stoppuhr würfelt Zahlen → „??“ (F684), Bubble + Pfeil (F705) | **HOW MANY SECONDS WOULD YOU LAST?** · **DROP A NUMBER** | Sub-Impact F720 |

## Bauen
```
python3 make_vo.py        # Sprecher (Kokoro, lokal)
python3 make_audio.py     # Beat, SFX, Mischungen mix_vo.wav / mix_novo.wav
npm run render            # -> renders/reel43v2_raw.mp4
ffmpeg -i renders/reel43v2_raw.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k renders/reel43v2_shift.mp4
```
