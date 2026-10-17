"""Checks against an independently verified reference chart and the API contract.

Reference: 12 June 1990, 14:40 local time, Berlin (52.52437 N, 13.41053 E). The
positions were computed with Skyfield/JPL and compared with Swiss Ephemeris; both
agree to well under an arcsecond, so they are quoted here to the arcminute.
"""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.chart import ChartError, build_chart
from app.main import app, places

BERLIN = dict(lat=52.52437, lng=13.41053, tz="Europe/Berlin", place_label="Berlin, Germany", country_code="DE")
REFERENCE = {
    "Sun": ("Gemini", "21°17′", False), "Moon": ("Aquarius", "7°01′", False),
    "Mercury": ("Gemini", "0°48′", False), "Venus": ("Taurus", "15°17′", False),
    "Mars": ("Aries", "8°54′", False), "Jupiter": ("Cancer", "15°15′", False),
    "Saturn": ("Capricorn", "24°12′", True), "Uranus": ("Capricorn", "8°17′", True),
    "Neptune": ("Capricorn", "13°47′", True), "Pluto": ("Scorpio", "15°28′", True),
}


@pytest.fixture(scope="module")
def berlin():
    return build_chart(name="Test", birth_date=date(1990, 6, 12), hour=14, minute=40, **BERLIN)


def test_planets_match_reference(berlin):
    by_name = {p["name"]: p for p in berlin["planets"]}
    for name, (sign, position, retrograde) in REFERENCE.items():
        p = by_name[name]
        assert (p["sign"], p["position_text"], p["retrograde"]) == (sign, position, retrograde), name


def test_angles_and_time_zone(berlin):
    assert (berlin["angles"]["ascendant"]["sign"], berlin["angles"]["ascendant"]["position_text"]) == ("Libra", "9°44′")
    assert (berlin["angles"]["midheaven"]["sign"], berlin["angles"]["midheaven"]["position_text"]) == ("Cancer", "12°53′")
    assert berlin["input"]["utc"] == "1990-06-12T12:40:00+00:00"  # CEST in 1990, resolved from the IANA rules
    assert len(berlin["houses"]) == 12 and berlin["houses"][0]["sign"] == "Libra"


def test_summary_and_svg(berlin):
    assert "Sun: Gemini 21°17′" in berlin["summary"] and "Ascendant: Libra 9°44′" in berlin["summary"]
    assert berlin["svg"].lstrip().startswith("<?xml") or "<svg" in berlin["svg"][:300]
    assert "Berlin" in berlin["svg"]
    assert berlin["aspects"] and all(a["orb"] >= 0 for a in berlin["aspects"])


def test_unknown_birth_time():
    chart = build_chart(name="", birth_date=date(1990, 6, 12), hour=None, minute=None, **BERLIN)
    assert chart["input"]["time_known"] is False and chart["houses"] == [] and chart["angles"] is None
    assert "birth time unknown" in chart["summary"]
    assert {p["name"] for p in chart["planets"]} >= set(REFERENCE)


def test_winter_time_offset():
    chart = build_chart(name="", birth_date=date(1990, 1, 12), hour=14, minute=40, **BERLIN)
    assert chart["input"]["utc"] == "1990-01-12T13:40:00+00:00"  # CET, one hour, not the summer offset


@pytest.mark.parametrize("year", [1849, 2151])
def test_year_range(year):
    with pytest.raises(ChartError):
        build_chart(name="", birth_date=date(year, 6, 12), hour=12, minute=0, **BERLIN)


def test_bad_time_zone():
    with pytest.raises(ChartError):
        build_chart(name="", birth_date=date(1990, 6, 12), hour=12, minute=0, **{**BERLIN, "tz": "Mars/Olympus"})


client = TestClient(app)


def test_api_chart_with_coordinates():
    r = client.post("/chart", json={"date": "1990-06-12", "hour": 14, "minute": 40, "lat": 52.52437, "lng": 13.41053,
                                    "timezone": "Europe/Berlin", "place_label": "Berlin", "country": "DE"})
    assert r.status_code == 200
    body = r.json()
    assert body["angles"]["ascendant"]["position_text"] == "9°44′" and "svg" in body


def test_api_svg_format():
    r = client.post("/chart?format=svg", json={"date": "1990-06-12", "hour": 14, "minute": 40, "lat": 52.52437,
                                               "lng": 13.41053, "timezone": "Europe/Berlin"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")


@pytest.mark.parametrize("payload", [
    {"date": "1990-06-12", "hour": 14, "lat": 52.5, "lng": 13.4, "timezone": "Europe/Berlin"},  # minute missing
    {"date": "1990-06-12", "hour": 14, "minute": 40},  # no place at all
    {"date": "1990-02-31", "hour": 14, "minute": 40, "lat": 52.5, "lng": 13.4, "timezone": "Europe/Berlin"},  # impossible date
    {"date": "1990-06-12", "hour": 24, "minute": 0, "lat": 52.5, "lng": 13.4, "timezone": "Europe/Berlin"},  # hour out of range
    {"date": "1990-06-12", "hour": 14, "minute": 40, "place_id": 999999999},  # unknown place id
])
def test_api_rejects_bad_input(payload):
    r = client.post("/chart", json=payload)
    assert r.status_code in (400, 422)


def test_places_search_when_data_present():
    if not places.places:
        pytest.skip("data/places.tsv not built")
    r = client.get("/places", params={"q": "berl"})
    names = [p["name"] for p in r.json()["places"]]
    assert "Berlin" in names
    assert client.get("/places", params={"q": "b"}).status_code == 422  # too short
