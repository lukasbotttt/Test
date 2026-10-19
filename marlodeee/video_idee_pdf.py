"""Erzeugt die PDF 'Video-Idee: Atemlos x Schranz' für @marlodeee.

Aufruf: python3 video_idee_pdf.py  ->  marlodeee_video_idee.pdf
"""
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "hockey-reel" / "fonts"
pdfmetrics.registerFont(TTFont("Anton", str(FONTS / "Anton.ttf")))
pdfmetrics.registerFont(TTFont("Body", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("BodyB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyB")

W, H = A4
M = 46  # Rand
BG = HexColor("#0c0c0f")
CARD = HexColor("#18181d")
LINE = HexColor("#2a2a31")
RED = HexColor("#e5252f")
WHITE = HexColor("#f4f1ec")
GREY = HexColor("#a4a2ab")

BODY = ParagraphStyle("body", fontName="Body", fontSize=10.2, leading=15, textColor=WHITE,
                      alignment=TA_LEFT)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.8, leading=12.5, textColor=GREY)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9.2, leading=13)
CELLH = ParagraphStyle("cellh", parent=CELL, fontName="BodyB", textColor=GREY, fontSize=8.2)


def page_bg(c, num, total):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(RED)
    c.rect(0, H - 6, W, 6, fill=1, stroke=0)
    c.setFont("Body", 7.5)
    c.setFillColor(GREY)
    c.drawString(M, 24, "@marlodeee  ·  Video-Idee  ·  Atemlos x Schranz")
    c.drawRightString(W - M, 24, f"{num} / {total}")


def kicker(c, y, txt):
    c.setFont("BodyB", 8.5)
    c.setFillColor(RED)
    c.drawString(M, y, " ".join(txt.upper()))
    return y - 14


def headline(c, y, txt, size=34, color=WHITE):
    c.setFont("Anton", size)
    c.setFillColor(color)
    c.drawString(M, y - size * 0.8, txt)
    return y - size * 1.15


def para(c, x, y, w, html, style=BODY):
    p = Paragraph(html, style)
    _, h = p.wrap(w, 1000)
    p.drawOn(c, x, y - h)
    return y - h


def card(c, x, y, w, h, fill=CARD):
    c.setFillColor(fill)
    c.roundRect(x, y - h, w, h, 8, fill=1, stroke=0)


