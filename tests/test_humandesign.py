"""Human Design: the mandala, the design moment, the type and authority rules, the API."""
from datetime import date, datetime

from fastapi.testclient import TestClient

from app.humandesign import CENTERS, CHANNELS, MANDALA, analyse, design_moment, gate_line, _utc_subject
from app.main import app

client = TestClient(app)
BERLIN = 2950159


def test_mandala_and_centers_cover_each_gate_once():
    assert sorted(MANDALA) == list(range(1, 65))
    assert sorted(g for gates in CENTERS.values() for g in gates) == list(range(1, 65))
    assert len(CHANNELS) == 36 and len({g for c in CHANNELS for g in c}) == 64


def test_gate_anchors():
    assert gate_line(302.0) == (41, 1)        # gate 41 begins at 2 Aquarius, the start of the Rave year
    assert gate_line(358.25) == (25, 1) and gate_line(358.24) == (36, 6)
    assert gate_line(223.25) == (1, 1) and gate_line(43.25) == (2, 1)  # gates 1 and 2 opposite
    assert gate_line(302.0 + 5.625 - 0.0001)[1] == 6


def test_design_is_88_degrees_of_sun_before_birth():
    birth = datetime(1990, 6, 12, 12, 40)
    sun = _utc_subject(birth).sun.abs_pos
    moment = design_moment(birth, sun)
    assert abs(((sun - _utc_subject(moment).sun.abs_pos) % 360) - 88) < 0.001
    assert 85 <= (birth - moment).days <= 92


def test_type_and_authority_rules():
    assert analyse(set())["type"] == "reflector" and analyse(set())["authority"] == "lunar"
    assert analyse({20, 34})["type"] == "manifesting_generator"      # sacral to throat
    g = analyse({5, 15})
    assert g["type"] == "generator" and g["authority"] == "sacral"   # sacral, no motor to throat
    m = analyse({21, 45})
    assert m["type"] == "manifestor" and m["authority"] == "ego_manifested"
    p = analyse({13, 33})
    assert p["type"] == "projector" and p["authority"] == "self_projected" and p["definition"] == "single"
    e = analyse({37, 40, 13, 33})
    assert e["authority"] == "emotional" and e["definition"] == "split"
    assert analyse({20, 34, 37, 40, 12, 22})["type"] == "manifesting_generator"


def test_api_chart():
    r = client.post("/human-design", json={"date": "1990-06-12", "hour": 14, "minute": 40, "place_id": BERLIN, "name": "Anna"})
    assert r.status_code == 200
    d = r.json()
    assert d["type"] in ("generator", "manifesting_generator", "manifestor", "projector", "reflector")
    assert len(d["personality"]) == 13 and len(d["design"]) == 13
    assert d["personality"]["Earth"]["gate"] == gate_line((d["personality"]["Sun"]["longitude"] + 180) % 360)[0]
    p_line, d_line = (int(x) for x in d["profile"].split("/"))
    assert (p_line, d_line) == (d["personality"]["Sun"]["line"], d["design"]["Sun"]["line"])
    assert d["summary"].startswith("Human Design chart") and "<svg" in d["svg"] and "Personality" in d["svg"]


def test_bodygraph_legend_in_the_page_language():
    r = client.post("/human-design", json={"date": "1990-06-12", "hour": 14, "minute": 40, "place_id": BERLIN, "language": "de"})
    assert "Persönlichkeit" in r.json()["svg"] and "Personality" not in r.json()["svg"]


def test_api_needs_the_birth_time():
    r = client.post("/human-design", json={"date": "1990-06-12", "place_id": BERLIN})
    assert r.status_code == 400 and "birth time" in r.json()["detail"]


def test_api_compatibility():
    r = client.post("/human-design/compatibility", json={"people": [
        {"date": "1990-06-12", "hour": 14, "minute": 40, "place_id": BERLIN, "name": "Anna"},
        {"date": "1988-11-03", "hour": 9, "minute": 15, "place_id": BERLIN, "name": "Marco"}]})
    assert r.status_code == 200
    d = r.json()
    a, b = (set(p["channels"]) for p in d["people"])
    for ch in d["electromagnetic"]:
        assert ch not in a and ch not in b
    for ch in d["companionship"]:
        assert ch in a and ch in b
    assert d["summary"].startswith("Human Design compatibility of Anna and Marco")
