# MOTION-PROMO – framegenaues Skript (HyperFrames)

| Eckdaten | |
|---|---|
| Format | 1080 × 1920 (9:16), **30 fps**, **15,0 s = Frame 0–449** |
| Takt | **120 BPM** → 1 Beat = 15 Frames (0,5 s), 1 Takt = 60 Frames (2 s) |
| Schnitte | auf Beats: **F90** (3,0 s) · **F210** (7,0 s) · **F330** (11,0 s) |
| Look | Neon/Cyberpunk: Magenta `#ff1744`/`#ff2bd6`, Cyan `#00f0ff`, Mint `#00ffc8`, Gold `#ffcf40`; Schrift Anton (Headlines), Archivo Expanded Black (CTA), JetBrains Mono (Labels) |
| Safe-Zone | Text nur in x 60–960 px und y 220–1500 px (oben App-Leiste, rechts Like-/Kommentar-Buttons, unten Caption) |
| Umsetzung | HyperFrames v0.8.209 · `index.html` (Übergänge, Audio) + `compositions/s1-hook.html … s4-cta.html` (je Szene ein GSAP-Timeline) · `npm run check` = 0 Fehler |

Alle Frame-Angaben unten sind **global** (Frame 0 = Videostart) und stehen 1:1 so im Code.

---

## [SZENE 1] Hook · 0:00–0:03 · F0–89

**Sprecher** (0,00–2,80 s, Datei `audio/vo/s1.wav`): „Hör auf zu scrollen. Das hier wird alles verändern!“
Wort-Anker (auf den Click aufnehmen): **„Hör“ F0 · „auf“ F8 · „zu scrollen“ F15 · „Das hier …“ ab F40**

**SFX**

| Frame | Zeit | Sound | Datei |
|---|---|---|---|
| F0 | 0,00 | Heavy Bass Drop | `sfx/bass_drop.wav` |
| F0 | 0,00 | Glitch-Swoosh | `sfx/glitch_swoosh.wav` |
| F60 | 2,00 | Digitaler Kamera-Shutter | `sfx/shutter.wav` |
| F84 | 2,80 | Glitch-Swoosh (Übergang) | `sfx/glitch_swoosh.wav` |

**KI-Bilder (2 Ebenen für echte Objekt-Separation)**

- `assets/s1_bg.jpg` (Hintergrund, 1080 × 1920 oder größer):
  `A hyper-detailed, neon-lit futuristic cyber-hacker room, walls of glowing monitors with code, magenta and cyan neon tubes, volumetric haze, intense cinematic lighting, empty room, no people, photorealistic, 8k --ar 9:16`
- `assets/s1_fg.png` (Vordergrund, freigestellt, 900 × 1200, PNG mit Alpha):
  `A hooded hacker, waist-up, facing the camera, face hidden in shadow, strong magenta and cyan rim light, isolated on a plain black background, photorealistic, sharp edges, 8k --ar 3:4`
- Negativ (alle Bilder): `text, letters, words, watermark, logo, extra fingers, deformed hands, blurry, low quality`

**Motion & Text**

| Frame | Element | Animation (Werte = Code) |
|---|---|---|
| F0 | **„HÖR“** (rot, 280 px) | ab Bild 0 sichtbar, Scale 118 % → 100 % in 5 F (`power4.out`), RGB-Split rot/cyan ±16 px für 10 F |
| F0–11 | Kamera (`#s1cam`) | Extremer Shake: 12 F, 46 px, pro Frame neu, linear abklingend |
| F8 | **„AUF“** (rot) | Scale 240 % → 100 %, Opacity 0 → 1 in 5 F; RGB-Split 8 F; Nach-Shake 6 F / 18 px |
| F15 | **„ZU SCROLLEN“** (weiß) | Scale **0 → 150 %** in 9 F (`back.out(2.2)`) |
| F0–95 | Objekt-Separation | Hintergrund Scale 100 → 106 % (linear); **Vordergrund** Scale 92 → 122 %, y +60 → −40 px (`power1.in`): Figur löst sich vom Raum und kommt auf den Zuschauer zu |
| F40 | Unterzeile „DAS ÄNDERT ALLES.“ (Cyan, Mono 44 px) | Opacity 0 → 1, y +30 → 0 in 6 F; für Zuschauer ohne Ton |
| F60 | Shutter | Weißer Blitz 95 % → 0 in 4 F + Kamera-Stoß 105 % → 100 % in 6 F |
| F84–96 | Übergang | Glitch-Schnitt zu S2 (siehe Übergänge) |

