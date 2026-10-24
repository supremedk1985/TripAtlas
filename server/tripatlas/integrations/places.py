"""Knowledge about places from free public services. All of them ask for a descriptive User-Agent and moderate use:
- OpenStreetMap Nominatim (reverse geocoding): max. 1 request/second — enforced here with a global lock.
- Wikidata / Wikipedia REST API: summaries and nearby articles.
- Child-friendly encyclopedias per language (KIDS_SOURCES): Klexikon (de), Simple English Wikipedia (en).
Results are cached in the `places` table (services/places.py), so each place is looked up once."""

from __future__ import annotations

import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field

import httpx

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
WIKIDATA = "https://www.wikidata.org/w/api.php"

# MediaWiki API endpoints of child-friendly encyclopedias. Add your language here — see docs/contributing.md.
KIDS_SOURCES = {
    "de": ("https://klexikon.zum.de/api.php", "https://klexikon.zum.de/wiki/"),
    "en": ("https://simple.wikipedia.org/w/api.php", "https://simple.wikipedia.org/wiki/"),
}

_nominatim_lock = threading.Lock()
_nominatim_last = 0.0


@dataclass
class PlaceInfo:
    name: str | None = None
    region: str | None = None
    country: str | None = None
    country_code: str | None = None
    wikidata: str | None = None
    article_title: str | None = None
    article_url: str | None = None
    summary: str | None = None
    thumbnail_url: str | None = None
    kids_summary: str | None = None
    kids_url: str | None = None
    sights: list[dict] = field(default_factory=list)


