"""Horoscope (transits to a birth chart), relationship compatibility (synastry) and the
Moon calendar, on top of Kerykeion. Like chart.py, this only shapes requests and
responses; the astronomy is Kerykeion's.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import chart  # noqa: F401  (sets the ephemeris environment before Kerykeion loads)
from .chart import SIGN_NAMES, ChartError, display_name
from kerykeion import (AspectsFactory, AstrologicalSubjectFactory, EphemerisDataFactory,  # noqa: E402
                       RelationshipScoreFactory, TransitsTimeRangeFactory)

PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
AXES = ["Ascendant", "Medium_Coeli"]
MAJOR = ("conjunction", "opposition", "square", "trine", "sextile")
# Tight orbs for transits, so a period lists what is really active then.
TRANSIT_ASPECTS = [{"name": "conjunction", "orb": 3}, {"name": "opposition", "orb": 3}, {"name": "square", "orb": 3},
                   {"name": "trine", "orb": 3}, {"name": "sextile", "orb": 2}]
# Slow planets shape a period more than fast ones; the Sun, Moon and angles of the birth
# chart are the most personal points.
TRANSIT_WEIGHT = {"Pluto": 10, "Neptune": 9, "Uranus": 8, "Saturn": 7, "Jupiter": 6, "Mars": 5, "Sun": 4, "Venus": 4, "Mercury": 3, "Moon": 1}
NATAL_WEIGHT = {"Sun": 3, "Moon": 3, "Ascendant": 3, "Medium_Coeli": 3, "Venus": 2, "Mars": 2, "Mercury": 2}
PERIOD_DAYS = {"tomorrow": 1, "week": 7, "month": 31}


def subject(birth: dict, name: str = "Birth chart"):
    """birth: date, hour, minute (None for unknown), lat, lng, tz, place_label, country_code."""
    known = birth["hour"] is not None and birth["minute"] is not None
    d = birth["date"]
    if not chart.MIN_YEAR <= d.year <= chart.MAX_YEAR:
        raise ChartError(f"Birth years from {chart.MIN_YEAR} to {chart.MAX_YEAR} are supported.")
    return AstrologicalSubjectFactory.from_birth_data(
        name=name or "Birth chart", year=d.year, month=d.month, day=d.day,
        hour=birth["hour"] if known else 12, minute=birth["minute"] if known else 0,
        city=birth.get("place_label") or "", nation=birth.get("country_code") or "",
        lng=birth["lng"], lat=birth["lat"], tz_str=birth["tz"], online=False,
        active_points=PLANETS + (AXES if known else []),
    ), known


def _local(moment: str, tz: str) -> datetime:
    return datetime.fromisoformat(moment.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))


# ---- Horoscope ----

def period_range(period: str, today: date) -> tuple[date, date]:
    """First and last day of the period, both included, in the visitor's calendar."""
    if period == "tomorrow":
        start = today + timedelta(days=1)
        return start, start
    if period == "week":
        return today, today + timedelta(days=6)
    if period == "month":
        first = today.replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        return first, nxt - timedelta(days=1)
    raise ChartError("Unknown period.")


