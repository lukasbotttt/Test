# Reel 46 · „A goal without a shot?“ – Awarded Goal (@bladesandpucks) – Frame-Tabelle

1080 × 1920 · 30 fps · 24,0 s (F0–719) · 120 BPM · Schnitte F90 / F270 / F420 / F495 / F600 · keine Bilder, keine
Spielerkörper: Chips auf der 3D-Eisfläche, Vektor-Schläger, Pucks, Statistik-Tafel, Torlampe. Ruhiger Stil (ein
Text-Block pro Bild). Ton = Beat + SFX + Sprecher (Kokoro `am_michael`, Tempo 1,2; „McLeod“ = mək lˈaʊd, passt ohne Fix).
Ergebnis: `renders/reel46_awarded.mp4` (−14 LUFS). Kompositionen per Generator erzeugt (Bausteine wie Reel 45);
weiter bearbeitet wird direkt in `compositions/`.

## Fakten + Quellen
- NHL-Regel 25.1: Ein Tor wird zugesprochen, wenn der Gegner seinen Torhüter vom Eis genommen hat, ein Angreifer die
  Scheibe in der neutralen oder Angriffszone kontrolliert (oder kontrolliert hätte), kein Verteidiger zwischen ihm und
  dem Tor ist und er durch ein Vergehen am Torschuss gehindert wird — Wortlaut zitiert bei Scouting the Refs (Josh Smith,
  16.01.2025).
- 15.01.2025, Sabres – Hurricanes 4:2: Carolina hatte den Torhüter gezogen, Brent Burns schlug Ryan McLeod auf dem Weg
  zum leeren Tor den Schläger kaputt; der Schiedsrichter gab das Tor = McLeods erster Hattrick (Gutschrift wechselte
  zwischendurch zu Tage Thompson, am Ende McLeod). Buffalo hatte im 3. Drittel 0 Torschüsse und traf trotzdem (erstmals
  seit 1965-66, dass ein Team in einem Drittel ohne Torschuss ein Tor erzielte) — AP-Bericht (ESPN/Fox Sports),
  Scouting the Refs, The Hockey News.

## Sprecher (Einsätze global)
| Start | Zeile |
|---|---|
| 0,10 s | How do you score a goal without a shot? |
| 3,10 s | If the goalie is pulled, and a player on a breakaway gets fouled, the referee just awards the goal. |
| 9,20 s | In twenty twenty-five, Ryan McLeod got slashed on his way to an empty net. |
| 14,20 s | Goal awarded. Hat trick complete. |
| 16,70 s | His team had zero shots in that period, and still scored. |
| 20,20 s | Should that count as a goal? |
| 21,90 s | Yes or no? |

## Bild (ein Gedanke pro Bild)
| Frames | Bild | Text | Ton |
|---|---|---|---|
| F0–89 | 3D-Eisfläche, Rot (#9) mit Puck rast aufs leere Tor, Torlampe blinkt ohne Schuss | **A GOAL WITHOUT A SHOT?** (ab Bild 0) | Bass-Drop, leises Horn |
| F84–96 | Glitch-Schnitt | | Glitch |
| F90–269 | Goalie-Chip „G“ fährt zur Bank (F108–134), Alleingang, Foul von hinten (Ring F184), Puck rutscht vorbei, Lampe F236 | **EMPTY NET** (F117) **+ FOUL** (F181) **= GOAL** (F234) | Whoosh, Knack + Pfiff, Horn |
| F264–276 | Snap-Swoosh nach rechts | | Whoosh |
| F270–419 | heller Schläger, roter Schläger holt aus und schlägt zu, F351 bricht der Schläger mit Splittern | **JAN 2025 · RYAN MCLEOD** | Knack |
| F419–421 | Blitz + Zoom-Stoß | | Slam |
| F420–494 | drei Pucks leuchten nacheinander (F440/447/459), Ring F478 | **GOAL AWARDED · HAT TRICK** | Klicks, Ding |
| F489–501 | Snap-Swoosh nach rechts | | Whoosh |
| F495–599 | Tafel: SHOTS 0 (F508), GOALS 1 (F568) | **3RD PERIOD** | Slam, Ding |
| F594–606 | Glitch-Schnitt | | Glitch |
| F600–719 | Torlampe blinkt auf den Beats | **SHOULD IT COUNT?** · Bubble **YES OR NO?** (F650) + Pfeil | Sub-Impact F684 |

## Bauen
```
python3 make_vo.py        # Sprecher (Kokoro, lokal)
python3 make_audio.py     # Beat, SFX, Mischungen mix_vo.wav / mix_novo.wav
npm run render            # -> renders/reel46_raw.mp4
ffmpeg -i renders/reel46_raw.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k renders/reel46_awarded.mp4
```
