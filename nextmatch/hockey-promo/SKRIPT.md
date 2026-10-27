# NEXT MATCH · Hockey-Promo (Full Motion) – Frame-Tabelle

1080 × 1920 · 30 fps · 15,0 s (F0–449) · 120 BPM (Beat = 15 F) · Schnitte F90 / F210 / F330 · keine Bilder, keine Sprache:
alles Vektor/CSS/SVG in HyperFrames, Ton = Beat + SFX (`audio/`). Ergebnis: `renders/nm_hockey_promo.mp4` (−14 LUFS).

| Frames | Szene | Bild / Motion | Ton |
|---|---|---|---|
| F0 | S1 Hook | **„STOP“** (rot, ab Bild 0, 118 → 100 %), Neon-Puck schlägt aus Kamerarichtung auf (Scale 3,2 → 1, bis F7), Wackler 12 F | Bass-Drop + Glitch-Swoosh |
| F0–95 | S1 | 3D-Eisfläche (Neon-Linien + Gitter, rotateX 68°) rast auf die Kamera zu; Puck kommt langsam näher (1 → 1,35) = Objekt-Separation; Hallenlichter flackern | |
| F15 | S1 | **„SCROLLING“** 0 → 150 % (`back.out`) | |
| F40 | S1 | „HOCKEY CLUBS, LISTEN UP.“ (Cyan, Mono) | |
| F60 | S1 | Shutter-Blitz 4 F + Kamera-Stoß | Kamera-Shutter |
| F84–96 | Übergang | Glitch-Schnitt (Flackern, Farbbalken, Versatz) | Glitch-Swoosh |
| F84–209 | S2 Problem | Regen; langweilige graue Spieltagsgrafik (Arial, „Team A vs Team B“) sinkt, kippt und schmilzt (Tropfen wachsen) | |
| F96–160 | S2 | Rote Reichweiten-Kurve „REACH“ zeichnet das Plateau | |
| F120 | S2 | **„BORING“** (weiß) slammt rein, Glitch-Wackeln + RGB-Split bis F206 | Vinyl-Scratch |
| F150 | S2 | **„= INVISIBLE“** (rot) | |
| F165–180 | S2 | Kurve stürzt durch den unteren Bildrand, Likes 3 → 0 (F172) | |
| F180 / F188 | S2 | Risse + rote Vignette + Wackler | Herzschlag (Double Thump) |
| F204–216 | Übergang | Snap-Swoosh nach rechts mit Motion-Blur | Whoosh L → R |
| F204–329 | S3 Lösung | Lime-Lichtstrahlen drehen; drei Lime-Speed-Ringe umkreisen die Gameday-Karte (beschleunigen bis F270) | Riser F210–270 |
| F212 | S3 | Pille „NM» NEXT MATCH“ | |
| F216 / 225 / 232 / 240 / 252 | S3 | Karte baut sich im Beat auf: GAMEDAY → Heimwappen von links → Gastwappen von rechts → VS-Slam (+ Wackler) → Infoleiste „FR 30.10. · BULLY 20:00“ | |
| F270 / 276 | S3 | **„MAXIMUM“** (Lime) und **„HYPE“** (weiß) Glow-In, Lime-Blitz, Wackler | Laser-Zap |
| F324–336 | Übergang | Glitch-Schnitt | Glitch-Swoosh |
| F330 | S4 CTA | **„COMMENT:“** schießt von unten rein, Handy (Vektor) fährt hoch, Konfetti-Explosion | Münz-Ding |
| F346 | S4 | Lime-Bubble **„GAMEDAY“** poppt, pulsiert auf F360/375/390/405 | |
| F352–376 | S4 | „GAMEDAY“ wird ins Kommentarfeld getippt, F380 „POST“ leuchtet | |
| F375 | S4 | Pfeil ↓ aufs Kommentarfeld, hüpft auf jedem Beat | |
| F420–449 | S4 | Großer Puls + Blitz + Wackler, dann Endbild halten | Sub-Bass-Impact |

Rendern: `npm run render`, danach Lautheit angleichen:
`ffmpeg -i renders/nm_hockey_promo_raw.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=9 -c:a aac -b:a 192k renders/nm_hockey_promo.mp4`
