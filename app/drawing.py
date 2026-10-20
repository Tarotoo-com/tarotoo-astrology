"""Tarotoo's own drawing of a birth chart, in the site's dark style.

The positions come from Kerykeion (see chart.py); the picture is drawn here: the wheel
alone for the chat, or the full chart (wheel, placements, aspect grid, elements and
modes) to open on its own. Glyphs are Unicode characters shown as text, so no font or
artwork is bundled.
"""
from __future__ import annotations

import math
from html import escape

# The site's palette.
BG, PANEL, LINE, TEXT, MUTED, GOLD, PURPLE = "#1e1131", "#2a1845", "#4a3470", "#e6f3e8", "#a689d2", "#d2a17d", "#7b47c9"
ELEMENT_COLORS = {"Fire": "#e58f6f", "Earth": "#8fbf8a", "Air": "#e8c97a", "Water": "#7fa8e0"}
ASPECT_COLORS = {"trine": "#7fa8e0", "sextile": "#7fa8e0", "square": "#e58f6f", "opposition": "#e58f6f", "conjunction": GOLD}
TEXT_FONT = "Lexend, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
GLYPH_FONT = "'Segoe UI Symbol', 'Noto Sans Symbols 2', 'Noto Sans Symbols', 'Apple Symbols', 'DejaVu Sans', sans-serif"
TEXT_STYLE = "︎"  # show the glyph as a symbol, not as a coloured emoji
SOURCE_URL = "github.com/Tarotoo-com/tarotoo-astrology"

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGN_GLYPHS = "♈♉♊♋♌♍♎♏♐♑♒♓"
SIGN_ELEMENTS = ["Fire", "Earth", "Air", "Water"] * 3
BODY_GLYPHS = {"Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂", "Jupiter": "♃", "Saturn": "♄",
               "Uranus": "♅", "Neptune": "♆", "Pluto": "♇", "Mean_North_Lunar_Node": "☊", "Mean_South_Lunar_Node": "☋",
               "Ascendant": "AC", "Medium_Coeli": "MC"}
ASPECT_GLYPHS = {"conjunction": "☌", "opposition": "☍", "square": "□", "trine": "△", "sextile": "⚹"}
WHEEL_BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Mean_North_Lunar_Node"]