---

## [SZENE 2] Problem · 0:03–0:07 · F90–209

**Sprecher** (3,05–6,75 s, `audio/vo/s2.wav`): „Herkömmliche Videos sind langweilig. Sie killen deine Retention!“
Wort-Anker: **„langweilig“ ≈ F120 · „Retention“ ≈ F171–180**

**SFX**

| Frame | Zeit | Sound | Datei |
|---|---|---|---|
| F120 | 4,00 | Vinyl Scratch | `sfx/vinyl_scratch.wav` |
| F180 / F188 | 6,00 / 6,27 | Herzschlag (Double Thump) | `sfx/heartbeat.wav` (beide Schläge in einer Datei) |
| F205 | 6,85 | Snap-Swoosh links → rechts | `sfx/whoosh_right.wav` |

**KI-Bilder**

- `assets/s2_bg.jpg`: `Dark rainy moody night, raindrops running down a window, deep blue neon reflections, bokeh city lights, abstract representation of boredom, cinematic, no people, no text --ar 9:16`
- `assets/s2_fg.png` (freigestellt): `A smartphone melting like wax, the screen dripping down, glowing neon blue tears running from the display, surreal, isolated on a plain black background, studio lighting, photorealistic --ar 3:4`

**Motion & Text**

| Frame | Element | Animation |
|---|---|---|
| F84–214 | Hintergrund / Handy | Hintergrund Scale 100 → 107 % linear; Handy y 0 → +50 px, Scale 100 → 108 % (`sine.inOut`): das Handy „sinkt“ und schmilzt |
| F96–160 | Retention-Kurve (rot, 16 px, Glow) | Wird von links gezeichnet (Reveal-Maske 0 → 650 px, linear): flaches Plateau |
| F120 | **„LANGWEILIG“** (weiß, 190 px) | Scale 180 % → 100 %, Opacity 0 → 1 in 6 F (`back.out(2)`) |
| F150 | **„= GAME OVER“** (rot, 170 px) | wie oben |
| F126–206 | Text-Glitch | Alle 2 F neuer Versatz: ±3 px, mit 25 % Chance ±12 px, Rotation ±0,6°; dazu RGB-Split ±9 px |
| F165–180 | Kurven-Absturz | Reveal 650 → 1080 px (`power3.in`): Kurve stürzt steil ab, über das Handy hinweg und **durch den unteren Bildrand** |
| F180 | Herzschlag 1 | Risse (weiß, Glow) erscheinen am Einschlagpunkt (880 \| 1700), Scale 70 → 100 % in 5 F; rote Vignette 90 % → 15 % in 7 F; Shake 8 F / 30 px |
| F188 | Herzschlag 2 | Zweite Risslage (rot) 80 → 100 % in 4 F; Vignette 75 % → 10 % in 10 F; Shake 6 F / 18 px |
| F204–216 | Übergang | Snap-Swoosh nach rechts (siehe Übergänge) |

---

## [SZENE 3] Lösung · 0:07–0:11 · F210–329

**Sprecher** (7,05–10,95 s, `audio/vo/s3.wav`): „Aber mit Claude und HyperFrames feuerst du Animationen ab, die süchtig machen.“
Wort-Anker: **„Claude“ ≈ F222 · „Animationen“ ≈ F270**

**SFX**

| Frame | Zeit | Sound | Datei |
|---|---|---|---|
| F210–270 | 7,00–9,00 | Energie-Aufbau (Riser) | `sfx/riser.wav` |
| F270 | 9,00 | Laserschuss (Zap) | `sfx/laser_zap.wav` |
| F324 | 10,80 | Glitch-Swoosh (Übergang) | `sfx/glitch_swoosh.wav` |

