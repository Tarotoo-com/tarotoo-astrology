"""Natal chart calculation on top of Kerykeion.

Everything astronomical comes from Kerykeion (libephemeris, NASA JPL data). This
module only shapes the request and the response for the Tarotoo site.
"""
from __future__ import annotations

import os
import tempfile
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Keep the ephemeris offline and quiet: the bundled base tier covers 1850-2150.
os.environ.setdefault("LIBEPHEMERIS_IERS_AUTO_DOWNLOAD", "false")
os.environ.setdefault("LIBEPHEMERIS_LOG_LEVEL", "ERROR")
# libephemeris creates a data folder in the home directory, which serverless platforms
# mount read-only; fall back to the temp directory there.
if "LIBEPHEMERIS_DATA_DIR" not in os.environ and not os.access(os.path.expanduser("~"), os.W_OK):
    os.environ["LIBEPHEMERIS_DATA_DIR"] = os.path.join(tempfile.gettempdir(), "libephemeris")

from kerykeion import AstrologicalSubjectFactory, ChartDataFactory  # noqa: E402
from kerykeion.schemas import KerykeionException  # noqa: E402

# Bodies shown in the chart. Chiron and the asteroids are left out: they are not in
# the bundled ephemeris and would fall back to an approximation.
ACTIVE_POINTS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus",
    "Neptune", "Pluto", "Mean_North_Lunar_Node", "Mean_South_Lunar_Node",
    "Ascendant", "Medium_Coeli", "Descendant", "Imum_Coeli",
]
PLANETS = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus",
           "neptune", "pluto", "mean_north_lunar_node", "mean_south_lunar_node"]
HOUSES = ["first_house", "second_house", "third_house", "fourth_house", "fifth_house",
          "sixth_house", "seventh_house", "eighth_house", "ninth_house", "tenth_house",
          "eleventh_house", "twelfth_house"]
SIGN_NAMES = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer", "Leo": "Leo",
    "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio", "Sag": "Sagittarius",
    "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}
HOUSE_SYSTEMS = {"placidus": "P", "whole_sign": "W", "koch": "K", "equal": "A"}
# Site languages that Kerykeion can label the wheel in.
CHART_LANGUAGES = {"en": "EN", "es": "ES", "fr": "FR", "it": "IT", "de": "DE", "pt": "PT"}
# The bundled ephemeris tier covers 1850-01-01 to 2150-01-01; whole years inside it.
MIN_YEAR, MAX_YEAR = 1850, 2149
ANGLES = ["Ascendant", "Medium_Coeli", "Descendant", "Imum_Coeli"]
HOUSE_SYSTEM_NAMES = {"placidus": "Placidus", "whole_sign": "whole sign", "koch": "Koch", "equal": "equal"}


class ChartError(ValueError):
    """A request that cannot be turned into a chart. The message is safe to show."""


def birth_subject(**kwargs):
    """Kerykeion's subject, also for a birth time in the hour the clocks change. A time
    that happened twice (clocks back) is read as the first, summer-time occurrence; a time
    that never happened (clocks forward) is read with the offset before the change, as
    Python does. Returns (subject, note) where note is None, "ambiguous" or "nonexistent"."""
    try:
        return AstrologicalSubjectFactory.from_birth_data(**kwargs), None
    except KerykeionException as error:
        text = str(error)
        if "Ambiguous time" in text:
            return AstrologicalSubjectFactory.from_birth_data(**kwargs, is_dst=True), "ambiguous"
        if "Non-existent time" in text:
            return AstrologicalSubjectFactory.from_birth_data(**kwargs, is_dst=False), "nonexistent"
        raise ChartError("The chart could not be calculated for this birth data.") from error


def _dms(position: float) -> str:
    degrees = int(position)
    minutes = int(round((position - degrees) * 60))
    if minutes == 60:
        degrees, minutes = degrees + 1, 0
    return f"{degrees}°{minutes:02d}′"


def _point(p) -> dict:
    return {
        "name": p.name,
        "sign": SIGN_NAMES[p.sign],
        "sign_abbr": p.sign,
        "position": round(p.position, 4),
        "position_text": _dms(p.position),
        "longitude": round(p.abs_pos, 4),
        "house": p.house,
        "retrograde": bool(p.retrograde),
        "element": p.element,
        "quality": p.quality,
    }


