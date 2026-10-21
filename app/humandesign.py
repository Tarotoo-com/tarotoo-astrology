"""Human Design chart and compatibility, on top of Kerykeion's planetary positions.

The Personality is the sky at birth; the Design is the sky when the Sun stood 88 degrees
of longitude earlier (about three months before birth). Each of the 13 bodies (Sun, Earth,
the true lunar nodes, Moon and the planets) falls in one of the 64 gates of the Rave
mandala and one of its six lines. A channel is defined when both of its gates are active
(in either chart); the centers at both ends of a defined channel are defined. Type,
authority, profile and definition follow from that.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import chart  # noqa: F401  (sets the ephemeris environment before Kerykeion loads)
from .chart import ChartError, birth_subject
from kerykeion import AstrologicalSubjectFactory  # noqa: E402

# Gates around the zodiac from 28°15' Pisces (where gate 25 begins), 5°37'30" each.
MANDALA = [25, 17, 21, 51, 42, 3, 27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56, 31, 33,
           7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50, 28, 44, 1, 43, 14, 34, 9, 5, 26, 11,
           10, 58, 38, 54, 61, 60, 41, 19, 13, 49, 30, 55, 37, 63, 22, 36]
MANDALA_START = 358.25
GATE_SPAN = 360 / 64

CENTERS = {
    "head": [64, 61, 63], "ajna": [47, 24, 4, 17, 43, 11],
    "throat": [62, 23, 56, 35, 12, 45, 33, 8, 31, 20, 16], "g": [7, 1, 13, 10, 25, 15, 46, 2],
    "heart": [21, 40, 26, 51], "sacral": [5, 14, 29, 59, 9, 3, 42, 27, 34],
    "solar_plexus": [36, 22, 37, 6, 49, 55, 30], "spleen": [48, 57, 44, 50, 32, 28, 18],
    "root": [53, 60, 52, 19, 39, 41, 58, 38, 54],
}
GATE_CENTER = {g: c for c, gates in CENTERS.items() for g in gates}
CHANNELS = [(1, 8), (2, 14), (3, 60), (4, 63), (5, 15), (6, 59), (7, 31), (9, 52), (10, 20), (10, 34), (10, 57),
            (11, 56), (12, 22), (13, 33), (16, 48), (17, 62), (18, 58), (19, 49), (20, 34), (20, 57), (21, 45),
            (23, 43), (24, 61), (25, 51), (26, 44), (27, 50), (28, 38), (29, 46), (30, 41), (32, 54), (34, 57),
            (35, 36), (37, 40), (39, 55), (42, 53), (47, 64)]
MOTORS = {"sacral", "solar_plexus", "heart", "root"}
BODIES = ["Sun", "Earth", "North_Node", "South_Node", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
          "Uranus", "Neptune", "Pluto"]
KERYKEION_POINTS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
                    "True_North_Lunar_Node", "True_South_Lunar_Node"]
STRATEGY = {"generator": "to respond", "manifesting_generator": "to respond, then inform", "manifestor": "to inform",
            "projector": "to wait for the invitation", "reflector": "to wait a lunar cycle"}
SIGNATURE = {"generator": ("satisfaction", "frustration"), "manifesting_generator": ("satisfaction", "frustration and anger"),
             "manifestor": ("peace", "anger"), "projector": ("success", "bitterness"), "reflector": ("surprise", "disappointment")}


def gate_line(longitude: float) -> tuple[int, int]:
    """Gate and line of an ecliptic longitude."""
    offset = (longitude - MANDALA_START) % 360
    index = int(offset // GATE_SPAN)
    line = int((offset - index * GATE_SPAN) // (GATE_SPAN / 6)) + 1
    return MANDALA[index], min(line, 6)


def _utc_subject(moment: datetime):
    return AstrologicalSubjectFactory.from_birth_data(
        name="Design", year=moment.year, month=moment.month, day=moment.day, hour=moment.hour, minute=moment.minute,
        seconds=moment.second, lng=0.0, lat=0.0, tz_str="UTC", online=False, active_points=KERYKEION_POINTS)


def _positions(s) -> dict[str, float]:
    sun = s.sun.abs_pos
    return {"Sun": sun, "Earth": (sun + 180) % 360, "North_Node": s.true_north_lunar_node.abs_pos,
            "South_Node": s.true_south_lunar_node.abs_pos, "Moon": s.moon.abs_pos, "Mercury": s.mercury.abs_pos,
            "Venus": s.venus.abs_pos, "Mars": s.mars.abs_pos, "Jupiter": s.jupiter.abs_pos, "Saturn": s.saturn.abs_pos,
            "Uranus": s.uranus.abs_pos, "Neptune": s.neptune.abs_pos, "Pluto": s.pluto.abs_pos}


def design_moment(birth_utc: datetime, natal_sun: float) -> datetime:
    """When the Sun was 88 degrees before its place at birth, to within a few seconds."""
    target = (natal_sun - 88) % 360
    moment = birth_utc - timedelta(days=89)
    for _ in range(8):
        sun = _utc_subject(moment).sun.abs_pos
        diff = ((target - sun + 180) % 360) - 180  # degrees still to go, signed
        if abs(diff) < 1e-5:
            break
        moment += timedelta(days=diff / 0.9856)
    return moment.replace(microsecond=0)


def _activations(positions: dict[str, float]) -> dict[str, dict]:
    out = {}
    for body in BODIES:
        g, l = gate_line(positions[body])
        out[body] = {"gate": g, "line": l, "longitude": round(positions[body], 4)}
    return out


def analyse(gates: set[int]) -> dict:
    """Channels, centers, type, authority and definition from a set of active gates."""
    channels = [c for c in CHANNELS if c[0] in gates and c[1] in gates]
    defined = sorted({GATE_CENTER[c[0]] for c in channels} | {GATE_CENTER[c[1]] for c in channels})
    links: dict[str, set[str]] = {c: set() for c in defined}
    for a, b in channels:
        ca, cb = GATE_CENTER[a], GATE_CENTER[b]
        links[ca].add(cb)
        links[cb].add(ca)

    def reach(start: str) -> set[str]:
        seen, todo = {start}, [start]
        while todo:
            for nxt in links.get(todo.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    groups, left = [], set(defined)
    while left:
        group = reach(next(iter(left)))
        groups.append(group)
        left -= group
    throat_group = reach("throat") if "throat" in defined else set()
    motor_to_throat = bool(throat_group & MOTORS)
    if not defined:
        kind = "reflector"
    elif "sacral" in defined:
        kind = "manifesting_generator" if motor_to_throat else "generator"
    else:
        kind = "manifestor" if motor_to_throat else "projector"
    if kind == "reflector":
        authority = "lunar"
    elif "solar_plexus" in defined:
        authority = "emotional"
    elif "sacral" in defined:
        authority = "sacral"
    elif "spleen" in defined:
        authority = "splenic"
    elif "heart" in defined:
        authority = "ego_manifested" if "throat" in links.get("heart", ()) else "ego_projected"
    elif "g" in defined and "throat" in links.get("g", ()):
        authority = "self_projected"
    else:
        authority = "mental"
    definition = ["none", "single", "split", "triple_split", "quadruple_split"][min(len(groups), 4)]
    return {"channels": [f"{a}-{b}" for a, b in channels], "defined_centers": defined, "type": kind,
            "authority": authority, "definition": definition}


def human_design(birth: dict, name: str = "") -> dict:
    """The chart for a birth (date, hour, minute, lat, lng, tz). The birth time matters:
    the Moon moves a gate in about ten hours, the profile line can change in a day."""
    if birth["hour"] is None or birth["minute"] is None:
        raise ChartError("Human Design needs the birth time.")
    d = birth["date"]
    natal, _ = birth_subject(name=name or "Birth", year=d.year, month=d.month, day=d.day, hour=birth["hour"],
                             minute=birth["minute"], lng=birth["lng"], lat=birth["lat"], tz_str=birth["tz"],
                             city=birth.get("place_label") or "Birthplace", nation=birth.get("country_code") or "",
                             online=False, active_points=KERYKEION_POINTS)
    birth_utc = datetime.fromisoformat(natal.iso_formatted_utc_datetime).astimezone(timezone.utc).replace(tzinfo=None)
    personality = _activations(_positions(natal))
    moment = design_moment(birth_utc, natal.sun.abs_pos)
    design = _activations(_positions(_utc_subject(moment)))
    gates = {a["gate"] for a in personality.values()} | {a["gate"] for a in design.values()}
    result = analyse(gates)
    p_line, d_line = personality["Sun"]["line"], design["Sun"]["line"]
    angle = "juxtaposition" if (p_line, d_line) == (4, 1) else "left_angle" if p_line >= 5 else "right_angle"
    cross = [personality["Sun"]["gate"], personality["Earth"]["gate"], design["Sun"]["gate"], design["Earth"]["gate"]]
    result.update({
        "name": name, "personality": personality, "design": design, "design_utc": moment.isoformat() + "Z",
        "profile": f"{p_line}/{d_line}", "cross": {"angle": angle, "gates": cross},
        "strategy": STRATEGY[result["type"]], "signature": SIGNATURE[result["type"]][0], "not_self": SIGNATURE[result["type"]][1],
        "gates": sorted(gates),
    })
    result["summary"] = summary(result)
    return result


NAMES = {"generator": "Generator", "manifesting_generator": "Manifesting Generator", "manifestor": "Manifestor",
         "projector": "Projector", "reflector": "Reflector", "emotional": "Emotional (solar plexus)", "sacral": "Sacral",
         "splenic": "Splenic", "ego_manifested": "Ego manifested", "ego_projected": "Ego projected",
         "self_projected": "Self-projected", "mental": "Mental (none inner)", "lunar": "Lunar",
         "none": "no definition", "single": "single definition", "split": "split definition",
         "triple_split": "triple split definition", "quadruple_split": "quadruple split definition",
         "right_angle": "Right Angle", "left_angle": "Left Angle", "juxtaposition": "Juxtaposition",
         "head": "Head", "ajna": "Ajna", "throat": "Throat", "g": "G (identity)", "heart": "Heart (ego)",
         "sacral_center": "Sacral", "solar_plexus": "Solar plexus", "spleen": "Spleen", "root": "Root"}


def center_name(c: str) -> str:
    return NAMES["sacral_center"] if c == "sacral" else NAMES[c]


def summary(r: dict) -> str:
    cross = r["cross"]["gates"]
    lines = [
        "Human Design chart (Personality at birth, Design when the Sun was 88 degrees earlier):",
        f"- Type: {NAMES[r['type']]}; strategy: {r['strategy']}; signature: {r['signature']}, not-self theme: {r['not_self']}",
        f"- Inner authority: {NAMES[r['authority']]}",
        f"- Profile: {r['profile']}; {NAMES[r['definition']]}",
        f"- Incarnation cross: {NAMES[r['cross']['angle']]}, gates {cross[0]}/{cross[1]} | {cross[2]}/{cross[3]}",
        "- Defined centers: " + (", ".join(center_name(c) for c in r["defined_centers"]) or "none"),
        "- Defined channels: " + (", ".join(r["channels"]) or "none"),
        "- Personality: " + ", ".join(f"{b.replace('_', ' ')} {a['gate']}.{a['line']}" for b, a in r["personality"].items()),
        "- Design: " + ", ".join(f"{b.replace('_', ' ')} {a['gate']}.{a['line']}" for b, a in r["design"].items()),
    ]
    return "\n".join(lines)


def compatibility(a: dict, b: dict) -> dict:
    """Two charts: channels that only form together (electromagnetic), channels both have
    (companionship), channels one brings alone (dominance), and the composite chart."""
    ga, gb = set(a["gates"]), set(b["gates"])
    ca, cb = set(a["channels"]), set(b["channels"])
    together = analyse(ga | gb)
    electro, companion, dominance = [], [], []
    for ch in together["channels"]:
        x, y = (int(v) for v in ch.split("-"))
        if ch in ca and ch in cb:
            companion.append(ch)
        elif ch in ca or ch in cb:
            dominance.append(ch)
        elif (x in ga and y in gb) or (x in gb and y in ga):
            electro.append(ch)
    names = [a.get("name") or "Person 1", b.get("name") or "Person 2"]
    lines = [f"Human Design compatibility of {names[0]} and {names[1]}:",
             f"- {names[0]}: {NAMES[a['type']]}, profile {a['profile']}, {NAMES[a['authority']]} authority",
             f"- {names[1]}: {NAMES[b['type']]}, profile {b['profile']}, {NAMES[b['authority']]} authority",
             "- Electromagnetic channels (formed only together, attraction): " + (", ".join(electro) or "none"),
             "- Companionship channels (both have them): " + (", ".join(companion) or "none"),
             "- Dominance channels (one brings them alone): " + (", ".join(dominance) or "none"),
             f"- Together: {NAMES[together['type']]}, {NAMES[together['definition']]}, defined centers: "
             + (", ".join(center_name(c) for c in together["defined_centers"]) or "none")]
    return {"names": names, "electromagnetic": electro, "companionship": companion, "dominance": dominance,
            "composite": together, "summary": "\n".join(lines)}


# ---- Bodygraph ----

BG, LINE, TEXT, GOLD = "#1e1131", "#4a3470", "#e6f3e8", "#d2a17d"
PERSONALITY, DESIGN = "#e6f3e8", "#e58f6f"
CENTER_COLORS = {"head": "#e8c97a", "ajna": "#8fbf8a", "throat": "#c79a6b", "g": "#e8c97a", "heart": "#e06c6c",
                 "spleen": "#c79a6b", "solar_plexus": "#c79a6b", "sacral": "#e06c6c", "root": "#c79a6b"}
# Where each center sits on a 320 x 560 page, and its shape.
LAYOUT = {"head": (160, 42, "up"), "ajna": (160, 122, "down"), "throat": (160, 205, "square"), "g": (160, 300, "diamond"),
          "heart": (232, 330, "small"), "spleen": (48, 410, "right"), "solar_plexus": (272, 410, "left"),
          "sacral": (160, 410, "square"), "root": (160, 500, "square")}


def _shape(center: str, fill: str, stroke: str) -> str:
    x, y, kind = LAYOUT[center]
    s = 25
    if kind == "square":
        return f'<rect x="{x - s}" y="{y - s}" width="{2 * s}" height="{2 * s}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    if kind == "diamond":
        return f'<polygon points="{x},{y - s - 6} {x + s + 6},{y} {x},{y + s + 6} {x - s - 6},{y}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    points = {"up": [(x, y - s), (x + s, y + s * .7), (x - s, y + s * .7)], "down": [(x - s, y - s * .7), (x + s, y - s * .7), (x, y + s)],
              "right": [(x - s * .7, y - s), (x + s, y), (x - s * .7, y + s)], "left": [(x + s * .7, y - s), (x - s, y), (x + s * .7, y + s)],
              "small": [(x - 20, y + 16), (x + 20, y + 16), (x, y - 18)]}[kind]
    return '<polygon points="' + " ".join(f"{px:.0f},{py:.0f}" for px, py in points) + f'" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def bodygraph_svg(r: dict, title: str = "Human Design") -> str:
    """The nine centers, every channel as a faint line, defined channels in the colour of
    the side that activates them (light: Personality, orange: Design, both side by side)."""
    by_gate: dict[int, set[str]] = {}
    for side, acts in (("p", r["personality"]), ("d", r["design"])):
        for a in acts.values():
            by_gate.setdefault(a["gate"], set()).add(side)
    pair_count: dict[frozenset, int] = {}
    lines = []
    for a, b in CHANNELS:
        ca, cb = GATE_CENTER[a], GATE_CENTER[b]
        key = frozenset((ca, cb))
        k = pair_count.get(key, 0)
        pair_count[key] = k + 1
        (x1, y1, _), (x2, y2, _) = LAYOUT[ca], LAYOUT[cb]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5 or 1
        nx, ny = -dy / length, dx / length
        off = (k - 0.5 * (sum(1 for c in CHANNELS if frozenset((GATE_CENTER[c[0]], GATE_CENTER[c[1]])) == key) - 1)) * 9
        ox, oy = nx * off, ny * off
        seg = f'x1="{x1 + ox:.1f}" y1="{y1 + oy:.1f}" x2="{x2 + ox:.1f}" y2="{y2 + oy:.1f}"'
        name = f"{a}-{b}"
        if name in r["channels"]:
            sides = by_gate.get(a, set()) | by_gate.get(b, set())
            if sides == {"p", "d"}:
                lines.append(f'<line {seg} stroke="{PERSONALITY}" stroke-width="5" stroke-linecap="round"/>')
                lines.append(f'<line {seg} stroke="{DESIGN}" stroke-width="5" stroke-linecap="round" stroke-dasharray="7 7"/>')
            else:
                lines.append(f'<line {seg} stroke="{PERSONALITY if sides == {"p"} else DESIGN}" stroke-width="5" stroke-linecap="round"/>')
        else:
            lines.append(f'<line {seg} stroke="{LINE}" stroke-width="3" stroke-linecap="round"/>')
    shapes = [_shape(c, CENTER_COLORS[c] if c in r["defined_centers"] else BG, CENTER_COLORS[c] if c in r["defined_centers"] else "#a689d2")
              for c in LAYOUT]
    legend = (f'<rect x="20" y="540" width="14" height="6" rx="3" fill="{PERSONALITY}"/>'
              f'<text x="40" y="546" font-family="Lexend, Helvetica, Arial, sans-serif" font-size="11" fill="{TEXT}">Personality</text>'
              f'<rect x="200" y="540" width="14" height="6" rx="3" fill="{DESIGN}"/>'
              f'<text x="220" y="546" font-family="Lexend, Helvetica, Arial, sans-serif" font-size="11" fill="{TEXT}">Design</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 560" width="320" height="560">'
            f'<title>{title}</title><rect width="320" height="560" rx="16" fill="{BG}"/>'
            + "".join(lines) + "".join(shapes) + legend + "</svg>")
