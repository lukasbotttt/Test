# Reel 45 · „Why does hockey have 3 periods?“ (@bladesandpucks) – Frame-Tabelle

1080 × 1920 · 30 fps · 23,0 s (F0–689) · 120 BPM · Schnitte F90 / F210 / F330 / F435 / F555 · keine Bilder, keine
Spielerkörper: Anzeigetafel, 3D-Eisfläche mit Schnee, Viertel-Kreis. Ruhiger Stil (ein Text-Block pro Bild, Standzeit
≥ 0,5 s + 0,3 s pro Wort), Ende kürzer als bei Reel 44 (dort brach die Kurve in den letzten 4 s ein: 25 s → 18 %).
Ton = Beat + SFX + Sprecher (Kokoro `am_michael`, Tempo 1,2) als eine Mischung. Ergebnis: `renders/reel45_periods.mp4` (−14 LUFS).
Die Kompositionen wurden mit einem kleinen Generator erzeugt (gemeinsame Bausteine Anzeigetafel/Eisfläche); bearbeitet
werden ab jetzt direkt die HTML-Dateien in `compositions/`.

## Fakten + Quellen
- Vor 1910 wurden zwei Halbzeiten à 30 Minuten gespielt; Schnee und Eis sammelten sich auf der Fläche (Jahrzehnte vor der
  ersten Eismaschine von Frank Zamboni); drei Drittel = häufigere Eisreinigung — NBC Sports Boston, Charlotte Edmonds,
  „Why hockey games are played in three periods“, 17.11.2022. (Dass die Patrick-Brüder dahinterstanden, nennt der
  Artikel selbst „Legende“ – deshalb nicht im Video.)
- NHA-Saison 1910-11: „Games were changed from two periods of 30 minutes, to three periods of twenty minutes“ —
  Wikipedia, „1910–11 NHA season“, Abschnitt Rule changes. Die NHA war die führende Profiliga vor der NHL (ab 1917).
- Heute: NHL-Spiele haben drei Drittel à 20 Minuten.

## Sprecher (Einsätze global)
| Start | Zeile |
|---|---|
| 0,10 s | Why does hockey have three periods? |
| 3,20 s | Until nineteen ten, games had two halves of thirty minutes. |
| 7,20 s | But snow kept piling up on the ice, and there was no Zamboni yet. |
| 11,20 s | So the top league switched to three periods of twenty minutes. |
| 14,70 s | Two breaks to clean the ice, instead of one. And it's still that way today. |
| 18,70 s | Should hockey switch to four quarters? |
| 20,60 s | Yes or no? |

## Bild (ein Gedanke pro Bild)
| Frames | Bild | Text | Ton |
|---|---|---|---|
| F0–89 | Anzeigetafel schlägt ein, Uhr 20:00 läuft, Lampen 1-2-3 (F9/19/29) | **WHY DOES HOCKEY HAVE 3 PERIODS?** (ab Bild 0) | Bass-Drop, Klicks |
| F84–96 | Glitch-Schnitt | | Glitch |
| F90–209 | Tafel vergilbt (alter Film), „HALF“ 30:00, Lampen 1-2 (F151/157) | **UNTIL 1910 · 2 × 30 MIN** | Slam |
| F204–216 | Snap-Swoosh nach rechts | | Whoosh |
| F210–329 | 3D-Eisfläche, Schnee legt sich drauf (F214–300), Flocken fallen | **SNOW ON THE ICE · NO ZAMBONI YET** (F285) | Wind |
| F329–331 | Blitz + Zoom-Stoß | | Slam |
| F330–434 | Tafel „PERIOD“ 20:00, Lampen 1-2-3 (F360/368/376) | **1910-11 · 3 × 20 MIN** (F369) | Klicks |
| F429–441 | Snap-Swoosh nach rechts | | Whoosh |
| F435–554 | Eis voller Schnee, Reinigungs-Balken fährt zweimal drüber (F445–470, F497–520) | **2 BREAKS TO CLEAN THE ICE** → **STILL TODAY** (F518) | Schaber ×2 |
| F549–561 | Glitch-Schnitt | | Glitch |
| F555–689 | Viertel-Kreis „4 × 15“ füllt sich (F567–585) | **4 QUARTERS INSTEAD?** · Bubble **YES OR NO?** (F604) + Pfeil | Klicks, Sub-Impact F612 |

## Bauen
```
python3 make_vo.py        # Sprecher (Kokoro, lokal)
python3 make_audio.py     # Beat, SFX, Mischungen mix_vo.wav / mix_novo.wav
npm run render            # -> renders/reel45_raw.mp4
ffmpeg -i renders/reel45_raw.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k renders/reel45_periods.mp4
```
