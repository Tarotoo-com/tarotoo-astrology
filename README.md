# Tarotoo astrology service

A small HTTP service that calculates natal (birth) charts for Tarotoo ([tarotoo.com](https://tarotoo.com)).
It returns planet positions, houses, aspects, an SVG wheel and a plain-text summary that
the site's Spiritual Chat ([tarotoo.com/psychic](https://tarotoo.com/psychic)) uses as context. It also offers a birthplace search over a
bundled city list, so no third-party API is involved at any step.

The astronomy comes from [Kerykeion](https://github.com/g-battaglia/kerykeion), which uses
NASA JPL ephemerides through libephemeris. The bundled data covers birth years 1850 to 2149 (Moon calendar months February 1850 to December 2149).

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check; also reports how many places are loaded |
| `POST` | `/places` | Birthplace search, body `{"q": "berl", "limit": 8}`: name, region, country, coordinates, IANA time zone, population, and whether the name matches exactly. The text goes in the body so it is not in request logs; `GET /places?q=berl` gives the same answer |
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
  "layout": "wheel",
  "language": "en"
}
```

Leave out `hour` and `minute` when the birth time is unknown: planets are still given,
houses and angles are not. Instead of `place_id` you can send `lat`, `lng` and `timezone`
(an IANA name such as `Europe/Berlin`). Local time is converted to UTC with the historical
rules of that zone, so a birth in 1990 gets 1990's offset, not today's.

The response holds `planets`, `houses`, `angles`, `aspects`, `elements`, `modes`, `summary`
(text facts for the chat prompt) and `svg`. The SVG is the service's own drawing
(`app/drawing.py`) in the site's dark style, labelled in `language` (en, es, fr, it, de,
pt): `layout` `wheel` is the square wheel alone, `full` one tall page with the wheel, the
placements, the aspect grid and the balance of elements and modes. A birth time in the hour
the clocks change is accepted; `input.time_note` says how it was read.


### Human Design

| Endpoint | What it returns |
| --- | --- |
| `POST /human-design` | Birth data (time required) and an optional `name`: type, strategy, signature and not-self theme, inner authority, profile, definition, incarnation cross (angle and the four gates), defined centers and channels, the 13 Personality and 13 Design activations (gate and line), a bodygraph SVG in the site's dark style and a text summary |
| `POST /human-design/compatibility` | Two people (`people`): electromagnetic channels (formed only together), companionship and dominance channels, the composite chart and a text summary |

The Personality is the sky at birth, the Design the sky when the Sun stood 88 degrees of
longitude earlier; the true lunar nodes are used. Gates follow the Rave mandala from gate 25
at 28°15' Pisces (`app/humandesign.py`).

### Forecasts

| Endpoint | What it returns |
| --- | --- |
| `POST /horoscope` | Transits to a birth chart for `period` `tomorrow`, `week` (7 days from `today`) or `month` (the calendar month of `today`): the most important major aspects with their exact moments (or "in effect from the start", "building, exact after this period"), the Moon's signs for a day or a week, and a text summary |
| `POST /synastry` | Two people (`people`: birth data and an optional `name` each): Kerykeion's relationship score and description, Sun, Moon, Venus and Mars signs, the closest aspects between the charts (pairs of two outer planets left out) and a text summary |
| `GET /moon-calendar?year=&month=&tz=` | Each day's Moon phase, illumination and sign at local noon, and the exact times of the new, first quarter, full and last quarter Moon in that month |

Birth data is the same as for `/chart`: `date`, `hour` and `minute` (or neither), and a `place_id` or `lat`, `lng` and `timezone`.

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