def horoscope(birth: dict, period: str, today: date, tz: str) -> dict:
    """Transits of the period to the birth chart: the most important aspects first."""
    natal, known = subject(birth)
    first, last = period_range(period, today)
    days = (last - first).days + 1
    # The Moon is only followed for a day or a week; over a month its many short aspects
    # would crowd out the slower planets (the Moon calendar covers it).
    with_moon = period != "month"
    step_type, step = ("hours", 1) if days == 1 else ("hours", 3) if days <= 8 else ("hours", 12)
    start_dt = datetime(first.year, first.month, first.day, 0, 0)
    end_dt = datetime(last.year, last.month, last.day, 23, 59)
    eph = EphemerisDataFactory(start_dt, end_dt, step_type=step_type, step=step, lat=birth["lat"], lng=birth["lng"], tz_str=tz,
                               active_points=PLANETS).get_ephemeris_data_as_astrological_subjects(as_model=True)
    transit_points = PLANETS if with_moon else [p for p in PLANETS if p != "Moon"]
    natal_points = PLANETS + (AXES if known else [])
    events = TransitsTimeRangeFactory(natal, eph, active_points=list(dict.fromkeys(transit_points + natal_points)),
                                      active_aspects=TRANSIT_ASPECTS).get_transit_events(refine_exact_moments=True).model_dump()["events"]
    first_moment = eph[0].iso_formatted_utc_datetime if eph else None
    last_moment = eph[-1].iso_formatted_utc_datetime if eph else None
    found = []
    for e in events:
        if e["p1_name"] not in transit_points or e["p2_name"] not in natal_points or e["aspect"] not in MAJOR:
            continue
        if e["p1_name"] == e["p2_name"] == "Moon":
            continue
        exact = _local(e["exact_moment"], tz) if e.get("exact_moment") else None
        orb = e.get("min_orb") or 0
        # The tightest moment at the first or last sample, still with some orb, means the
        # aspect was already in effect when the period began, or becomes exact after it.
        at_start = first_moment and e.get("exact_moment", "")[:16] == first_moment[:16]
        at_end = last_moment and e.get("exact_moment", "")[:16] == last_moment[:16]
        ongoing = exact is None or (at_start and orb > 0.3)
        building = bool(at_end and orb > 0.3 and not ongoing)
        weight = TRANSIT_WEIGHT.get(e["p1_name"], 1) * NATAL_WEIGHT.get(e["p2_name"], 1) + max(0.0, 3 - (e.get("min_orb") or 0))
        found.append({
            "transit": e["p1_name"], "natal": e["p2_name"], "aspect": e["aspect"],
            "exact": None if ongoing or building else exact.isoformat(timespec="minutes"),
            "date": (first if ongoing else last if building else exact.date()).isoformat(), "ongoing": bool(ongoing), "building": building,
            "orb": round(e.get("min_orb") or 0, 2), "weight": round(weight, 2),
        })
    # One entry per transit pair (the same aspect can be reported in several windows).
    unique = {}
    for f in sorted(found, key=lambda x: (-x["weight"], x["orb"])):
        unique.setdefault((f["transit"], f["natal"], f["aspect"]), f)
    top = sorted(unique.values(), key=lambda x: -x["weight"])[: 8 if days == 1 else 12]
    top.sort(key=lambda x: (x["date"], -x["weight"]))
    moon_signs = []
    if with_moon:
        seen = None
        for s in eph:
            local = _local(s.iso_formatted_utc_datetime, tz)
            sign = SIGN_NAMES[s.moon.sign]
            if sign != seen:
                moon_signs.append({"from": local.isoformat(timespec="minutes"), "sign": sign})
                seen = sign
    return {
        "period": period, "first": first.isoformat(), "last": last.isoformat(), "time_known": known,
        "transits": top, "moon_signs": moon_signs,
        "summary": horoscope_summary(period, first, last, top, moon_signs, known),
    }


def horoscope_summary(period, first, last, transits, moon_signs, known) -> str:
    span = first.isoformat() if first == last else f"{first.isoformat()} to {last.isoformat()}"
    lines = [f"Horoscope ({period}, {span}), transits to the birth chart" + ("" if known else " (birth time unknown, so no Ascendant or Midheaven)") + ":"]
    for t in transits:
        when = ("in effect from the start" if t["ongoing"] else "building, exact after this period" if t.get("building")
                else f"exact {t['exact'][:16].replace('T', ' ')}")
        lines.append(f"- Transiting {display_name(t['transit'])} {t['aspect']} natal {display_name(t['natal'])}, {when} (orb {t['orb']}°)")
    if not transits:
        lines.append("- No major transits in tight orb in this period")
    if moon_signs:
        lines.append("Moon: " + "; ".join(f"{m['sign']} from {m['from'][:16].replace('T', ' ')}" for m in moon_signs[:9]))
    return "\n".join(lines)


# ---- Compatibility ----

def synastry(people: list[dict]) -> dict:
    """Two birth charts: Kerykeion's relationship score and the closest aspects between them."""
    (a, a_known), (b, b_known) = subject(people[0]["birth"], people[0]["name"] or "Person 1"), subject(people[1]["birth"], people[1]["name"] or "Person 2")
    score = RelationshipScoreFactory(a, b).get_relationship_score().model_dump()
    points = PLANETS + (AXES if a_known and b_known else [])
    aspects = AspectsFactory.dual_chart_aspects(a, b, active_points=points).model_dump()["aspects"]
    # Two outer planets in aspect are the same for everyone born within a few years.
    outer = {"Uranus", "Neptune", "Pluto"}
    aspects = [x for x in aspects if x["aspect"] in MAJOR and not (x["p1_name"] in outer and x["p2_name"] in outer)]
    aspects.sort(key=lambda x: x["orbit"])
    top = [{"first": x["p1_name"], "second": x["p2_name"], "aspect": x["aspect"], "orb": round(x["orbit"], 2)} for x in aspects[:10]]

    def placements(s):
        return {p: SIGN_NAMES[getattr(s, p.lower()).sign] for p in ["Sun", "Moon", "Venus", "Mars"]}

    names = [people[0]["name"] or "Person 1", people[1]["name"] or "Person 2"]
    pa, pb = placements(a), placements(b)
    lines = [f"Astrological compatibility (synastry, tropical zodiac) of {names[0]} and {names[1]}:",
             f"- Relationship score {score['score_value']} ({score['score_description']}, Kerykeion scale)"]
    for n, p in zip(names, [pa, pb]):
        lines.append(f"- {n}: Sun {p['Sun']}, Moon {p['Moon']}, Venus {p['Venus']}, Mars {p['Mars']}")
    lines.append("Closest aspects between the charts: " + "; ".join(
        f"{names[0]}'s {display_name(x['first'])} {x['aspect']} {names[1]}'s {display_name(x['second'])} ({x['orb']}°)" for x in top[:8]))
    if not (a_known and b_known):
        lines.append("- At least one birth time is unknown, so Ascendants and houses are not compared")
    return {"score": score["score_value"], "description": score["score_description"], "destiny_sign": bool(score.get("is_destiny_sign")),
            "names": names, "placements": [pa, pb], "aspects": top, "summary": "\n".join(lines)}


