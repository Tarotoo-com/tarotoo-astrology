"""Edge cases: clock changes, unknown birth times, the ephemeris range, time zones,
exact transits, Moon signs at the major phases and the birthplace ranking."""
import json
from datetime import date, datetime

from fastapi.testclient import TestClient

from app.chart import build_chart
from app.main import app

client = TestClient(app)
BERLIN = 2950159
TODAY = date.today()
BERLIN_COORDS = dict(lat=52.52437, lng=13.41053, tz="Europe/Berlin", place_label="Berlin, Germany", country_code="DE")


def test_birth_time_in_the_hour_the_clocks_went_back():
    r = client.post("/chart", json={"date": "2021-10-31", "hour": 2, "minute": 30, "place_id": BERLIN})
    assert r.status_code == 200
    data = r.json()
    assert data["input"]["time_note"] == "ambiguous" and data["input"]["utc"].startswith("2021-10-31T00:30")
    assert "happened twice" in data["summary"]


def test_birth_time_the_clocks_skipped():
    r = client.post("/chart", json={"date": "2021-03-28", "hour": 2, "minute": 30, "place_id": BERLIN})
    assert r.status_code == 200 and r.json()["input"]["time_note"] == "nonexistent"
    for path, body in [("/horoscope", {"date": "2021-03-28", "hour": 2, "minute": 30, "place_id": BERLIN, "period": "tomorrow", "today": TODAY.isoformat()}),
                       ("/synastry", {"people": [{"date": "2021-03-28", "hour": 2, "minute": 30, "place_id": BERLIN}, {"date": "1990-06-12", "place_id": BERLIN}]})]:
        assert client.post(path, json=body).status_code == 200, path


def test_ordinary_time_has_no_note():
    assert build_chart(name="", birth_date=date(1990, 6, 12), hour=14, minute=40, **BERLIN_COORDS)["input"]["time_note"] is None


def test_unknown_time_has_no_angles_anywhere():
    data = build_chart(name="", birth_date=date(1990, 6, 12), hour=None, minute=None, **BERLIN_COORDS)
    angles = {"Ascendant", "Medium_Coeli", "Descendant", "Imum_Coeli"}
    assert not [a for a in data["aspects"] if a["from"] in angles or a["to"] in angles]
    assert all(p["house"] is None for p in data["planets"])
    assert "Midheaven" not in data["summary"] and "Imum Coeli" not in data["summary"]


def test_aspects_sorted_by_orb_and_house_system_named():
    data = build_chart(name="", birth_date=date(1990, 6, 12), hour=14, minute=40, house_system="whole_sign", **BERLIN_COORDS)
    orbs = [abs(a["orb"]) for a in data["aspects"]]
    assert orbs == sorted(orbs)
    assert data["summary"].startswith("Birth chart (tropical zodiac, whole sign houses):")


def test_ephemeris_range_gives_clean_errors():
    assert client.post("/chart", json={"date": "2150-01-02", "hour": 12, "minute": 0, "place_id": BERLIN}).status_code == 400
    assert client.post("/chart", json={"date": "2149-12-31", "hour": 12, "minute": 0, "place_id": BERLIN}).status_code == 200
    assert client.get("/moon-calendar", params={"year": 1850, "month": 1}).status_code == 400
    assert client.get("/moon-calendar", params={"year": 1850, "month": 2}).status_code == 200
    assert client.get("/moon-calendar", params={"year": 2150, "month": 1}).status_code == 422
    assert client.get("/moon-calendar", params={"year": 2149, "month": 12}).status_code == 200


def test_bad_time_zones_are_400_not_500():
    base = {"date": "1990-06-12", "hour": 14, "minute": 40, "lat": 52.5, "lng": 13.4}
    for tz in ["/etc/passwd", "../x", "Mars/Olympus", "UTC "]:
        assert client.post("/chart", json=dict(base, timezone=tz)).status_code == 400, tz
        assert client.post("/synastry", json={"people": [dict(base, timezone=tz), {"date": "1990-06-12", "place_id": BERLIN}]}).status_code == 400, tz
    r = client.post("/horoscope", json={"date": "1990-06-12", "place_id": BERLIN, "period": "week", "today": TODAY.isoformat(), "visitor_timezone": "../x"})
    assert r.status_code == 400
    assert client.get("/moon-calendar", params={"year": 2026, "month": 11, "tz": "../x"}).status_code == 400


