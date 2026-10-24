# Development

## Server

```bash
cd server
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                       # all tests, no network needed
TRIPATLAS_DATA_DIR=./data .venv/bin/uvicorn tripatlas.main:app --reload --port 8097
```

API documentation (OpenAPI) is served at `http://localhost:8097/api/docs`.

### Database changes

1. Change `tripatlas/db/models.py`.
2. `TRIPATLAS_DATA_DIR=./data .venv/bin/alembic revision --autogenerate -m "what changed"`
3. Read the generated file in `tripatlas/migrations/versions/` — autogenerate misses renames and data moves.
4. Migrations run automatically at startup.

### Lint

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## Web

```bash
cd web
npm ci
npm run dev        # http://localhost:5173, proxies /api to http://127.0.0.1:8097 (TRIPATLAS_API to change)
npm run check      # TypeScript + Svelte
npm run build      # → web/build, served by the server
```

UI texts go into `src/lib/i18n/en.ts` (reference) and every other language file; TypeScript reports missing keys.

## Docker

```bash
docker build -f docker/Dockerfile -t tripatlas:dev .
docker run --rm -p 8097:8097 -v $PWD/data:/data tripatlas:dev
```

## Country data

`server/tripatlas/data/country_names.json` and `web/static/countries.geojson` are generated from Natural Earth:
`python3 tools/build_countries.py`.
