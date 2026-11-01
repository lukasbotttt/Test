# Reel 47 · „Why didn't this goal count?“ – hoher Stock (@bladesandpucks) – Frame-Tabelle

1080 × 1920 · 30 fps · 21,0 s (F0–629) · 120 BPM · Schnitte F75 / F315 / F390 / F525 · keine Bilder, keine
Spielerkörper: Tor von vorn/von der Seite, Vektor-Schläger, Puck, Torlatten-Linie (4 ft). Ruhiger Stil (ein Text-Block
pro Bild), kürzer als Reel 44–46 (dort brach die Kurve im letzten Viertel ein).
Ton = Beat + SFX + Sprecher (Kokoro `am_michael`, Tempo 1,2). Ergebnis: `renders/reel47_highstick.mp4` (−14 LUFS).
Kompositionen per Generator erzeugt (wie Reel 45/46); weiter bearbeitet wird direkt in `compositions/`.

## Fakten + Quellen
- NHL-Regel 80.3 (zitiert in der NHL.com-Videobeweis-Meldung ANA @ CGY, 26.01.2026): „When an attacking player causes
  the puck to enter the opponent's goal by contacting the puck above the height of the crossbar, either directly or
  deflected off any player or official, the goal shall not be allowed.“
- Entscheidend ist die Höhe des Kontaktpunkts Puck–Schläger (Scouting the Refs, z. B. Kings-Review 02.12.2021: „the
  stick must have contacted the puck at or below crossbar height“). Torlatte = 4 ft (1,22 m) über dem Eis.
- Verteidiger schlägt den Puck mit hohem Stock ins eigene Tor → Tor zählt (Wikipedia „High-sticking“ mit Verweis auf
  NHL-Regel 80; gleichlautend im IIHF-Regelbuch).
- Bewusst weggelassen (zu viel auf einmal): Schulterhöhe als Grenze für „High-sticking the puck“ ohne Tor (Regel 80.1).

## Sprecher (Einsätze global)
| Start | Zeile |
|---|---|
| 0,10 s | Why didn't this goal count? |
| 2,70 s | The stick was too high. |
| 4,70 s | If an attacker touches the puck above the crossbar, about four feet up, the goal is waved off. |
| 10,70 s | What matters is where the puck hits the stick. |
| 13,20 s | But if a defender knocks it into his own net with a high stick? It counts. |
| 17,70 s | Fair rule? |
| 18,70 s | Yes or no? |

## Bild (ein Gedanke pro Bild)
| Frames | Bild | Text | Ton |
|---|---|---|---|
| F0–74 | Tor von vorn, Puck drin, Lampe brennt; F39–44 Stempel **NO GOAL**, Lampe aus | **WHY DIDN'T THIS GOAL COUNT?** (ab Bild 0) | Bass-Drop, Horn, Fehler-Ton |
| F69–81 | Glitch-Schnitt | | Glitch |
| F75–139 | Seitenansicht, Torlatten-Linie „CROSSBAR · 4 FT“, Puck trifft die Schaufel ÜBER der Linie (F79), ins Tor | **STICK TOO HIGH** | Knack |
| F140–314 | Linie pulsiert (F176), Label pulsiert (F226), Wiederholung (F250), rotes ✕ am Tor (F296) | **ABOVE THE CROSSBAR = NO GOAL** | Whoosh, Fehler-Ton |
| F309–321 | Snap-Swoosh nach rechts | | Whoosh |
| F315–389 | Schläger hoch, aber der Puck trifft den Schaft UNTER der Linie (F347) → Tor, „✓ BELOW THE BAR“ | **WHERE THE PUCK HITS THE STICK** | Klick, Ding |
| F389–391 | Blitz + Zoom-Stoß | | Slam |
| F390–524 | blauer Verteidiger-Schläger schlägt den hohen Puck ins eigene Tor (F466), Lampe, grünes ✓ | **DEFENDER + HIGH STICK = IT COUNTS** | Knack, Ding |
| F519–531 | Glitch-Schnitt | | Glitch |
| F525–629 | Bokeh, Torlatten-Linie als Deko | **FAIR RULE?** · Bubble **YES OR NO?** (F556) + Pfeil | Sub-Impact F587 |

## Bauen
```
python3 make_vo.py        # Sprecher (Kokoro, lokal)
python3 make_audio.py     # Beat, SFX, Mischungen mix_vo.wav / mix_novo.wav
npm run render            # -> renders/reel47_raw.mp4
ffmpeg -i renders/reel47_raw.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k renders/reel47_highstick.mp4
```
