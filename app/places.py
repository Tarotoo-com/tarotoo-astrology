"""Birthplace search over a bundled city list (GeoNames extract, CC BY 4.0).

The data file is built by scripts/build_places.py from the GeoNames cities15000
dump: one city per line, tab-separated, sorted by population.
"""
from __future__ import annotations

import gzip
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# The compressed file is what the repo ships; a plain .tsv next to it is also accepted.
DATA_FILE = DATA_DIR / "places.tsv.gz" if (DATA_DIR / "places.tsv.gz").exists() else DATA_DIR / "places.tsv"


def fold(text: str) -> str:
    """Lower-case and strip accents, so 'munchen' finds 'München'."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).casefold().strip()


@dataclass(frozen=True)
class Place:
    id: int
    name: str
    admin: str
    country: str
    lat: float
    lng: float
    timezone: str
    population: int
    keys: tuple[str, ...]  # folded name variants used for matching

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.admin and self.admin != self.name:
            parts.append(self.admin)
        parts.append(self.country)
        return ", ".join(parts)

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "admin": self.admin, "country": self.country,
                "label": self.label, "lat": self.lat, "lng": self.lng, "timezone": self.timezone,
                "population": self.population}


class PlaceIndex:
    def __init__(self, path: Path = DATA_FILE):
        self.places: list[Place] = []
        self.by_id: dict[int, Place] = {}
        if not path.exists():
            return
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip() or line.startswith("#"):
                    continue
                gid, name, ascii_name, alternates, country, admin, lat, lng, tz, pop = line.rstrip("\n").split("\t")
                keys = {fold(name), fold(ascii_name)}
                keys.update(fold(a) for a in alternates.split(",") if a)
                place = Place(int(gid), name, admin, country, float(lat), float(lng), tz, int(pop),
                              tuple(k for k in keys if k))
                self.places.append(place)
                self.by_id[place.id] = place
        # Population order means the best-known city of a name comes first.
        self.places.sort(key=lambda p: -p.population)

    def search(self, query: str, limit: int = 8) -> list[Place]:
        return [place for place, _ in self.search_ranked(query, limit)]

    def search_ranked(self, query: str, limit: int = 8) -> list[tuple[Place, bool]]:
        """Places whose name or one of its other names (Roma, München) equals the query
        come first, flagged True; then places with a name starting with it."""
        q = fold(query)
        if len(q) < 2:
            return []
        exact, prefix = [], []
        for place in self.places:
            if any(k == q for k in place.keys):
                exact.append(place)
            elif any(k.startswith(q) for k in place.keys):
                prefix.append(place)
            if len(exact) >= limit:
                break
        return ([(p, True) for p in exact] + [(p, False) for p in prefix])[:limit]

    def get(self, place_id: int) -> Place | None:
        return self.by_id.get(place_id)
