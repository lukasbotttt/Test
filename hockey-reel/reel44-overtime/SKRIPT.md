# Reel 44 · „Why is overtime only 3-on-3?“ (@bladesandpucks) – Frame-Tabelle

1080 × 1920 · 30 fps · 27,0 s (F0–809) · 120 BPM · Schnitte F105 / F195 / F360 / F570 / F675 · keine Bilder, keine
Spielerkörper: Spieler sind nummerierte Chips auf einer 3D-Eisfläche (NHL-Maße 200 × 85 ft). Ruhiger Stil wie Reel 43 v2:
ein Text-Block pro Bild, Standzeit ≥ 0,5 s + 0,3 s pro Wort, Quellen nur in Caption/Anpinn-Kommentar.
Ton = Beat + SFX + Sprecher (Kokoro `am_michael`, Tempo 1,2) als eine Mischung. Ergebnis: `renders/reel44_overtime.mp4` (−14 LUFS).

## Fakten + Quellen (NHL.com, Nicholas J. Cotsonika)
- 2014-15 (4 gegen 4 in der Verlängerung): 44 % der Spiele mit Verlängerung endeten in der Verlängerung; das Gefühl war,
  dass zu viele Spiele im Shootout endeten → ab 2015-16 3 gegen 3 — „NHL general managers discuss, endorse OT format at
  meetings“, 18.03.2024.
- 2022-23: 69 %, 2023-24: 70 % (Rekord), 2024-25 nach 1.064 Spielen 74 % — „NHL GMs encouraged by lots of offense,
  parity“, 17.03.2025.

## Sprecher (Einsätze global)
| Start | Zeile |
|---|---|
| 0,10 s | Why is NHL overtime only three-on-three? |
| 3,70 s | Because too many games were ending in shootouts. |
| 6,70 s | With four-on-four, only forty-four percent of overtime games ended in overtime. |
| 12,20 s | So in twenty fifteen, the NHL took one more skater off the ice. |
| 16,60 s | More space. More overtime goals. |
| 19,20 s | Now about seventy percent end in overtime. |
| 22,70 s | Three-on-three, or shootout? |
| 24,40 s | Comment one word. |

## Bild (ein Gedanke pro Bild)
| Frames | Bild | Text | Ton |
|---|---|---|---|
| F0–104 | 3D-Eisfläche, 3 gegen 3 Chips gleiten über viel freies Eis, Kamera-Dolly | **WHY IS OVERTIME ONLY 3-ON-3?** (ab Bild 0, Puls F53) | Bass-Drop |
| F99–111 | Glitch-Schnitt | | Glitch |
| F105–194 | Tor (Vorderansicht), vier Pucks fliegen auf den Beats rein, Torlampe | **TOO MANY SHOOTOUTS** | 4 Schüsse |
| F189–201 | Snap-Swoosh nach rechts | | Whoosh |
| F195–359 | 4 gegen 4 eng in der Mitte | **4-ON-4 · ONLY 44% · ENDED IN OVERTIME** (Zähler F240–249) | Slam |
| F354–366 | Glitch-Schnitt | | Glitch |
| F360–489 | #3 und #5 heben ab und fliegen vom Eis (F462–480) | **2015-16 · −1 SKATER** | Pop ×2 |
| F490–569 | 3 gegen 3 ziehen auseinander, #9 Alleingang, Tor F540 | **MORE SPACE · MORE GOALS** | Riser, Horn |
| F569–571 | Blitz + Zoom-Stoß | | Slam |
| F570–674 | Balken: 4-on-4 (2014-15) 44 % · 3-on-3 (2023-24) füllt auf 70 % (F583–595) | **ENDED IN OVERTIME** | Ding |
| F669–681 | Glitch-Schnitt | | Glitch |
| F675–809 | Bokeh | **3-ON-3 OR SHOOTOUT?** · Bubble **COMMENT ONE WORD** (F726) + Pfeil | Sub-Impact F732 |

## Bauen
```
python3 make_vo.py        # Sprecher (Kokoro, lokal)
python3 make_audio.py     # Beat, SFX, Mischungen mix_vo.wav / mix_novo.wav
npm run render            # -> renders/reel44_raw.mp4
ffmpeg -i renders/reel44_raw.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k renders/reel44_overtime.mp4
```
