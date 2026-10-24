"""Country names → ISO 3166-1 alpha-2 codes. Sources name countries differently (Immich: "The Netherlands",
Nominatim in German: "Niederlande"); TripAtlas stores codes and lets the client translate them
(e.g. Intl.DisplayNames in the browser). Data: tools/build_countries.py."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data" / "country_names.json"


def normalise(name: str) -> str:
    """Same rule as tools/build_countries.py — keep both in sync."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@lru_cache
def _names() -> dict[str, str]:
    return json.loads(_DATA.read_text())


def country_code(name: str | None) -> str | None:
    if not name:
        return None
    if len(name) == 2 and name.isalpha():
        return name.upper()
    return _names().get(normalise(name))