# ---- Moon calendar ----

PHASES = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous", "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
MAJOR_PHASES = [(0, "New Moon"), (90, "First Quarter"), (180, "Full Moon"), (270, "Last Quarter")]


def _elongation(s) -> float:
    return (s.moon.abs_pos - s.sun.abs_pos) % 360


def phase_name(angle: float) -> str:
    """Crescent or gibbous by quarter of the cycle; the four major phases are named only on
    the day they happen (see moon_calendar)."""
    return ["Waxing Crescent", "Waxing Gibbous", "Waning Gibbous", "Waning Crescent"][int((angle % 360) // 90)]


def moon_calendar(year: int, month: int, tz: str) -> dict:
    try:
        ZoneInfo(tz)
    except Exception:
        raise ChartError("Unknown time zone.")
    if not chart.MIN_YEAR <= year <= chart.MAX_YEAR or not 1 <= month <= 12:
        raise ChartError("Unknown month.")
    first = date(year, month, 1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    # Every 6 hours from the day before to the day after, to find the exact major phases.
    eph = EphemerisDataFactory(datetime(year, month, 1) - timedelta(days=1), datetime(last.year, last.month, last.day, 23, 59) + timedelta(days=1),
                               step_type="hours", step=6, lat=0.0, lng=0.0, tz_str=tz,
                               active_points=["Sun", "Moon"]).get_ephemeris_data_as_astrological_subjects(as_model=True)
    samples = [(_local(s.iso_formatted_utc_datetime, tz), _elongation(s), s) for s in eph]
    majors = []
    for (t0, e0, _), (t1, e1, s1) in zip(samples, samples[1:]):
        step = (e1 - e0) % 360
        for target, name in MAJOR_PHASES:
            passed = (target - e0) % 360
            if 0 < passed <= step or (passed == 0 and step > 0 and target == 0 and e0 == 0):
                moment = t0 + (t1 - t0) * (passed / step)
                if first <= moment.date() <= last:
                    majors.append({"phase": name, "moment": moment.isoformat(timespec="minutes"), "sign": SIGN_NAMES[s1.moon.sign]})
    days = []
    for t, e, s in samples:
        if t.hour == 12 and first <= t.date() <= last:
            days.append({"date": t.date().isoformat(), "phase": phase_name(e), "illumination": round((1 - math.cos(math.radians(e))) / 2 * 100),
                         "sign": SIGN_NAMES[s.moon.sign]})
    # Samples fall on local noon only for whole-hour offsets; otherwise take the sample nearest noon.
    if len(days) < (last - first).days + 1:
        days = []
        for i in range((last - first).days + 1):
            d = first + timedelta(days=i)
            t, e, s = min(samples, key=lambda x: abs((x[0].replace(tzinfo=None) - datetime(d.year, d.month, d.day, 12)).total_seconds()))
            days.append({"date": d.isoformat(), "phase": phase_name(e), "illumination": round((1 - math.cos(math.radians(e))) / 2 * 100),
                         "sign": SIGN_NAMES[s.moon.sign]})
    for m in majors:
        for d in days:
            if d["date"] == m["moment"][:10]:
                d["phase"] = m["phase"]
                d["major"] = m["moment"]
    lines = [f"Moon calendar for {first.strftime('%Y-%m')} ({tz}):"]
    lines += [f"- {m['phase']}: {m['moment'][:16].replace('T', ' ')}, Moon in {m['sign']}" for m in majors]
    return {"year": year, "month": month, "tz": tz, "majors": majors, "days": days, "summary": "\n".join(lines)}
