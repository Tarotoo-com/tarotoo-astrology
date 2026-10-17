# Tarotoo astrology service

A small HTTP service that calculates natal (birth) charts for [tarotoo.com](https://tarotoo.com).
It returns planet positions, houses, aspects, an SVG wheel and a plain-text summary that
the site's Spiritual Chat uses as context. It also offers a birthplace search over a
bundled city list, so no third-party API is involved at any step.

The astronomy comes from [Kerykeion](https://github.com/g-battaglia/kerykeion), which uses
NASA JPL ephemerides through libephemeris. The bundled data covers birth years 1850 to 2150.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check; also reports how many places are loaded |
| `GET` | `/places?q=berl` | Birthplace search: name, region, country, coordinates, IANA time zone |
| `POST` | `/chart` | Natal chart as JSON (add `?format=svg` for the SVG alone) |

`POST /chart` body:

```json
{
  "name": "Optional name",
  "date": "1990-06-12",
  "hour": 14,
  "minute": 40,
  "place_id": 2950159,
  "house_system": "placidus",
  "theme": "dark"
}
```

Leave out `hour` and `minute` when the birth time is unknown: planets are still given,
houses and angles are not. Instead of `place_id` you can send `lat`, `lng` and `timezone`
(an IANA name such as `Europe/Berlin`). Local time is converted to UTC with the historical
rules of that zone, so a birth in 1990 gets 1990's offset, not today's.

The response holds `planets`, `houses`, `angles`, `aspects`, `elements`, `summary` (text
facts for the chat prompt) and `svg`.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8781
```

Set `ALLOWED_ORIGINS` (comma separated) to the sites allowed to call it from a browser;
the default is `https://tarotoo.com`.

### Birthplace data

```bash
python scripts/build_places.py cities15000.txt admin1CodesASCII.txt
```

builds `data/places.tsv.gz` from the GeoNames dumps (both files from
<https://download.geonames.org/export/dump/>). Places without a time zone are skipped
rather than guessed. The service starts without this file; `/places` then returns nothing.

### Deploy

`deploy/` has a systemd unit and an nginx `location` block. The service listens on
localhost only; nginx exposes it under `/astro/` on the site and applies rate limiting.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The reference chart (Berlin, 12 June 1990, 14:40) was verified independently with
Skyfield/JPL and Swiss Ephemeris; the tests check every planet and both angles to the
arcminute, the historical time-zone conversion, the unknown-time case and the input
validation.

## Licence and credits

This service is released under the GNU Affero General Public License v3 (see `LICENSE`),
the licence of Kerykeion, on which it depends. Birthplace data adapted from
[GeoNames](https://download.geonames.org/export/dump/), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), filtered and reformatted for
Tarotoo; data supplied without warranty.