**KI-Bilder**

- `assets/s3_bg.jpg`: `Futuristic AI core chamber, floating holographic screens, golden energy lines, warm orange and gold volumetric light rays, epic composition, no robot, no people, no text --ar 9:16`
- `assets/s3_fg.png` (freigestellt): `A powerful humanoid AI robot, upper body, front view, glowing golden energy lines across sleek dark chrome armor, glowing eyes, isolated on a plain black background, epic lighting, photorealistic --ar 3:4`

**Motion & Text**

| Frame | Element | Animation |
|---|---|---|
| F204–330 | Hintergrund | Scale 108 → 100 % (`power1.out`): Gegenbewegung zum Roboter = Tiefe |
| F210–234 | Roboter | Steigt auf: y +120 → 0, Scale 90 → 100 % (`power3.out`); danach bis F330 auf 108 % |
| F210–270 | 3 goldene Speed-Line-Ringe (perspektivische Ellipsen) | Beschleunigen mit dem Riser (`power2.in`): Ring 1 0 → 540°, Ring 2 0 → −720°, Ring 3 0 → 360°. Ring 1 und 3 liegen hinter dem Roboter, Ring 2 davor, dadurch **umkreisen** sie ihn |
| F270–330 | Ringe | Vollgas (linear): +1440° / −1800° / +1080° |
| F210 | Übergang | Snap-Swoosh-Ankunft von links |
| F222 | Pille „CLAUDE × HYPERFRAMES“ (Gold, Mono) | x −300 → 0, Opacity 0 → 1 in 8 F (`expo.out`) |
| F270 | Laser-Zap | Gold-Blitz 70 % → 0 in 8 F; Shake 8 F / 22 px |
| F270 | **„MAXIMAL“** (Gold, Glow) | **Glow-In**: Opacity 0 → 1, Scale 135 → 100 % in 8 F (`power3.out`) |
| F276 | **„KRASS“** (weiß, goldener Glow, 250 px) | Glow-In: Scale 150 → 100 % in 8 F |
| F300 | „KRASS“ | Puls 100 → 106 → 100 % (2 × 4 F) |
| F324–336 | Übergang | Glitch-Schnitt zu S4 |

---

## [SZENE 4] Call to Action · 0:11–0:15 · F330–449

**Sprecher** (11,05–14,55 s, `audio/vo/s4.wav`): „Schreib jetzt ‚MOTION‘ in die Kommentare und ich schicke dir den Skill!“
Wort-Anker: **„MOTION“ ≈ F346 · „Kommentare“ ≈ F375 · „Skill“ ≈ F412**

**SFX**

| Frame | Zeit | Sound | Datei |
|---|---|---|---|
| F330 | 11,00 | „Ding“-Münzsound | `sfx/coin.wav` |
| F420 | 14,00 | Sub-Bass-Impact (Abschluss) | `sfx/sub_impact.wav` |

**KI-Bilder**

- `assets/s4_bg.jpg`: `Dark minimal background with neon purple and teal glow, soft bokeh light orbs, subtle haze, no text --ar 9:16`
- `assets/s4_fg.png` (freigestellt): `A hand holding a sleek glowing smartphone, the screen shows an open messaging app with one empty neon chat bubble, magenta rim light, isolated on a plain black background, photorealistic --ar 3:4`
- **Wichtig:** „MOTION“ nicht ins KI-Bild schreiben lassen, Bildgeneratoren verhunzen Schrift. Die Neon-Bubble „MOTION“ ist ein Overlay in HyperFrames (gestochen scharf, im Takt animierbar).

**Motion & Text**

