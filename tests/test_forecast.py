"""Horoscope, compatibility and Moon calendar endpoints."""
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BERLIN = 2950159
TODAY = date.today()
ANNA = {"date": "1990-06-12", "hour": 14, "minute": 40, "place_id": BERLIN}


def test_moon_calendar_matches_kerykeion_phase_times():
    from kerykeion import AstrologicalSubjectFactory, MoonPhaseDetailsFactory
    r = client.get("/moon-calendar", params={"year": 2026, "month": 11, "tz": "Europe/Berlin"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["days"]) == 30 and [m["phase"] for m in data["majors"]] == ["Last Quarter", "New Moon", "First Quarter", "Full Moon"]
    s = AstrologicalSubjectFactory.from_birth_data(name="d", year=2026, month=11, day=1, hour=12, minute=0, lng=0, lat=0, tz_str="Europe/Berlin", online=False)
    up = MoonPhaseDetailsFactory.from_subject(s).model_dump()["moon"]["detailed"]["upcoming_phases"]
    keys = {"Last Quarter": "last_quarter", "New Moon": "new_moon", "First Quarter": "first_quarter", "Full Moon": "full_moon"}
    for m in data["majors"]:
        ours = datetime.fromisoformat(m["moment"])
        theirs = datetime.fromtimestamp(up[keys[m["phase"]]]["next"]["timestamp"], tz=ours.tzinfo)
        assert abs((ours - theirs).total_seconds()) < 180, (m, theirs)
    full = next(d for d in data["days"] if d["phase"] == "Full Moon")
    assert full["date"] == "2026-11-24" and full["illumination"] >= 99


def test_moon_calendar_other_time_zone_and_bad_input():
    r = client.get("/moon-calendar", params={"year": 2026, "month": 2, "tz": "Asia/Kolkata"})
    assert r.status_code == 200 and len(r.json()["days"]) == 28
    assert client.get("/moon-calendar", params={"year": 2026, "month": 13, "tz": "UTC"}).status_code == 422
    assert client.get("/moon-calendar", params={"year": 2026, "month": 1, "tz": "Mars/Olympus"}).status_code == 400


def test_horoscope_periods():
    for period, days in (("tomorrow", 1), ("week", 7)):
        r = client.post("/horoscope", json={**ANNA, "period": period, "today": TODAY.isoformat(), "visitor_timezone": "Europe/Berlin"})
        assert r.status_code == 200, r.text
        h = r.json()
        first, last = date.fromisoformat(h["first"]), date.fromisoformat(h["last"])
        assert (last - first).days + 1 == days
        assert first == (TODAY + timedelta(days=1) if period == "tomorrow" else TODAY)
        assert h["summary"].startswith(f"Horoscope ({period}") and h["moon_signs"]
        for t in h["transits"]:
            assert t["aspect"] in ("conjunction", "opposition", "square", "trine", "sextile") and t["orb"] <= 3
    month = client.post("/horoscope", json={**ANNA, "period": "month", "today": TODAY.isoformat()}).json()
    assert month["first"] == TODAY.replace(day=1).isoformat() and month["moon_signs"] == []
    assert all(t["transit"] != "Moon" for t in month["transits"])


def test_horoscope_unknown_time_has_no_angles_and_checks_input():
    r = client.post("/horoscope", json={"date": "1990-06-12", "place_id": BERLIN, "period": "week", "today": TODAY.isoformat()})
    assert r.status_code == 200
    assert all(t["natal"] not in ("Ascendant", "Medium_Coeli") for t in r.json()["transits"])
    assert client.post("/horoscope", json={**ANNA, "period": "year", "today": TODAY.isoformat()}).status_code == 422
    assert client.post("/horoscope", json={**ANNA, "period": "week", "today": "2020-01-01"}).status_code == 400


def test_synastry():
    marco = {"name": "Marco", "date": "1988-11-03", "hour": 9, "minute": 15, "lat": 41.9028, "lng": 12.4964, "timezone": "Europe/Rome"}
    r = client.post("/synastry", json={"people": [{**ANNA, "name": "Anna"}, marco]})
    assert r.status_code == 200, r.text
    s = r.json()
    assert isinstance(s["score"], int) and s["description"] and s["names"] == ["Anna", "Marco"]
    assert s["placements"][0]["Sun"] == "Gemini" and s["placements"][1]["Sun"] == "Scorpio"
    outer = {"Uranus", "Neptune", "Pluto"}
    assert not any(a["first"] in outer and a["second"] in outer for a in s["aspects"])
    assert "Anna" in s["summary"] and "Marco" in s["summary"]
    r2 = client.post("/synastry", json={"people": [{"date": "1990-06-12", "place_id": BERLIN}, {"date": "1988-11-03", "place_id": BERLIN}]})
    assert r2.status_code == 200 and not any("Ascendant" in (a["first"], a["second"]) for a in r2.json()["aspects"])
    assert client.post("/synastry", json={"people": [ANNA]}).status_code == 422
