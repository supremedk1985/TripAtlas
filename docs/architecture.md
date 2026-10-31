# Architecture

```
            ┌───────────── TripAtlas container ─────────────┐
 Traccar ──▶│ services/sync.py ──▶ positions (SQLite) ──┐    │
 GPX/JSON ─▶│ importers/*       ──▶                     │    │
            │                                           ▼    │
            │ core/detection.py  (pure)  trips · stays · drives│
 Immich ◀──▶│ services/photos.py  ──▶  core/photos.py (pure)  │
 Wikipedia ◀│ services/places.py  (cached per ~1 km cell)     │
 Nominatim ◀│                                                 │
            │ api/*  (FastAPI, JSON)  ◀──  web/ (SvelteKit SPA)│◀── browser / app
            └─────────────────────────────────────────────────┘
```

## Principles

1. **One local source of positions.** Traccar is synced into the `positions` table; imports land there too. All
   detection works on that table, so a trip before the tracker existed (imported GPX) and one recorded live look the
   same.
2. **Pure core.** Everything that decides *what a trip is* lives in `server/tripatlas/core/` — plain functions over
   `Point`s, no database, no network, fully unit-tested. If you change a rule, change a test.
3. **Detected data is a cache.** `trips` and `stays` are thrown away and rebuilt whenever positions or settings
   change (`services/trips.py: recompute`). User content (titles, notes) lives in `annotations`, keyed by tracker +
   kind + *local start day*, so it survives recomputation even when the start moves by a few minutes.
4. **Read-only integrations.** TripAtlas never writes to Traccar or Immich. Everything specific to their APIs is in
   `integrations/` — when Immich changes its API, that is the one file to fix.
5. **Photos are not copied.** The web UI loads thumbnails through `/api/photos/{id}/thumbnail`, which proxies Immich
   with the user's own key (or the household key). TripAtlas stores only counts and the cover photo id.
6. **Security in the API, not the UI.** Role checks happen in `auth/deps.py` and in every endpoint; the children's
   interface is a convenience, the protection is that the API refuses changes and hides live data
   (`tests/test_api.py` locks this in).

## Server layout (`server/tripatlas/`)

| Package | Responsibility |
|---|---|
| `core/` | geometry, trip/stay/drive detection, photo matching, timeline, country codes — pure |
| `db/` | SQLAlchemy models, engine/session; `migrations/` holds the Alembic history |
| `integrations/` | HTTP clients: Traccar, Immich, OpenStreetMap/Wikipedia/Klexikon |
| `importers/` | file formats → `Point`s |
| `services/` | glue: settings (encrypted secrets), sync, recompute, photos, places, background jobs |
| `auth/` | password hashing (Argon2), sessions, login throttle, FastAPI dependencies for roles |
| `api/` | HTTP endpoints, grouped by topic |

Background work runs in one thread (`services/jobs.py`): sync Traccar → recompute changed trackers → look up up to 20
unknown places (Nominatim allows one request per second).

## Web layout (`web/src/`)

| Path | |
|---|---|
| `routes/+layout.svelte` | session loading and route guard (setup → login → kids) |
| `routes/+page.svelte` | the map explorer; owns the map layers and implements `MapControl` |
| `routes/visited` | globe with pins and visited countries |
| `routes/kids` | children's home and trip stories |
| `routes/settings`, `routes/setup` | settings tabs; the wizard reuses the same forms |
| `lib/map/` | MapLibre wrapper and layers (tracks, photo stacks, pins) — no Svelte inside layers |
| `lib/components/` | panels and widgets |
| `lib/i18n/` | dictionaries; `en.ts` is the reference |

## App bridge

TripAtlas runs in any browser; a host app that wraps it in a WebView can add what a web page cannot do safely — keep
passwords behind the fingerprint. The page looks for an optional object `window.TripAtlasApp` (see
`web/src/lib/accounts.ts`):

| method | |
|---|---|
| `accounts(): string` | JSON array of `{username, display_name}` the app holds a password for — never the passwords |
| `offerSave(json)` | after a sign-in with a typed password: `{username, password, display_name}`; the app asks the user |
| `signIn(username)` | the app verifies the user (fingerprint or screen lock), then calls `window.tripAtlasSignIn(username, password)` |
| `forget(username)` | remove a saved account |
| `changeServer()` | optional: the app shows its own screen for another server; the account menu and the sign-in page offer "Change server…" only when it exists |

The Android app in `android/` implements it. An app should expose the bridge only while its own TripAtlas address is loaded. Without the bridge the account menu
still lists the accounts recently used in this browser; the browser's password manager fills in passwords.

## Storage on the device

`web/src/service-worker.ts` keeps map tiles (cache-first, they sit under versioned paths), photo thumbnails
(cache-first: an asset id is the same picture forever) and GET API answers (network-first, stored copy only when the
network fails) in Cache Storage, up to a limit chosen per device. Tiles share one bucket; everything else goes into
a bucket per account. The page names the account with `u=<id>` on image URLs and the `X-TripAtlas-Account` header
on API calls — the server ignores both and checks access as always; they only choose the bucket, so switching
accounts on a shared device keeps each account's storage apart. An index in IndexedDB holds size and last use of
each entry; beyond the limit the least recently used go first (`web/src/lib/deviceCache/`).

## Data model

`users` ←→ `user_trackers` ←→ `trackers` → `positions` (tracker_id, t) · `trips` → `stays` (cache) ·
`annotations` (tracker, kind, day_key) · `places` (cell, lang) · `settings` (key → JSON) · `sessions` · `import_jobs`