| Frame | Element | Animation |
|---|---|---|
| F324–450 | Hintergrund | Scale 100 → 106 % linear |
| F330 | Handy (freigestellt) | Fährt von unten rein: y +500 → 0 in 14 F (`expo.out`) |
| F330 | **„KOMMENTIERE:“** (weiß, 150 px) | **Schießt von unten** ins Bild: y +1700 → 0 in 10 F (`expo.out`) |
| F330 | Konfetti (48 Teile, 6 Neonfarben) | Explodiert aus der Bubble-Mitte (540 \| 620): Radius 350–1000 px, Schwerkraft +380 px, Rotation bis ±720°, Fade-out über 36 F |
| F346 | **Neon-Bubble „MOTION“** | Pop 0 → 100 % in 8 F (`back.out(2.6)`) |
| F360 / 375 / 390 / 405 | Bubble | **Puls im Takt des Sub-Basses**: 109 % → 100 % in 8 F |
| F375 | Pfeil ↓ (doppelter Chevron, Mint, Glow) | Erscheint y −60 → 0 in 6 F (`back.out(2)`) |
| F390 / 405 / 420 / 435 | Pfeil | Hüpft 40 px nach unten und zurück (2 × 5 F) |
| F420 | Sub-Bass-Impact | Bubble 122 % → 100 % und Headline 112 % → 100 % in 12 F, weißer Blitz 35 % → 0 in 5 F, Shake 10 F / 34 px |
| F420–449 | Endbild | Halten (Screenshot-Moment) |

---

## Übergänge (in `index.html`)

| Frames | Typ | Ablauf |
|---|---|---|
| **F84–96** (S1 → S2) | Glitch-Schnitt | 12 Frames: alte/neue Szene flackern (vor dem Schnitt 25 %, danach 80 % neue Szene), Versatz alt ±60 px / neu ±40 px, 6 Farbbalken (Magenta/Cyan/Weiß/Violett, 6–76 px hoch, Blend `difference`) an wechselnden Höhen; harter Schnitt F90, ab F96 sauber |
| **F204–216** (S2 → S3) | Snap-Swoosh nach rechts | S2 x 0 → +1080 in 6 F (`power3.in`) + Motion-Blur 14 px; Schnitt F210; S3 x −1080 → 0 in 6 F (`power3.out`), Blur bis F214 |
| **F324–336** (S3 → S4) | Glitch-Schnitt | wie F84–96, Schnitt F330 |

Alle Zufallswerte (Shake, Glitch, Konfetti) laufen über einen festen Seed. Jeder Render ist dadurch identisch, das verlangt HyperFrames.

---

## Audio

**Musik** `audio/music_120bpm.wav` (selbst erzeugt, lizenzfrei): Kick auf jedem Beat, Clap auf 2 + 4, 16tel-Hats, 808-Sub D–D–C–E pro Takt, Synth-Stab alle 2 Takte. Der Drop sitzt auf F0. Kurze Kick-Pause auf Beat 13 (6,5 s), damit der Herzschlag frei steht. Lautstärke 0,45.

**Sprecher-Regie:** Deutsch, sehr energetisch, kurz und hart betont, ca. 180 Wörter/min. Jede Zeile auf den 120-BPM-Click aufnehmen. Höchstlängen: S1 2,8 s · S2 3,7 s · S3 3,9 s · S4 3,5 s. Als WAV 48 kHz in `audio/vo/` ablegen, gleiche Dateinamen. Danach mit `npx hyperframes audio audio/vo/s1.wav` die echten Wortzeiten messen und die oben genannten Wort-Anker angleichen.

**Mix:** Sprache 1,0 · SFX 0,55–0,95 · Musik 0,45. Ziel −14 LUFS. Mit `npx hyperframes normalize-audio` lassen sich die Pegel angleichen.

---

## Ablauf bis zum fertigen Video

1. KI-Bilder erzeugen. Je Szene einen Hintergrund ohne Hauptobjekt und das Hauptobjekt auf Schwarz.
2. Das Hauptobjekt freistellen und als PNG mit Alpha speichern (900 × 1200). Den Hintergrund als JPG speichern (mindestens 1080 × 1920).
3. Beide Dateien über die Platzhalter in `assets/` legen, mit gleichen Namen.
4. Sprache aufnehmen und als `audio/vo/s1.wav` bis `s4.wav` ablegen.
5. `npm run check` ausführen, dann mit `npx hyperframes snapshot --at 0,1,3.4,6.1,9.3,12.6` Standbilder prüfen.
6. `npm run render` ausführen, das Ergebnis liegt in `renders/motion-promo.mp4`.
