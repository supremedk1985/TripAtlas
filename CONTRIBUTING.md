# Contributing

Thanks for helping! A few rules keep TripAtlas maintainable:

1. **Open an issue first** for anything bigger than a bug fix, so we can agree on the approach.
2. **Rules come with tests.** A change to how trips, stays, drives or photo assignment are detected
   (`server/tripatlas/core/`) needs a test that shows the real-world case that motivated it — the existing tests read
   like a list of situations, please keep it that way.
3. **Security is enforced in the API.** Any new endpoint states who may call it (`current_user`, `require_editor`,
   `require_admin`, `tracker_for`). Children must never get write access or live positions — `tests/test_api.py`
   checks this; extend it for new data.
4. **No new external services without a switch.** TripAtlas runs at home; every request to a third party
   (map tiles excluded) must be optional and documented in the README.
5. **Translations:** add new UI texts to `web/src/lib/i18n/en.ts` and to every other language file. New languages
   are very welcome (and a child-friendly encyclopedia for it in `integrations/places.py: KIDS_SOURCES`).
6. **Database changes** need an Alembic migration (see docs/development.md).
7. **Never commit real data** — positions, photos, home coordinates, keys. Use made-up places in tests.

Before a pull request: `pytest`, `ruff check`, `npm run check`, `npm run build` — CI runs the same.

By contributing you agree that your contribution is licensed under the AGPL-3.0-or-later.
