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
    main_keys: tuple[str, ...] = ()  # the folded name and ASCII name only

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
                main = {fold(name), fold(ascii_name)}
                keys = set(main)
                keys.update(fold(a) for a in alternates.split(",") if a)
                place = Place(int(gid), name, admin, country, float(lat), float(lng), tz, int(pop),
                              tuple(k for k in keys if k), tuple(k for k in main if k))
                self.places.append(place)
                self.by_id[place.id] = place
        # Population order means the best-known city of a name comes first.
        self.places.sort(key=lambda p: -p.population)

    def search(self, query: str, limit: int = 8) -> list[Place]:
        return [place for place, _ in self.search_ranked(query, limit)]

    def search_ranked(self, query: str, limit: int = 8) -> list[tuple[Place, bool]]:
        """Places named exactly as typed come first, flagged True. A place whose other name
        (Roma for Rome, München) is the query is flagged too, but only when it is bigger than
        every place with that main name, so a small town known locally as "Berlin" does not
        rank as Berlin. Then the other matches and the names starting with the query, by
        population. Queries of up to three letters match main names only."""
        q = fold(query)
        if len(q) < 2:
            return []
        short = len(q) <= 3
        main, other, prefix = [], [], []
        for place in self.places:
            keys = place.main_keys if short else place.keys
            if q in place.main_keys:
                main.append(place)
            elif q in keys:
                other.append(place)
            elif any(k.startswith(q) for k in keys):
                prefix.append(place)
            if len(main) >= limit:
                break
        biggest = max((p.population for p in main), default=-1)
        other_exact = [p for p in other if p.population > biggest]
        exact = sorted(main + other_exact, key=lambda p: -p.population)
        rest = [p for p in other if p not in other_exact] + prefix
        return ([(p, True) for p in exact] + [(p, False) for p in rest])[:limit]

    def get(self, place_id: int) -> Place | None:
        return self.by_id.get(place_id)
