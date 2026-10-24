#!/usr/bin/env python3
"""Build the country data shipped with TripAtlas from Natural Earth (public domain, https://www.naturalearthdata.com).

Outputs
  server/tripatlas/data/country_names.json   normalised country name (any language Natural Earth knows) -> ISO 3166-1 alpha-2
  web/static/countries.geojson               110m country outlines with {iso, name} — for colouring visited countries

Run from the repository root:  python3 tools/build_countries.py
"""
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

SOURCE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_110m_admin_0_countries.geojson"
NAMES_SOURCE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_50m_admin_0_countries.geojson"
ROOT = Path(__file__).resolve().parent.parent
NAME_FIELDS = ["NAME", "NAME_LONG", "ADMIN", "FORMAL_EN", "NAME_SORT", "NAME_ALT", "GEOUNIT", "SUBUNIT", "BRK_NAME",
               "NAME_CIAWF"] + [f"NAME_{l}" for l in ("EN", "DE", "FR", "ES", "IT", "NL", "PL", "PT", "SV", "TR")]


def normalise(name: str) -> str:
    """Same rule as tripatlas.core.countries.normalise — keep both in sync."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def iso(props: dict) -> str | None:
    for k in ("ISO_A2_EH", "ISO_A2", "WB_A2"):
        v = props.get(k)
        if v and v != "-99":
            return v.upper()
    return None


def load(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def main() -> None:
    names: dict[str, str] = {}
    for f in load(NAMES_SOURCE)["features"]:
        p = f["properties"]
        code = iso(p)
        if not code:
            continue
        for field in NAME_FIELDS:
            if p.get(field):
                names.setdefault(normalise(p[field]), code)
    out = ROOT / "server/tripatlas/data/country_names.json"
    out.write_text(json.dumps(dict(sorted(names.items())), ensure_ascii=False, indent=0))
    print(f"{out}: {len(names)} names")

    shapes = load(SOURCE)
    features = []
    for f in shapes["features"]:
        code = iso(f["properties"])
        if not code:
            continue

        def r(c):
            return [r(x) for x in c] if isinstance(c[0], list) else [round(c[0], 3), round(c[1], 3)]
        f["geometry"]["coordinates"] = r(f["geometry"]["coordinates"])
        features.append({"type": "Feature", "properties": {"iso": code, "name": f["properties"]["NAME_EN"]},
                         "geometry": f["geometry"]})
    out = ROOT / "web/static/countries.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"{out}: {len(features)} countries, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