LABELS = {
    "en": {"title": "Birth chart", "planets": "Placements", "aspects": "Aspects", "elements": "Elements", "modes": "Modes",
           "house": "House", "unknown": "time unknown", "noHouses": "Without a birth time, houses and the Ascendant are not shown.",
           "elementNames": ["Fire", "Earth", "Air", "Water"], "modeNames": ["Cardinal", "Fixed", "Mutable"], "zodiac": "Tropical zodiac",
           "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "North Node", "South Node", "Ascendant", "Midheaven"],
           "signs": SIGNS},
    "es": {"title": "Carta natal", "planets": "Posiciones", "aspects": "Aspectos", "elements": "Elementos", "modes": "Modalidades",
           "house": "Casa", "unknown": "hora desconocida", "noHouses": "Sin hora de nacimiento no se muestran las casas ni el Ascendente.",
           "elementNames": ["Fuego", "Tierra", "Aire", "Agua"], "modeNames": ["Cardinal", "Fija", "Mutable"], "zodiac": "Zodiaco tropical",
           "bodies": ["Sol", "Luna", "Mercurio", "Venus", "Marte", "Júpiter", "Saturno", "Urano", "Neptuno", "Plutón", "Nodo Norte", "Nodo Sur", "Ascendente", "Medio Cielo"],
           "signs": ["Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo", "Libra", "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis"]},
    "fr": {"title": "Thème astral", "planets": "Positions", "aspects": "Aspects", "elements": "Éléments", "modes": "Modes",
           "house": "Maison", "unknown": "heure inconnue", "noHouses": "Sans heure de naissance, les maisons et l’Ascendant ne sont pas affichés.",
           "elementNames": ["Feu", "Terre", "Air", "Eau"], "modeNames": ["Cardinal", "Fixe", "Mutable"], "zodiac": "Zodiaque tropical",
           "bodies": ["Soleil", "Lune", "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton", "Nœud Nord", "Nœud Sud", "Ascendant", "Milieu du Ciel"],
           "signs": ["Bélier", "Taureau", "Gémeaux", "Cancer", "Lion", "Vierge", "Balance", "Scorpion", "Sagittaire", "Capricorne", "Verseau", "Poissons"]},
    "it": {"title": "Tema natale", "planets": "Posizioni", "aspects": "Aspetti", "elements": "Elementi", "modes": "Modalità",
           "house": "Casa", "unknown": "ora sconosciuta", "noHouses": "Senza l’ora di nascita le case e l’Ascendente non sono mostrati.",
           "elementNames": ["Fuoco", "Terra", "Aria", "Acqua"], "modeNames": ["Cardinale", "Fissa", "Mobile"], "zodiac": "Zodiaco tropicale",
           "bodies": ["Sole", "Luna", "Mercurio", "Venere", "Marte", "Giove", "Saturno", "Urano", "Nettuno", "Plutone", "Nodo Nord", "Nodo Sud", "Ascendente", "Medio Cielo"],
           "signs": ["Ariete", "Toro", "Gemelli", "Cancro", "Leone", "Vergine", "Bilancia", "Scorpione", "Sagittario", "Capricorno", "Acquario", "Pesci"]},
    "de": {"title": "Geburtshoroskop", "planets": "Stellungen", "aspects": "Aspekte", "elements": "Elemente", "modes": "Qualitäten",
           "house": "Haus", "unknown": "Uhrzeit unbekannt", "noHouses": "Ohne Geburtszeit werden Häuser und Aszendent nicht gezeigt.",
           "elementNames": ["Feuer", "Erde", "Luft", "Wasser"], "modeNames": ["Kardinal", "Fix", "Veränderlich"], "zodiac": "Tropischer Tierkreis",
           "bodies": ["Sonne", "Mond", "Merkur", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptun", "Pluto", "Mondknoten (N)", "Mondknoten (S)", "Aszendent", "Medium Coeli"],
           "signs": ["Widder", "Stier", "Zwillinge", "Krebs", "Löwe", "Jungfrau", "Waage", "Skorpion", "Schütze", "Steinbock", "Wassermann", "Fische"]},
    "pt": {"title": "Mapa astral", "planets": "Posições", "aspects": "Aspectos", "elements": "Elementos", "modes": "Modalidades",
           "house": "Casa", "unknown": "hora desconhecida", "noHouses": "Sem a hora de nascimento, as casas e o Ascendente não são mostrados.",
           "elementNames": ["Fogo", "Terra", "Ar", "Água"], "modeNames": ["Cardinal", "Fixo", "Mutável"], "zodiac": "Zodíaco tropical",
           "bodies": ["Sol", "Lua", "Mercúrio", "Vênus", "Marte", "Júpiter", "Saturno", "Urano", "Netuno", "Plutão", "Nodo Norte", "Nodo Sul", "Ascendente", "Meio do Céu"],
           "signs": ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes"]},
}
BODY_ORDER = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
              "Mean_North_Lunar_Node", "Mean_South_Lunar_Node", "Ascendant", "Medium_Coeli"]


def _t(x: float, y: float, text: str, size: float, fill: str = TEXT, anchor: str = "middle", weight: str = "400",
       font: str = TEXT_FONT, extra: str = "") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" dominant-baseline="central"{extra}>{escape(text)}</text>')


def _glyph(x, y, glyph, size, fill=TEXT):
    return _t(x, y, glyph + (TEXT_STYLE if len(glyph) == 1 else ""), size, fill, font=GLYPH_FONT)


class Wheel:
    """Longitudes to points on the wheel: the Ascendant on the left (the first point of
    Aries there when the birth time is unknown), the zodiac running counterclockwise."""

    def __init__(self, cx: float, cy: float, start: float):
        self.cx, self.cy, self.start = cx, cy, start

    def point(self, longitude: float, radius: float) -> tuple[float, float]:
        a = math.radians(180 + (longitude - self.start))
        return self.cx + radius * math.cos(a), self.cy - radius * math.sin(a)


def _spread(longitudes: list[float], gap: float = 7.5) -> list[float]:
    """Display longitudes for glyphs, pushed apart where planets are close together."""
    order = sorted(range(len(longitudes)), key=lambda i: longitudes[i])
    shown = {i: longitudes[i] for i in order}
    for _ in range(40):
        moved = False
        for k in range(len(order)):
            i, j = order[k], order[(k + 1) % len(order)]
            diff = (shown[j] - shown[i]) % 360
            if len(order) > 1 and diff < gap:
                push = (gap - diff) / 2
                shown[i] -= push
                shown[j] += push
                moved = True
        if not moved:
            break
    return [shown[i] for i in range(len(longitudes))]


def wheel_svg_parts(data: dict, cx: float, cy: float, r: float) -> list[str]:
    """The wheel as SVG elements, centred at (cx, cy) with outer radius r."""
    known = data["input"]["time_known"]
    angles = data.get("angles") or {}
    start = angles["ascendant"]["longitude"] if known and angles else 0.0
    w = Wheel(cx, cy, start)
    r_sign_in, r_house, r_inner = r * 0.84, r * 0.74, r * 0.56
    parts = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PANEL}" stroke="{LINE}" stroke-width="1.5"/>',
             f'<circle cx="{cx}" cy="{cy}" r="{r_sign_in:.1f}" fill="{BG}" stroke="{LINE}" stroke-width="1"/>',
             f'<circle cx="{cx}" cy="{cy}" r="{r_inner:.1f}" fill="none" stroke="{LINE}" stroke-width="1"/>']
    # Zodiac band: twelve signs, each glyph in its element's colour.
    for i in range(12):
        x1, y1 = w.point(i * 30, r)
        x2, y2 = w.point(i * 30, r_sign_in)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{LINE}" stroke-width="1"/>')
        gx, gy = w.point(i * 30 + 15, (r + r_sign_in) / 2)
        parts.append(_glyph(gx, gy, SIGN_GLYPHS[i], r * 0.085, ELEMENT_COLORS[SIGN_ELEMENTS[i]]))
        for d in range(5, 30, 5):
            tx1, ty1 = w.point(i * 30 + d, r_sign_in)
            tx2, ty2 = w.point(i * 30 + d, r_sign_in - (r * 0.025 if d % 10 else r * 0.04))
            parts.append(f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="{LINE}" stroke-width="1"/>')
    # Houses: cusp lines and numbers; the Ascendant and Midheaven axes stand out.
    if known and data.get("houses"):
        cusps = [h["longitude"] for h in data["houses"]]
        for n, lon in enumerate(cusps):
            x1, y1 = w.point(lon, r_sign_in)
            x2, y2 = w.point(lon, r_inner)
            axis = n in (0, 3, 6, 9)
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD if axis else LINE}" stroke-width="{2 if axis else 1}"/>')
            nxt = cusps[(n + 1) % 12]
            mid = lon + ((nxt - lon) % 360) / 2
            hx, hy = w.point(mid, r_inner + r * 0.04)
            parts.append(_t(hx, hy, str(n + 1), r * 0.04, MUTED))
        for key, label in (("ascendant", "AC"), ("midheaven", "MC")):
            lx, ly = w.point(angles[key]["longitude"], r + r * 0.07)
            parts.append(_t(lx, ly, label, r * 0.05, GOLD, weight="600"))
    # Aspect lines between the planets.
    pos = {p["name"]: p["longitude"] for p in data["planets"]}
    for a in data.get("aspects", []):
        if a["type"] in ASPECT_COLORS and a["type"] != "conjunction" and a["from"] in WHEEL_BODIES[:10] and a["to"] in WHEEL_BODIES[:10]:
            x1, y1 = w.point(pos[a["from"]], r_inner)
            x2, y2 = w.point(pos[a["to"]], r_inner)
            opacity = max(0.25, 0.9 - abs(a["orb"]) / 10)
            dash = ' stroke-dasharray="5 4"' if a["type"] == "sextile" else ""
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{ASPECT_COLORS[a["type"]]}" stroke-width="1.4" opacity="{opacity:.2f}"{dash}/>')
    # Planets: a tick at the true position, the glyph and degree where there is room.
    bodies = [p for p in data["planets"] if p["name"] in WHEEL_BODIES]
    shown = _spread([p["longitude"] for p in bodies])
    for p, at in zip(bodies, shown):
        tx1, ty1 = w.point(p["longitude"], r_sign_in)
        tx2, ty2 = w.point(p["longitude"], r_sign_in - r * 0.05)
        parts.append(f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="{TEXT}" stroke-width="1.5"/>')
        gx, gy = w.point(at, r * 0.68)
        parts.append(_glyph(gx, gy, BODY_GLYPHS[p["name"]], r * 0.075, GOLD if p["name"] in ("Sun", "Moon") else TEXT))
        dx, dy = w.point(at, r * 0.605)
        parts.append(_t(dx, dy, f'{int(p["position"])}°' + ("℞" if p["retrograde"] else ""), r * 0.032, MUTED))
    return parts


def _svg(width: float, height: float, body: list[str], title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}">'
            f'<title>{escape(title)}</title>' + "".join(body) + "</svg>")


