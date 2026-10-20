"""Tarotoo astrology service: birthplace search and natal charts.

Run locally:  uvicorn app.main:app --reload
The WordPress site calls this over HTTP; it holds no user data and keeps no state.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from .places import PlaceIndex

# The chart module loads Kerykeion and its ephemeris, which takes a moment. It is
# imported on the first chart request only, so a cold start for /health and the
# birthplace search (the first calls a visitor's page makes) stays fast.

app = FastAPI(title="Tarotoo astrology", version="0.1.0", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "https://tarotoo.com").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
places = PlaceIndex()


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    """422 with where and what, without echoing the values sent (a NaN would not fit in JSON)."""
    return JSONResponse({"detail": [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
                                    for e in error.errors()]}, status_code=422)


@app.exception_handler(Exception)
async def calculation_error(request: Request, error: Exception):
    """Kerykeion refusing a calculation (a date at the edge of the ephemeris, for example)
    is a bad request, not a server fault. Anything else stays a 500."""
    if type(error).__name__ == "KerykeionException":
        return JSONResponse({"detail": "The chart could not be calculated for this birth data."}, status_code=400)
    logging.getLogger("tarotoo").exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Internal error."}, status_code=500)


def valid_zone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


class BirthData(BaseModel):
    """A birth: date, optional time, and a place id or coordinates with a time zone."""
    date: date
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    place_id: int | None = None
    # Coordinates and time zone may be given directly instead of a place id.
    lat: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    lng: float | None = Field(None, ge=-180, le=180, allow_inf_nan=False)
    timezone: str | None = Field(None, max_length=64)
    place_label: str = Field("", max_length=120)
    country: str = Field("", max_length=2)

    @field_validator("place_label", mode="before")
    @classmethod
    def strip_label(cls, value):
        return value.strip() if isinstance(value, str) else value


class ChartRequest(BirthData):
    name: str = Field("", max_length=80)
    house_system: str = Field("placidus", pattern="^(placidus|whole_sign|koch|equal)$")
    theme: str = Field("dark", pattern="^(dark|classic|black-and-white)$")
    layout: str = Field("wheel", pattern="^(wheel|full)$")
    language: str = Field("en", pattern="^(en|es|fr|it|de|pt)$")

    @field_validator("name", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class HoroscopeRequest(BirthData):
    period: str = Field(..., pattern="^(tomorrow|week|month)$")
    today: date  # the visitor's own date, so "tomorrow" and "this month" follow their calendar
    visitor_timezone: str | None = Field(None, max_length=64)


class Person(BirthData):
    name: str = Field("", max_length=40)


class SynastryRequest(BaseModel):
    people: list[Person] = Field(..., min_length=2, max_length=2)


def resolve_birth(req: BirthData) -> dict:
    if (req.hour is None) != (req.minute is None):
        raise HTTPException(400, "Give both hour and minute, or neither for an unknown birth time.")
    if req.place_id is not None:
        place = places.get(req.place_id)
        if place is None:
            raise HTTPException(400, "Unknown place.")
        lat, lng, tz, label, country = place.lat, place.lng, place.timezone, place.label, place.country
    elif req.lat is not None and req.lng is not None and req.timezone:
        lat, lng, tz, label, country = req.lat, req.lng, req.timezone, req.place_label or "Birthplace", req.country or ""
    else:
        raise HTTPException(400, "Give a place_id, or lat, lng and timezone.")
    if not valid_zone(tz):
        raise HTTPException(400, "Unknown time zone for the birthplace.")
    return {"date": req.date, "hour": req.hour, "minute": req.minute, "lat": lat, "lng": lng, "tz": tz,
            "place_label": label, "country_code": country}


@app.get("/health")
def health():
    return {"ok": bool(places.places), "places": len(places.places)}


@app.get("/places")
def search_places(q: str = Query(..., min_length=2, max_length=60), limit: int = Query(8, ge=1, le=15)):
    return {"places": [dict(p.public(), exact=is_exact) for p, is_exact in places.search_ranked(q, limit)]}


@app.post("/chart")
def chart(req: ChartRequest, format: str = Query("json", pattern="^(json|svg)$")):
    from .chart import ChartError, build_chart

    b = resolve_birth(req)
    try:
        result = build_chart(
            name=req.name, birth_date=b["date"], hour=b["hour"], minute=b["minute"],
            lat=b["lat"], lng=b["lng"], tz=b["tz"], place_label=b["place_label"], country_code=b["country_code"],
            house_system=req.house_system, theme=req.theme, layout=req.layout, language=req.language,
        )
    except ChartError as error:
        raise HTTPException(400, str(error))
    if format == "svg":
        return Response(result["svg"], media_type="image/svg+xml")
    return result


@app.post("/horoscope")
def horoscope(req: HoroscopeRequest):
    """Transits of tomorrow, this week (7 days from today) or this month to a birth chart."""
    from .chart import ChartError
    from .forecast import horoscope as build

    b = resolve_birth(req)
    tz = req.visitor_timezone or b["tz"]
    if abs((req.today - date.today()).days) > 2:
        raise HTTPException(400, "The visitor's date is too far from today.")
    if not valid_zone(tz):
        raise HTTPException(400, "Unknown time zone.")
    try:
        return build(b, req.period, req.today, tz)
    except ChartError as error:
        raise HTTPException(400, str(error))


@app.post("/synastry")
def synastry(req: SynastryRequest):
    """Two birth charts: relationship score and the closest aspects between them."""
    from .chart import ChartError
    from .forecast import synastry as build

    people = [{"name": p.name.strip(), "birth": resolve_birth(p)} for p in req.people]
    try:
        return build(people)
    except ChartError as error:
        raise HTTPException(400, str(error))


@app.get("/moon-calendar")
def moon_calendar(year: int = Query(..., ge=1850, le=2149), month: int = Query(..., ge=1, le=12), tz: str = Query("UTC", max_length=64)):
    """Each day's Moon phase, illumination and sign, and the exact times of the major phases."""
    from .chart import ChartError
    from .forecast import moon_calendar as build

    try:
        return build(year, month, tz)
    except ChartError as error:
        raise HTTPException(400, str(error))
