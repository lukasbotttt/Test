# Reel 50 · „Why is HE in the box?“ – Torwart-Strafe (@bladesandpucks) – Frame-Tabelle

1080 × 1920 · 30 fps · 23,0 s (F0–689) · 120 BPM · Schnitte F100 / F196 / F297 / F363 / F570 · keine Bilder, keine
Spielerkörper: Strafbank (Glas + Bande), Tor von vorn, nummerierte Chips (G = Torwart), Strafuhr (DSEG7), Klemmbrett.
Ruhiger Stil (ein Text-Block pro Bild), Muster von Reel 47/49 (Verwirrung im Spiel, ~21–23 s).
Ton = Beat + SFX + Sprecher (Kokoro `am_michael`, Tempo 1,2). Ergebnis: `renders/reel50_goaliepen.mp4` (−14 LUFS).
Kompositionen per Generator erzeugt (wie Reel 45–49); weiter bearbeitet wird direkt in `compositions/`.
Sprecher-Hinweis: „goalies sat“ / „goalies serve“ verschluckte das s (Whisper hörte „Goldie“) → Sätze mit Einzahl.

## Fakten + Quellen
- Heute: Bekommt der Torwart eine kleine (oder große) Strafe, geht er nicht in die Strafbank; ein Mitspieler, der beim
  Vergehen auf dem Eis war, sitzt sie ab, der Trainer bestimmt, wer — NHL-Regelbuch Regel 27 (Goalkeeper's Penalties,
  zitiert bei Winging It In Motown „Getting to Know the NHL Rulebook: Goalie Penalties“); gleichlautend IIHF-Regel 27.1
  und USA-Hockey-Regel 407.
- Bis 1932: In den ersten 15 NHL-Saisons saß der Torwart seine kleine Strafe selbst ab, ein Feldspieler ging ins Tor.
  15.03.1932 in Boston: Torontos Lorne Chabot musste 2 Minuten sitzen, Verteidiger Red Horner ging ohne
  Torwart-Ausrüstung ins Tor; danach Regeländerung (ab Saison 1932-33 darf ein Ersatzmann die Strafe des Torwarts
  absitzen) — NHL.com „Wild sequence led to NHL rule change in 1932“; Wikipedia „Lorne Chabot“ und „1932–33 NHL season“.
- Bewusst weggelassen: Matchstrafe/Spieldauer-Disziplinarstrafe (Torwart fliegt raus), Namen Chabot/Horner (nur Caption).

## Sprecher (Einsätze global)
| Start | Zeile |
|---|---|
| 0,10 s | Why is he in the box? The goalie took the penalty. |
| 3,40 s | When a goalie gets a penalty, he stays in his net. |
| 6,60 s | A teammate who was on the ice sits in the box for him. |
| 10,05 s | And the coach picks who goes. |
| 12,25 s | Until nineteen thirty-two, the goalie had to sit in the box himself. |
| 16,25 s | A skater had to play goal, with no goalie gear. |
| 19,30 s | Should the goalie sit in the box too? |
| 21,25 s | Yes or no? |

## Bild (ein Gedanke pro Bild)
| Frames | Bild | Text | Ton |
|---|---|---|---|
| F0–99 | Strafuhr 2:00 läuft, Nr. 17 in der Strafbank, Torwart G im Tor: roter Ring (F48), gestrichelter Pfeil G → Strafbank (F54) | **WHY IS HE IN THE BOX?** (ab Bild 0) | Bass-Drop, Pfiff |
| F94–105 | Glitch-Schnitt | | Glitch |
| F100–195 | großes Tor, G will raus (F134), federt zurück (F146), grüner Schloss-Ring (F175–181) | **GOALIE** → **STAYS IN NET** (F154) | Klick |
| F190–202 | Snap-Swoosh nach rechts | | Whoosh |
| F196–296 | 5 Chips auf dem Eis leuchten (F212–224), Nr. 17 fährt in die Strafbank (F242–258), Strafuhr (F262) | **A TEAMMATE** → **SITS FOR HIM** (F238) | Klicks, Tür, Uhr |
| F296–298 | Blitz + Zoom-Stoß | | Slam |
| F297–362 | Klemmbrett #4 #9 #17 #22 #71, Kreis um #17 (F318–330), Haken (F345) | **THE COACH PICKS WHO** | Ding |
| F357–369 | Glitch-Schnitt | | Glitch |
| F363–569 | Rückblende in Sepia (Flackern, Kratzer): G fährt selbst in die Strafbank (F440–456), Nr. 4 rutscht ins leere Tor und zittert (F494–568) | **UNTIL 1932** → **SKATER IN GOAL** (F492) | Projektor |
| F564–575 | Glitch-Schnitt | | Glitch |
| F570–689 | G in der Strafbank pulsiert auf den Beats | **SHOULD THE GOALIE SIT IN THE BOX?** · Bubble **YES OR NO?** (F628) + Pfeil | Sub-Impact F662 |

## Bauen
```
python3 make_vo.py        # Sprecher (Kokoro, lokal)
python3 make_audio.py     # Beat, SFX, Mischungen mix_vo.wav / mix_novo.wav
npm run render            # -> renders/reel50_raw.mp4
# Lautheit zweistufig (linear) auf −14 LUFS -> renders/reel50_goaliepen.mp4
```