class PlaceLookup:
    def __init__(self, user_agent: str, timeout: float = 15):
        self._http = httpx.Client(headers={"User-Agent": user_agent}, timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _json(self, url: str, **params) -> dict | None:
        try:
            r = self._http.get(url, params=params)
            return r.json() if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            return None

    def reverse(self, lat: float, lon: float, lang: str) -> dict | None:
        global _nominatim_last
        with _nominatim_lock:
            wait = 1.1 - (time.monotonic() - _nominatim_last)
            if wait > 0:
                time.sleep(wait)
            _nominatim_last = time.monotonic()
            return self._json(
                NOMINATIM, lat=lat, lon=lon, format="jsonv2", zoom=10, extratags=1, **{"accept-language": lang}
            )

    def search(self, query: str, lang: str, limit: int = 6) -> list[dict]:
        """Places matching a name or address (for setting the home location)."""
        global _nominatim_last
        with _nominatim_lock:
            wait = 1.1 - (time.monotonic() - _nominatim_last)
            if wait > 0:
                time.sleep(wait)
            _nominatim_last = time.monotonic()
            d = self._json(NOMINATIM_SEARCH, q=query, format="jsonv2", limit=limit, **{"accept-language": lang})
        return [
            {
                "name": r.get("name") or r.get("display_name", "").split(",")[0],
                "label": r.get("display_name"),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
            }
            for r in (d or [])
            if "lat" in r
        ]

    def wikipedia_title(self, wikidata_id: str, lang: str) -> tuple[str, str] | None:
        """(language, title) of the Wikipedia article for a Wikidata item, preferring `lang`, then English."""
        d = self._json(
            WIKIDATA,
            action="wbgetentities",
            ids=wikidata_id,
            props="sitelinks",
            sitefilter=f"{lang}wiki|enwiki",
            format="json",
        )
        links = ((d or {}).get("entities", {}).get(wikidata_id, {}) or {}).get("sitelinks", {})
        for code in (lang, "en"):
            if f"{code}wiki" in links:
                return code, links[f"{code}wiki"]["title"]
        return None

    def summary(self, lang: str, title: str) -> dict | None:
        return self._json(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(title.replace(" ", "_"), safe="")
        )

    def nearby(self, lat: float, lon: float, lang: str, radius_m: int = 10000, limit: int = 8) -> list[dict]:
        d = self._json(
            f"https://{lang}.wikipedia.org/w/api.php",
            action="query",
            list="geosearch",
            gscoord=f"{lat}|{lon}",
            gsradius=radius_m,
            gslimit=limit,
            format="json",
        )
        out = []
        for a in (d or {}).get("query", {}).get("geosearch", []):
            out.append(
                {
                    "title": a["title"],
                    "distance_m": round(a.get("dist", 0)),
                    "url": f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(a["title"].replace(" ", "_")),
                }
            )
        return out

    def kids_intro(self, lang: str, candidates: list[str]) -> tuple[str, str] | None:
        """First candidate (place, region, country …) that has an article in the child-friendly source."""
        src = KIDS_SOURCES.get(lang)
        if not src:
            return None
        api, base = src
        for title in [c for c in candidates if c]:
            d = self._json(
                api, action="query", prop="extracts", exintro=1, explaintext=1, titles=title, redirects=1, format="json"
            )
            for page in ((d or {}).get("query", {}).get("pages", {}) or {}).values():
                text = (page.get("extract") or "").strip()
                if text and "missing" not in page:
                    return clean_text(text), base + urllib.parse.quote(page["title"].replace(" ", "_"))
        return None

    def lookup(self, lat: float, lon: float, lang: str) -> PlaceInfo:
        info = PlaceInfo()
        rev = self.reverse(lat, lon, lang) or {}
        addr = rev.get("address", {})
        info.name = rev.get("name") or addr.get("city") or addr.get("town") or addr.get("village")
        info.region = addr.get("state") or addr.get("region")
        info.country = addr.get("country")
        info.country_code = (addr.get("country_code") or "").upper() or None
        info.wikidata = (rev.get("extratags") or {}).get("wikidata")
        found = self.wikipedia_title(info.wikidata, lang) if info.wikidata else None
        article = None
        if found and found[0] == lang:
            article = self.summary(lang, found[1])
        else:
            # A village often has no article in the reader's language, its municipality or region usually has:
            # better German text about the surroundings than an English one about the village.
            for larger in (addr.get("municipality"), addr.get("county"), addr.get("state_district"), info.region):
                if not larger or larger == info.name:
                    continue
                cand = self.summary(lang, larger)
                if cand and cand.get("type") == "standard" and cand.get("extract"):
                    article = cand
                    break
            if article is None and found:
                article = self.summary(*found)   # last resort: the article in another language
        if article:
            info.article_title = article.get("title") or (found[1] if found else None)
            info.article_url = (article.get("content_urls", {}).get("desktop", {}) or {}).get("page")
            info.summary = clean_text(article.get("extract"))
            info.thumbnail_url = (article.get("thumbnail") or {}).get("source")
        info.sights = [x for x in self.nearby(lat, lon, lang) if x["title"] != info.article_title][:6]
        kids = self.kids_intro(lang, [info.name, info.region])
        if kids:
            info.kids_summary, info.kids_url = kids
        return info


_IPA = re.compile(r"\s*\[[^\]]*\]")             # pronunciation: [ˈɪnsbʁʊk]
_EMPTY = re.compile(r"\s*\(\s*[;,]?\s*\)")      # what remains of a removed audio link: (), (;)
_BARE_LABEL = re.compile(r"\b[A-Z][\w-]*:\s*(?=[;,)])")  # "German: " whose value was removed
# Other names right after the name the text begins with: "Innsbruck (Bavarian: Innschbruck; Tyrolean: …) is …"
_LEAD_NAMES = re.compile(r"^((?:[A-ZÄÖÜ][\w.'-]*\s?){1,4})\(([^()]*[:;][^()]*)\)\s*")


def clean_text(text: str | None) -> str | None:
    """Wikipedia intros carry pronunciation and audio remnants that read as noise outside Wikipedia."""
    if not text:
        return text
    for _ in range(3):
        text = _IPA.sub("", text)
        text = _BARE_LABEL.sub("", text)
        text = re.sub(r"\(\s*[;,]\s*", "(", text)
        text = re.sub(r"\s*[;,]\s*\)", ")", text)
        text = _EMPTY.sub("", text)
    text = _LEAD_NAMES.sub(lambda m: m.group(1).rstrip() + " ", text, count=1)
    # navigation lines of children's encyclopedias ("⇒ Hier gibt es eine Übersicht …") lead nowhere outside them
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("⇒", "→")))
    return re.sub(r"[ \t]{2,}", " ", text).strip()

