# TripAtlas

**Your family's travel map — self-hosted.** TripAtlas combines the GPS track of your camper van, car or phone
([Traccar](https://www.traccar.org)) with your photos ([Immich](https://immich.app)) and turns them into a map of
every trip you have taken: where you drove, where you slept, what you saw, and what Wikipedia knows about the places.

- 🚐 **Trips are recognised automatically** — every time a tracker spends a night away from home. Overnight stays,
  drives, kilometres and countries come for free.
- 📷 **Photos where they were taken** — as stacks on the map, per trip or all of them, independent of any tracker.
  Photos without GPS (system cameras) are placed along the route.
- 📍 **Where I've been** — a globe with a pin for every place and every country you have visited.
- 📖 **Knowledge about places** — Wikipedia summaries and nearby sights for every overnight stay.
- 👨‍👩‍👧 **Made for families** — user accounts with roles. **Children** get their own simple, read-only view with big
  pictures and child-friendly texts ([Klexikon](https://klexikon.zum.de), Simple English Wikipedia), and never see
  where someone is right now.
- ✍️ **Titles and notes** for trips and overnight stays (rich text).
- ⬆️ **Import** GPX files, Google location history (Takeout and the new on-device Timeline export) and GeoJSON — for
  the trips before you had a tracker.
- 🔒 **Private by design** — everything runs on your server. Photos stay in Immich, positions are read-only from
  Traccar. Place lookups (OpenStreetMap, Wikipedia) can be switched off.

> Status: early (0.1). It runs in daily use for one family; expect rough edges. Feedback and contributions welcome.

## Quick start

```bash
mkdir tripatlas && cd tripatlas
curl -O https://raw.githubusercontent.com/supremedk1985/tripatlas/main/docker/compose.example.yaml
mv compose.example.yaml compose.yaml
docker compose up -d
```

Open `http://<your-server>:8097` — the setup wizard asks for

1. an administrator account,
2. your home (tap it on the map) and time zone,
3. the Traccar and Immich addresses with an API token/key (both optional, test button included),
4. which Traccar devices to follow.

TripAtlas then fetches the history and recognises your trips (a few minutes for a year of data).

### Requirements

- Docker (amd64; arm64 images are built by CI but not yet tested on real hardware). About 100–150 MB RAM
  (105 MB measured with two trackers, 40,000 positions and 42,000 photos).
- Traccar (optional) — a read-only user or API token is enough. Tested with Traccar 6.16.
- Immich (optional) — an API key with read access to assets. Tested with Immich 3.3; older versions may lack the
  `/api/map/markers` endpoint the photo layer uses.

### Behind a reverse proxy

Serve TripAtlas over HTTPS if it is reachable from the internet, and set `TRIPATLAS_SECURE_COOKIES=true`.
The container honours `X-Forwarded-*` headers.

## Configuration

Almost everything is configured in the web UI (*Settings*). Environment variables:

| Variable | Default | |
|---|---|---|
| `TRIPATLAS_DATA_DIR` | `/data` | database and `secret.key` |
| `TRIPATLAS_DATABASE_URL` | SQLite in the data dir | SQLAlchemy URL; only SQLite is tested so far |
| `TRIPATLAS_SECRET_KEY` | generated into `secret.key` | encrypts stored Traccar/Immich credentials |
| `TRIPATLAS_SECURE_COOKIES` | `false` | `true` behind HTTPS |
| `TRIPATLAS_SYNC_INTERVAL_MINUTES` | `5` | how often Traccar is polled |
| `TRIPATLAS_SESSION_DAYS` | `30` | web sign-in lifetime |
| `TRIPATLAS_BACKUP_KEEP` | `7` | daily database snapshots kept in `data/backups/` (0 = off) |

**Backup:** the data directory. TripAtlas writes a consistent copy of its SQLite database to `data/backups/` once a
day (keeps 7, `TRIPATLAS_BACKUP_KEEP`), so a file-level backup of the folder is safe even while it runs. Restore =
stop the container, copy a snapshot over `tripatlas.db`, start. Keep `secret.key` with it (it decrypts the stored
Traccar/Immich credentials). Positions imported from files exist only here.

## How trips are recognised

A trip is a period in which a tracker is further from home than the home radius (default 4 km) **and** spends at
least one night away (its position at 3 a.m.). A night at home ends a trip; a short stop at home during the day does
not. Each night's location becomes an overnight stay; consecutive nights within 5 km are the same stay. The thresholds
are adjustable under *Settings → Household*. The rules and the real cases behind them are documented in
[`server/tripatlas/core/detection.py`](server/tripatlas/core/detection.py).

## Roles

| | Administrator | Member | Child |
|---|---|---|---|
| See trips of assigned trackers | all | ✓ | ✓ |
| Live positions, ongoing trips | ✓ | ✓ (can be turned off) | ✗ (can be turned on) |
| Titles, notes, imports | ✓ | ✓ | ✗ |
| Users, trackers, connections | ✓ | ✗ | ✗ |
| Interface | full | full | simplified "kids" view |

## Development

See [docs/development.md](docs/development.md) — and [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
Architecture overview: [docs/architecture.md](docs/architecture.md).

## Credits

Map tiles: [OpenFreeMap](https://openfreemap.org) · © [OpenStreetMap](https://www.openstreetmap.org/copyright)
contributors · Country shapes: [Natural Earth](https://www.naturalearthdata.com) · Place texts:
[Wikipedia](https://www.wikipedia.org) and [Klexikon](https://klexikon.zum.de) (CC BY-SA) · Maps by
[MapLibre GL JS](https://maplibre.org).

## License

[AGPL-3.0-or-later](LICENSE). If you run a modified TripAtlas as a service for others, share your changes.