def wheel_svg(data: dict, language: str = "en") -> str:
    labels = LABELS.get(language, LABELS["en"])
    size = 600
    body = [f'<rect width="{size}" height="{size}" fill="{BG}" rx="16"/>'] + wheel_svg_parts(data, size / 2, size / 2, 262)
    return _svg(size, size, body, labels["title"])


def full_svg(data: dict, language: str = "en") -> str:
    """The wheel with the placements, the aspect grid and the balance of elements and
    modes below it, one tall page that reads well on a phone."""
    L = LABELS.get(language, LABELS["en"])
    inp = data["input"]
    known = inp["time_known"]
    width, margin = 680, 32
    body = []
    y = 40
    title = L["title"] + (f' · {inp["name"]}' if inp.get("name") else "")
    body.append(_t(margin, y, title, 28, TEXT, "start", "600"))
    y += 34
    when = inp["date"] + " " + (inp["time"] or "") if known else f'{inp["date"]} ({L["unknown"]})'
    body.append(_t(margin, y, f'{when} · {inp["place"]}', 15, MUTED, "start"))
    y += 22
    house = (inp.get("house_system") or "placidus").replace("_", " ").title()
    body.append(_t(margin, y, L["zodiac"] + (f" · {house}" if known else ""), 13, MUTED, "start"))
    y += 18
    body += wheel_svg_parts(data, width / 2, y + 300, 270)
    y += 610
    if not known:
        body.append(_t(width / 2, y, L["noHouses"], 13, MUTED))
        y += 30

    # Placements.
    body.append(_t(margin, y, L["planets"], 20, GOLD, "start", "600"))
    y += 30
    points = {p["name"]: p for p in data["planets"]}
    if known and data.get("angles"):
        points["Ascendant"] = dict(data["angles"]["ascendant"], house=None)
        points["Medium_Coeli"] = dict(data["angles"]["midheaven"], house=None)
    for key in BODY_ORDER:
        p = points.get(key)
        if not p:
            continue
        sign = SIGNS.index(p["sign"])
        body.append(f'<rect x="{margin}" y="{y - 14}" width="{width - 2 * margin}" height="28" fill="{PANEL}" rx="6"/>')
        body.append(_glyph(margin + 20, y, BODY_GLYPHS[key], 17, GOLD))
        body.append(_t(margin + 44, y, L["bodies"][BODY_ORDER.index(key)], 15, TEXT, "start"))
        body.append(_glyph(margin + 300, y, SIGN_GLYPHS[sign], 16, ELEMENT_COLORS[SIGN_ELEMENTS[sign]]))
        body.append(_t(margin + 318, y, f'{L["signs"][sign]} {p["position_text"]}' + (" ℞" if p.get("retrograde") else ""), 15, TEXT, "start"))
        if known and p.get("house"):
            from .chart import HOUSE_ORDINALS
            number = HOUSE_ORDINALS.get(p["house"].replace("_House", ""), "")[:-2]
            body.append(_t(width - margin - 12, y, f'{L["house"]} {number}', 14, MUTED, "end"))
        y += 32
    y += 20

    # Aspect grid: each pair of points once, the aspect glyph and its orb.
    body.append(_t(margin, y, L["aspects"], 20, GOLD, "start", "600"))
    y += 22
    grid = [k for k in BODY_ORDER if k in points and k != "Mean_South_Lunar_Node"]
    cell = min(44, (width - 2 * margin - 40) / len(grid))
    found = {}
    for a in data.get("aspects", []):
        if a["type"] in ASPECT_GLYPHS:
            found[frozenset((a["from"], a["to"]))] = a
    gx0 = margin + 40
    for i, key in enumerate(grid):
        cy_ = y + i * cell + cell / 2
        body.append(_glyph(margin + 18, cy_, BODY_GLYPHS[key], 16, GOLD))
        for j in range(i):
            other = grid[j]
            x = gx0 + j * cell
            body.append(f'<rect x="{x:.1f}" y="{y + i * cell:.1f}" width="{cell - 2:.1f}" height="{cell - 2:.1f}" fill="{PANEL}" rx="4"/>')
            a = found.get(frozenset((key, other)))
            if a:
                body.append(_glyph(x + (cell - 2) / 2, y + i * cell + cell * 0.38, ASPECT_GLYPHS[a["type"]], 15, ASPECT_COLORS[a["type"]]))
                body.append(_t(x + (cell - 2) / 2, y + i * cell + cell * 0.74, f'{abs(a["orb"]):.0f}°', 9.5, MUTED))
    for j, key in enumerate(grid[:-1]):
        body.append(_glyph(gx0 + j * cell + (cell - 2) / 2, y + len(grid) * cell + 14, BODY_GLYPHS[key], 14, GOLD))
    y += len(grid) * cell + 50

    # Balance of the elements and modes.
    def bars(heading, names, values, colors):
        nonlocal y
        body.append(_t(margin, y, heading, 20, GOLD, "start", "600"))
        y += 28
        for name, value, color in zip(names, values, colors):
            body.append(_t(margin, y, name, 15, TEXT, "start"))
            body.append(f'<rect x="{margin + 140}" y="{y - 8}" width="{width - 2 * margin - 200}" height="16" fill="{PANEL}" rx="8"/>')
            body.append(f'<rect x="{margin + 140}" y="{y - 8}" width="{max(4, (width - 2 * margin - 200) * value / 100):.1f}" height="16" fill="{color}" rx="8"/>')
            body.append(_t(width - margin, y, f"{value}%", 14, MUTED, "end"))
            y += 28
        y += 16

    el = data.get("elements") or {}
    bars(L["elements"], L["elementNames"], [int(el.get(k + "_percentage", 0)) for k in ("fire", "earth", "air", "water")],
         [ELEMENT_COLORS[k] for k in ("Fire", "Earth", "Air", "Water")])
    mo = data.get("modes") or {}
    bars(L["modes"], L["modeNames"], [int(mo.get(k + "_percentage", 0)) for k in ("cardinal", "fixed", "mutable")], [PURPLE, GOLD, MUTED])
    body.append(_t(width / 2, y + 6, "tarotoo.com", 13, MUTED))
    # The service is free software (AGPL, as Kerykeion): its source is offered here.
    body.append(_t(width / 2, y + 26, f"Source: {SOURCE_URL}", 11, MUTED))
    height = y + 52
    return _svg(width, height, [f'<rect width="{width}" height="{height:.0f}" fill="{BG}"/>'] + body, title)