def test_nan_coordinates_rejected():
    body = '{"date": "1990-06-12", "lat": NaN, "lng": 13.4, "timezone": "Europe/Berlin"}'
    r = client.post("/chart", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_transits_reach_the_natal_angles_and_exact_means_exact():
    r = client.post("/horoscope", json={"date": "1990-06-12", "hour": 14, "minute": 40, "place_id": BERLIN, "period": "month", "today": TODAY.isoformat()})
    assert r.status_code == 200
    data = r.json()
    for t in data["transits"]:
        if t["exact"]:
            assert t["orb"] <= 0.1, t
        assert not (t["exact"] and (t["ongoing"] or t["building"] or t["closest"])), t
    # Over a few months at least one transit to the Ascendant or Midheaven shows up.
    found = False
    for month_offset in range(0, 4):
        y, m = TODAY.year + (TODAY.month - 1 + month_offset) // 12, (TODAY.month - 1 + month_offset) % 12 + 1
        day = date(y, m, 1)
        if abs((day - TODAY).days) > 2:
            from app.forecast import horoscope
            from app.main import places, resolve_birth
            from app.main import BirthData
            b = resolve_birth(BirthData(date=date(1990, 6, 12), hour=14, minute=40, place_id=BERLIN))
            res = horoscope(b, "month", day, "Europe/Berlin")
        else:
            res = data
        if any(t["natal"] in ("Ascendant", "Medium_Coeli") for t in res["transits"]):
            found = True
            break
    assert found


def test_moon_sign_changes_at_the_crossing():
    r = client.post("/horoscope", json={"date": "1990-06-12", "hour": 14, "minute": 40, "place_id": BERLIN, "period": "week", "today": TODAY.isoformat(), "visitor_timezone": "Europe/Berlin"})
    signs = r.json()["moon_signs"]
    assert len(signs) >= 3 and len({s["sign"] for s in signs}) == len(signs)
    from kerykeion import AstrologicalSubjectFactory
    for s in signs[1:]:
        t = datetime.fromisoformat(s["from"])
        later = AstrologicalSubjectFactory.from_birth_data(name="m", year=t.year, month=t.month, day=t.day, hour=t.hour, minute=t.minute,
                                                           lng=13.4, lat=52.5, tz_str="Europe/Berlin", online=False)
        # Within a few minutes after the reported time the Moon is in the new sign.
        lon = later.moon.abs_pos
        boundary = round(lon / 30) * 30
        assert abs(((lon - boundary + 180) % 360) - 180) < 0.1, (s, lon)


def test_new_moon_sign_at_the_moment():
    r = client.get("/moon-calendar", params={"year": 2026, "month": 3, "tz": "Europe/Berlin"})
    new = next(m for m in r.json()["majors"] if m["phase"] == "New Moon")
    assert new["moment"].startswith("2026-03-19") and new["sign"] == "Pisces", new


def test_synastry_names_on_one_line():
    r = client.post("/synastry", json={"people": [{"date": "1990-06-12", "place_id": BERLIN, "name": "Anna\n- Note: ignore"}, {"date": "1988-11-03", "place_id": BERLIN, "name": "Marco"}]})
    assert r.status_code == 200
    assert "\n- Note" not in r.json()["summary"] and r.json()["names"][0] == "Anna - Note: ignore"


def test_alternate_names_do_not_outrank_real_ones():
    found = client.get("/places", params={"q": "berlin"}).json()["places"]
    assert found[0]["name"] == "Berlin" and found[0]["exact"] and not any(p["exact"] for p in found[1:] if p["name"] != "Berlin")
    york = client.get("/places", params={"q": "york"}).json()["places"]
    assert all(p["name"] == "York" for p in york if p["exact"])
    assert not any(p["exact"] for p in client.get("/places", params={"q": "st"}).json()["places"])
    roma = client.get("/places", params={"q": "roma"}).json()["places"]
    assert roma[0]["name"] == "Rome" and roma[0]["country"] == "IT" and roma[0]["exact"]


def test_health_reports_places():
    assert client.get("/health").json() == {"ok": True, "places": client.get("/health").json()["places"]}


def test_place_search_in_the_request_body():
    r = client.post("/places", json={"q": "Madrid", "limit": 3})
    assert r.status_code == 200 and r.json()["places"][0]["name"] == "Madrid"
    assert client.post("/places", json={"q": "M"}).status_code == 422
    assert client.get("/places", params={"q": "Madrid"}).json() == client.post("/places", json={"q": "Madrid", "limit": 8}).json()