def table(c, y, rows, widths, head=True):
    data = [[Paragraph(str(v), CELLH if (head and i == 0) else CELL) for v in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    if head:
        st.append(("LINEBELOW", (0, 0), (-1, 0), 1.2, RED))
    t.setStyle(TableStyle(st))
    _, h = t.wrap(W - 2 * M, 1000)
    t.drawOn(c, M, y - h)
    return y - h


def bullets(c, x, y, w, items, gap=5, style=BODY):
    for it in items:
        c.setFillColor(RED)
        c.rect(x, y - 10, 5, 5, fill=1, stroke=0)
        y = para(c, x + 14, y, w - 14, it, style) - gap
    return y


# ---------------------------------------------------------------- Seiten
def p_cover(c):
    c.setFillColor(RED)
    c.rect(M, H - 150, 52, 4, fill=1, stroke=0)
    y = kicker(c, H - 170, "Video-Idee für @marlodeee")
    c.setFont("Anton", 92)
    c.setFillColor(WHITE)
    c.drawString(M - 3, y - 80, "ATEMLOS")
    c.setFillColor(RED)
    c.drawString(M - 3, y - 175, "x SCHRANZ")
    y -= 210
    y = para(c, M, y, 380,
             "Helene Fischer auf <b>160 BPM</b>: ein Reel, das die drei Dinge kombiniert, die "
             "auf deinem Account nachweislich funktionieren.", ParagraphStyle(
                 "lead", parent=BODY, fontSize=13, leading=19)) - 34

    y = kicker(c, y, "Warum genau dieses Video")
    cw = (W - 2 * M - 24) / 3
    cards = [("1.390", "Views", "Blümchen x Scooter x Schranz bekam mit 8 Kommentaren die "
              "meisten Kommentare. Schlager trifft Schranz polarisiert."),
             ("34", "Likes", "Bad Bunny x Schranz hat die meisten Likes. Ein bekannter Name im "
              "Hook holt Leute, die dich nicht kennen."),
             ("177", "Views", "„Transition of the Day“ ohne bekannten Namen war dein schwächstes "
              "Reel. Underground-Tracks erreichen nur die Szene.")]
    for k, (num, unit, txt) in enumerate(cards):
        x = M + k * (cw + 12)
        card(c, x, y, cw, 150)
        c.setFont("Anton", 34)
        c.setFillColor(RED if k < 2 else GREY)
        c.drawString(x + 14, y - 46, num)
        c.setFont("BodyB", 8)
        c.setFillColor(GREY)
        c.drawString(x + 16 + pdfmetrics.stringWidth(num, "Anton", 34), y - 46, " " + unit.upper())
        para(c, x + 14, y - 60, cw - 28, txt, SMALL)
    y -= 178
    para(c, M, y, W - 2 * M,
         "Datenbasis: deine 12 öffentlichen Reels vom 14.–18. Oktober 2026 "
         "(insgesamt ca. 10.700 Views, im Schnitt 890 pro Reel).", SMALL)


def phone(c, x, y, w, label, time, lines, flash=False, small=None):
    h = w * 16 / 9
    c.setFillColor(HexColor("#1a0608") if flash else HexColor("#121216"))
    c.roundRect(x, y - h, w, h, 10, fill=1, stroke=0)
    # angedeutete Person + Pult
    c.setFillColor(HexColor("#2b0d10") if flash else HexColor("#1f1f25"))
    c.circle(x + w / 2, y - h * 0.47, w * 0.13, fill=1, stroke=0)
    c.roundRect(x + w * 0.22, y - h * 0.82, w * 0.56, h * 0.28, 12, fill=1, stroke=0)
    c.setFillColor(HexColor("#26262d"))
    c.rect(x + w * 0.08, y - h * 0.93, w * 0.84, h * 0.09, fill=1, stroke=0)
    if flash:
        c.setFillColor(RED)
        c.setFillAlpha(0.18)
        c.roundRect(x, y - h, w, h, 10, fill=1, stroke=0)
        c.setFillAlpha(1)
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.roundRect(x, y - h, w, h, 10, fill=0, stroke=1)
    ty = y - 42
    for txt, size, col in lines:
        c.setFont("Anton", size)
        c.setFillColor(col)
        c.drawCentredString(x + w / 2, ty, txt)
        ty -= size * 1.15
    if small:
        c.setFont("BodyB", 6)
        c.setFillColor(WHITE)
        c.drawRightString(x + w - 8, y - 14, small)
    c.setFont("BodyB", 8)
    c.setFillColor(RED)
    c.drawString(x, y - h - 16, time)
    c.setFont("Body", 8)
    c.setFillColor(GREY)
    c.drawString(x, y - h - 28, label)


def p_storyboard(c):
    y = kicker(c, H - 60, "Storyboard · 12–15 Sekunden")
    y = headline(c, y, "SO LÄUFT DAS REEL AB")
    pw = (W - 2 * M - 3 * 12) / 4
    frames = [
        ("Ernster Blick, Finger auf Play", "0 – 1,5 s",
         [("„ATEMLOS“", 16, WHITE), ("AUF 160 BPM", 16, RED)], False),
        ("Play drücken, Zoom auf Hand", "1,5 – 3 s",
         [("VERBRECHEN", 15, WHITE), ("ODER BANGER?", 15, RED)], False),
        ("DROP. Kamera tief, rotes Licht", "3 – 10 s", [], True),
        ("Abrupter Stopp, Blick in Kamera", "10 – 13 s",
         [("WEN SOLL ICH", 13, WHITE), ("ALS NÄCHSTES", 13, WHITE), ("ZERSTÖREN?", 13, RED)],
         False),
    ]
    for k, (lab, tm, lines, fl) in enumerate(frames):
        phone(c, M + k * (pw + 12), y - 4, pw, lab, tm, lines, fl, "TAG 25/365")
    y -= pw * 16 / 9 + 52
    y = table(c, y, [
        ["Zeit", "Bild", "Ton", "Text im Bild"],
        ["0 – 1,5 s", "Nahaufnahme Gesicht, ernster Blick, Finger über Play",
         "Original „Atemlos“, leise und fröhlich", "<b>„Atemlos“ auf 160 BPM</b>"],
        ["1,5 – 3 s", "Er drückt Play, schneller Zoom auf die Hand", "Kurzer Aufbau, Snare-Roll",
         "<b>Verbrechen oder Banger?</b>"],
        ["3 – 10 s", "<b>Drop.</b> Kamera tief, er geht ab, rotes Licht flackert",
         "Harte Schranz-Kick unter Helenes Gesang", "–"],
        ["10 – 13 s", "Abrupter Stopp, Blick zurück in die Kamera", "Stille oder Plattenstopp",
         "<b>Wen soll ich als Nächstes zerstören?</b>"],
        ["immer", "–", "–", "klein in der Ecke: <b>Tag 25/365</b>"],
    ], [58, 160, 140, W - 2 * M - 358]) - 16
    card(c, M, y, W - 2 * M, 50, HexColor("#2a0b0e"))
    para(c, M + 14, y - 10, W - 2 * M - 28,
         "<b>Wichtig:</b> Der Drop kommt spätestens nach 3 Sekunden. Das Ende schneidet abrupt "
         "ab, damit das Video sofort wieder von vorn startet: Wiederholungen pushen die Reichweite.")


def p_setup(c):
    y = kicker(c, H - 60, "Dreh, Cover, Caption")
    y = headline(c, y, "SO SIEHT ES NACH RAVE AUS")
    colw = (W - 2 * M - 20) / 2
    top = y
    card(c, M, top, colw, 200)
    para(c, M + 14, top - 14, colw - 28, "<b>Dreh-Setup (5 Minuten)</b>")
    bullets(c, M + 14, top - 38, colw - 28, [
        "Deckenlicht aus, rote LED-Leiste oder Taschenlampe hinter roter Folie, Licht von "
        "hinten oder von der Seite",
        "Handy hochkant auf Tischhöhe, leicht von unten: wirkt nach Bühne statt Zimmer",
        "Dunkles Outfit, die Cap als Markenzeichen",
        "Den Drop 2–3× drehen und den energischsten Take nehmen",
    ], 4, SMALL)
    x2 = M + colw + 20
    card(c, x2, top, colw, 200)
    para(c, x2 + 14, top - 14, colw - 28, "<b>Cover</b>")
    # Cover-Mockup
    cw, ch = 74, 74 * 16 / 9
    cx, cy = x2 + 14, top - 40
    c.setFillColor(HexColor("#2b0d10"))
    c.roundRect(cx, cy - ch, cw, ch, 6, fill=1, stroke=0)
    c.setFont("Anton", 15)
    c.setFillColor(WHITE)
    c.drawCentredString(cx + cw / 2, cy - ch / 2 + 6, "HELENE")
    c.setFillColor(RED)
    c.drawCentredString(cx + cw / 2, cy - ch / 2 - 12, "x SCHRANZ")
    para(c, cx + cw + 14, cy, colw - cw - 56,
         "Standbild vom Drop (Bewegung, rotes Licht) mit großem Text "
         "<b>HELENE x SCHRANZ</b>. Im Profilraster muss man es in einer halben Sekunde lesen "
         "können.", SMALL)
    y = top - 224

    y = kicker(c, y, "Caption")
    card(c, M, y, W - 2 * M, 112)
    para(c, M + 16, y - 14, W - 2 * M - 32,
         "Helene Fischer auf 160 BPM… <b>Verbrechen oder Banger?</b> Schreib mir, wen ich als "
         "Nächstes zerstören soll!<br/><br/>Tag 25/365 bis zum Festival-Gig<br/><br/>"
         "<font color='#e5252f'>#schranz #hardtechno #schranzremix #helenefischer #techno</font>")
    para(c, M, y - 124, W - 2 * M,
         "Emojis nach Geschmack ergänzen (z. B. Lachen und Feuer nach der Frage). Die erste Zeile "
         "trägt Hook und Frage, denn die Instagram-Suche liest Captions mit. Statt #dj und "
         "#musik lieber wenige, genaue Hashtags.", SMALL)


def p_bpm(c):
    y = kicker(c, H - 60, "Der BPM-Workflow")
    y = headline(c, y, "VON 128 AUF 160 BPM")
    y = para(c, M, y, W - 2 * M,
             "„Atemlos durch die Nacht“ liegt bei etwa <b>128 BPM</b>, Schranz meistens bei "
             "<b>150–165 BPM</b>. Auf 160 sind das <b>+25 %</b>: zu viel für den normalen "
             "Pitch-Fader, aber gut machbar. Drei Wege, vom schnellsten zum saubersten:") - 16

    def block(y, num, title, tag, items, h):
        card(c, M, y, W - 2 * M, h)
        c.setFont("Anton", 30)
        c.setFillColor(RED)
        c.drawString(M + 16, y - 40, num)
        c.setFont("BodyB", 11)
        c.setFillColor(WHITE)
        c.drawString(M + 56, y - 22, title)
        c.setFont("Body", 8.5)
        c.setFillColor(GREY)
        c.drawString(M + 56, y - 36, tag)
        bullets(c, M + 56, y - 50, W - 2 * M - 72, items, 2, SMALL)
        return y - h - 12

    y = block(y, "1", "Live am Controller (rekordbox + DDJ-FLX4)", "5 Minuten · ideal zum Testen", [
        "Deck 1: Schranz-Track oder Kick-Loop auf 160 BPM. Deck 2: „Atemlos“ mit "
        "<b>Master Tempo (Key Lock) an</b>",
        "Tempobereich auf <b>WIDE</b> stellen: ±10/16 % reichen nicht für +25 %",
        "Atemlos auf Deck 1 syncen, nur die <b>Vocals</b> offen lassen: Stems, falls verfügbar, "
        "sonst Bässe und Mitten am EQ ganz raus",
        "Refrain auf den Drop legen und loopen. Leichte Stretching-Artefakte sind im Reel egal",
    ], 140)
    y = block(y, "2", "Sped-up statt Key Lock", "der aktuelle Trend-Sound", [
        "Master Tempo <b>aus</b>, einfach schneller abspielen: Helene klingt rund "
        "4 Halbtöne höher",
        "Absichtlich überdreht, polarisiert noch mehr und passt zu „Verbrechen oder Banger?“",
        "<b>Tipp:</b> beide Versionen aufnehmen und die stärkere posten",
    ], 96)
    y = block(y, "3", "Richtiger Bootleg in der DAW", "Ableton / FL Studio · für Release", [
        "Vocals freistellen: Ultimate Vocal Remover (kostenlos), Demucs oder rekordbox-Stems",
        "Vocal auf 160 BPM warpen (Ableton: „Complex Pro“ klingt am saubersten)",
        "Aufbau: <b>Intro</b> 8 Takte „Atemlos durch die Nacht…“ mit gefilterter Kick, "
        "<b>Build</b> mit Snare-Roll und Chop „Atemlos – los – los“, <b>Drop</b> mit "
        "rollender, verzerrter Kick",
        "Vocal unter ~200 Hz wegschneiden und per Sidechain an die Kick koppeln",
        "Tonart mit rekordbox oder Mixed In Key bestimmen, Loop passend wählen oder Vocal um "
        "1–2 Halbtöne verschieben",
    ], 150)
    colw = (W - 2 * M - 12) / 2
    card(c, M, y, colw, 82, HexColor("#2a0b0e"))
    para(c, M + 14, y - 12, colw - 28,
         "<b>Welche BPM?</b> 155–160: schnell genug für „krank“, noch tanzbar. Steht im Video "
         "160 BPM, muss es auch 160 sein. Die Szene hört das.", SMALL)
    card(c, M + colw + 12, y, colw, 82)
    para(c, M + colw + 26, y - 12, colw - 28,
         "<b>Rechte:</b> Im Reel ist so ein Edit üblich. Als Gratis-Download auf SoundCloud "
         "kann ein Bootleg gesperrt werden. Dann lieber Snippets posten oder den Download per "
         "DM-Link verteilen.", SMALL)


def p_post(c):
    y = kicker(c, H - 60, "Posten & danach")
    y = headline(c, y, "DIE ERSTE STUNDE ENTSCHEIDET")
    y = table(c, y, [
        ["Wann", "Was", "Warum"],
        ["Vorher", "An dem Tag <b>nichts anderes</b> posten",
         "Das Reel soll nicht mit deinen eigenen Reels um Aufmerksamkeit konkurrieren"],
        ["17–20 Uhr", "Posten", "Deine stärksten Reels liefen nachmittags und abends, Nacht- "
         "und Morgen-Posts am schwächsten"],
        ["Erste Stunde", "Jeden Kommentar beantworten, einen lustigen anpinnen",
         "Frühe Interaktion signalisiert: Dieses Reel lohnt sich"],
        ["Kritik", "Locker antworten oder per Video („Ihr meintet, das ist Schrott…“)",
         "Deine Antwort „Lass es lieber“ unter Blümchen x Scooter bekam 6 Likes"],
        ["Teil 2", "Meistgewünschten Künstler aus den Kommentaren nehmen",
         "„Ihr wolltet X, hier ist er“: aus einem Reel wird eine Serie"],
    ], [80, 200, W - 2 * M - 280]) - 26

    y = kicker(c, y, "Woran du Erfolg misst")
    kw = (W - 2 * M - 24) / 3
    for k, (v, lab) in enumerate([("> 1.500", "Views nach 48 h (dein Schnitt: 890)"),
                                  ("> 3 %", "Likes pro View (bisher 1,6 %)"),
                                  ("> 10", "Kommentare (Rekord bisher: 8)")]):
        x = M + k * (kw + 12)
        card(c, x, y, kw, 74)
        c.setFont("Anton", 26)
        c.setFillColor(RED)
        c.drawString(x + 14, y - 36, v)
        para(c, x + 14, y - 44, kw - 28, lab, SMALL)
    y -= 92
    para(c, M, y, W - 2 * M,
         "In den Insights zusätzlich auf <b>Wiedergabedauer, Shares und Saves</b> achten. "
         "Bleiben die meisten nicht die ersten 3 Sekunden, muss der Einstieg härter werden.",
         SMALL)
    y -= 46

    y = kicker(c, y, "Plan B")
    card(c, M, y, W - 2 * M, 96)
    c.setFont("Anton", 19)
    c.setFillColor(WHITE)
    c.drawString(M + 16, y - 32, "3 SONGS, DIE MAN NIE AUF EINEM RAVE SPIELEN SOLLTE…")
    c.setFillColor(RED)
    c.drawString(M + 16, y - 54, "…AUSSER ALS SCHRANZ")
    para(c, M + 16, y - 64, W - 2 * M - 32,
         "Drei Mini-Drops à 3 Sekunden (z. B. Atemlos, Last Christmas, Macarena). Kombiniert "
         "Listenformat (dein Reichweiten-Hit), Humor und Mashup, falls der Atemlos-Mix noch "
         "nicht fertig ist.", SMALL)


def main():
    out = HERE / "marlodeee_video_idee.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)
    c.setTitle("Video-Idee: Atemlos x Schranz")
    c.setAuthor("Video-Idee für @marlodeee")
    pages = [p_cover, p_storyboard, p_setup, p_bpm, p_post]
    for i, fn in enumerate(pages, 1):
        page_bg(c, i, len(pages))
        fn(c)
        c.showPage()
    c.save()
    print(out)


if __name__ == "__main__":
    main()