def build_chart(
    *,
    name: str,
    birth_date: date,
    hour: int | None,
    minute: int | None,
    lat: float,
    lng: float,
    tz: str,
    place_label: str,
    country_code: str,
    house_system: str = "placidus",
    theme: str = "dark",
    layout: str = "wheel",
    language: str = "en",
) -> dict:
    """Return the chart as a dict: positions, houses, aspects, SVG and a text summary.

    layout "wheel" gives the wheel alone (square, readable on a phone; the page shows its
    own placements table); "full" gives the complete chart: the wheel, the placements, the
    aspect grid and the balance of elements and modes. Both are Tarotoo's own drawing
    (drawing.py) in the site's dark style; theme is kept for the API but not used.
    """
    if not MIN_YEAR <= birth_date.year <= MAX_YEAR:
        raise ChartError(f"Birth years from {MIN_YEAR} to {MAX_YEAR} are supported.")
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ChartError("Unknown time zone for the birthplace.")
    if house_system not in HOUSE_SYSTEMS:
        raise ChartError("Unknown house system.")

    time_known = hour is not None and minute is not None
    # Without a birth time the angles of a noon chart mean nothing, so they are left out
    # of the points (and so of the aspects).
    subject, time_note = birth_subject(
        name=name or "Birth chart",
        year=birth_date.year, month=birth_date.month, day=birth_date.day,
        hour=hour if time_known else 12, minute=minute if time_known else 0,
        city=place_label or "Birthplace", nation=country_code or "",
        lng=lng, lat=lat, tz_str=tz, online=False,
        houses_system_identifier=HOUSE_SYSTEMS[house_system],
        active_points=ACTIVE_POINTS if time_known else [p for p in ACTIVE_POINTS if p not in ANGLES],
    )
    chart_data = ChartDataFactory.create_natal_chart_data(subject)

    data = subject.model_dump()
    planets = [_point(getattr(subject, key)) for key in PLANETS]
    houses = [
        {"house": i + 1, "sign": SIGN_NAMES[data[key]["sign"]], "longitude": round(data[key]["abs_pos"], 4),
         "position": round(data[key]["position"], 4), "position_text": _dms(data[key]["position"])}
        for i, key in enumerate(HOUSES)
    ]
    angles = {
        "ascendant": _point(subject.ascendant),
        "midheaven": _point(subject.medium_coeli),
        "descendant": _point(subject.descendant),
        "imum_coeli": _point(subject.imum_coeli),
    }
    aspects = sorted((
        {"from": a.p1_name, "to": a.p2_name, "type": a.aspect, "orb": round(a.orbit, 2)}
        for a in chart_data.aspects
        if time_known or (a.p1_name not in ANGLES and a.p2_name not in ANGLES)
    ), key=lambda a: abs(a["orb"]))
    if not time_known:
        # Without a birth time the houses and angles are unknown; the Moon moves
        # about 13 degrees a day, so its sign may differ at the true time.
        houses, angles = [], None
        for p in planets:
            p["house"] = None

    result = {
        "input": {
            "name": name, "date": birth_date.isoformat(),
            "time": f"{hour:02d}:{minute:02d}" if time_known else None,
            "time_known": time_known, "place": place_label, "country": country_code,
            "lat": lat, "lng": lng, "timezone": tz,
            "utc": subject.iso_formatted_utc_datetime,
            "house_system": house_system if time_known else None,
            "zodiac": "tropical",
            # Set when the birth time fell in the hour the clocks changed (see birth_subject).
            "time_note": time_note,
        },
        "planets": planets,
        "houses": houses,
        "angles": angles,
        "aspects": aspects,
        "elements": {k: round(v, 1) for k, v in chart_data.element_distribution.model_dump().items()
                     if isinstance(v, (int, float))},
        "modes": {k: round(v, 1) for k, v in chart_data.quality_distribution.model_dump().items()
                  if isinstance(v, (int, float))},
        "lunar_phase": data.get("lunar_phase", {}).get("moon_phase_name") if data.get("lunar_phase") else None,
        "summary": summary_text(planets, angles, aspects, time_known, house_system, time_note),
    }
    from .drawing import full_svg, wheel_svg
    result["svg"] = full_svg(result, language) if layout == "full" else wheel_svg(result, language)
    return result


DISPLAY_NAMES = {
    "Mean_North_Lunar_Node": "North Node", "Mean_South_Lunar_Node": "South Node",
    "Medium_Coeli": "Midheaven", "Imum_Coeli": "Imum Coeli",
}
HOUSE_ORDINALS = {"First": "1st", "Second": "2nd", "Third": "3rd", "Fourth": "4th", "Fifth": "5th",
                  "Sixth": "6th", "Seventh": "7th", "Eighth": "8th", "Ninth": "9th", "Tenth": "10th",
                  "Eleventh": "11th", "Twelfth": "12th"}


def display_name(name: str) -> str:
    return DISPLAY_NAMES.get(name, name.replace("_", " "))


def house_label(house: str | None) -> str:
    """'Ninth_House' -> '9th house'."""
    if not house:
        return ""
    word = house.replace("_House", "")
    return f"{HOUSE_ORDINALS.get(word, word)} house"


def summary_text(planets: list[dict], angles: dict | None, aspects: list[dict], time_known: bool,
                 house_system: str = "placidus", time_note: str | None = None) -> str:
    """Plain-text chart facts for the Spiritual Chat prompt. No interpretation here."""
    lines = [f"Birth chart (tropical zodiac, {HOUSE_SYSTEM_NAMES.get(house_system, house_system)} houses):" if time_known
             else "Birth chart (tropical zodiac; birth time unknown, so houses and the Ascendant are not available):"]
    if time_note == "ambiguous":
        lines.append("- Note: the birth time happened twice that night (clocks went back); the first occurrence was used")
    elif time_note == "nonexistent":
        lines.append("- Note: the clocks skipped the birth time that night; it was read with the time zone offset before the change")
    for p in planets:
        if p["name"] == "Mean_South_Lunar_Node":
            continue
        house = f", {house_label(p['house'])}" if time_known and p["house"] else ""
        rx = ", retrograde" if p["retrograde"] else ""
        lines.append(f"- {display_name(p['name'])}: {p['sign']} {p['position_text']}{house}{rx}")
    if time_known and angles:
        lines.append(f"- Ascendant: {angles['ascendant']['sign']} {angles['ascendant']['position_text']}")
        lines.append(f"- Midheaven: {angles['midheaven']['sign']} {angles['midheaven']['position_text']}")
    major = [a for a in aspects if a["orb"] <= 3
             and a["type"] in ("conjunction", "opposition", "square", "trine", "sextile")
             and "South" not in a["from"] + a["to"]]
    if major:
        lines.append("Closest aspects: " + "; ".join(
            f"{display_name(a['from'])} {a['type']} {display_name(a['to'])}" for a in major[:8]))
    return "\n".join(lines)
