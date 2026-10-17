"""Build data/places.tsv from a GeoNames cities dump (cities15000.txt or cities5000.txt).

Usage: python scripts/build_places.py path/to/cities15000.txt [path/to/admin1CodesASCII.txt]

Output columns: geonameid, name, asciiname, alternatenames (comma separated, trimmed),
country code, admin1 name, latitude, longitude, timezone, population.
Data: GeoNames, CC BY 4.0, https://download.geonames.org/export/dump/
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "places.tsv"


def fold(text: str) -> str:
    """Strip accents and lower-case, as app.places.fold does."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).casefold()
MAX_ALTERNATES = 12


def load_admin1(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    names = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        code, name, _ascii, _id = line.split("\t")
        names[code] = name
    return names


def main() -> None:
    source = Path(sys.argv[1])
    admin1 = load_admin1(Path(sys.argv[2]) if len(sys.argv) > 2 else None)
    rows, skipped = [], 0
    for line in source.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        gid, name, ascii_name, alternates, lat, lng = f[0], f[1], f[2], f[3], f[4], f[5]
        country, admin1_code, population, timezone = f[8], f[10], f[14], f[17]
        if not timezone:
            skipped += 1  # a chart needs the historical time zone; never guess one
            continue
        # Keep short Latin-script alternates (accented ones included, so "München" is
        # found for "Munich"); other scripts are left out to keep the file small.
        alts = [a for a in alternates.split(",")
                if a and len(a) <= 40 and fold(a).isascii() and a.lower() not in (name.lower(), ascii_name.lower())]
        rows.append((int(population or 0), "\t".join([
            gid, name, ascii_name, ",".join(alts[:MAX_ALTERNATES]), country,
            admin1.get(f"{country}.{admin1_code}", ""), lat, lng, timezone, population or "0",
        ])))
    rows.sort(key=lambda r: -r[0])
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8") as out:
        out.write("# GeoNames extract, CC BY 4.0, https://download.geonames.org/export/dump/ ; built by scripts/build_places.py\n")
        for _, row in rows:
            out.write(row + "\n")
    print(f"wrote {len(rows)} places to {OUT} ({skipped} skipped for missing time zone)")


if __name__ == "__main__":
    main()
