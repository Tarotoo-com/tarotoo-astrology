"""Tarotoo astrology service: birthplace search and natal charts.

Run locally:  uvicorn app.main:app --reload
The WordPress site calls this over HTTP; it holds no user data and keeps no state.
"""
from __future__ import annotations

import os
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from .chart import ChartError, build_chart
from .places import PlaceIndex

app = FastAPI(title="Tarotoo astrology", version="0.1.0", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ALLOWED_ORIGINS", "https://tarotoo.com").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
places = PlaceIndex()


class ChartRequest(BaseModel):
    name: str = Field("", max_length=80)
    date: date
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    place_id: int | None = None
    # Coordinates and time zone may be given directly instead of a place id.
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    timezone: str | None = Field(None, max_length=64)
    place_label: str = Field("", max_length=120)
    country: str = Field("", max_length=2)
    house_system: str = Field("placidus", pattern="^(placidus|whole_sign|koch|equal)$")
    theme: str = Field("dark", pattern="^(dark|classic|black-and-white)$")
    layout: str = Field("wheel", pattern="^(wheel|full)$")
    language: str = Field("en", pattern="^(en|es|fr|it|de|pt)$")

    @field_validator("name", "place_label", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


@app.get("/health")
def health():
    return {"ok": True, "places": len(places.places)}


@app.get("/places")
def search_places(q: str = Query(..., min_length=2, max_length=60), limit: int = Query(8, ge=1, le=15)):
    return {"places": [p.public() for p in places.search(q, limit)]}


@app.post("/chart")
def chart(req: ChartRequest, format: str = Query("json", pattern="^(json|svg)$")):
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
    try:
        result = build_chart(
            name=req.name, birth_date=req.date, hour=req.hour, minute=req.minute,
            lat=lat, lng=lng, tz=tz, place_label=label, country_code=country,
            house_system=req.house_system, theme=req.theme, layout=req.layout, language=req.language,
        )
    except ChartError as error:
        raise HTTPException(400, str(error))
    if format == "svg":
        return Response(result["svg"], media_type="image/svg+xml")
    return result
