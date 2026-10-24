# The demo

Try TripAtlas without Traccar or Immich — or develop the web UI without a real installation. The demo brings a
made-up family ("Familie Beispiel", home in Kassel) with a camper van and a car, five trips (Brittany, Lake Garda,
the Dutch coast, the Harz mountains, a weekend in Hamburg), a flight to Mallorca and about 50 public-domain photos.

```bash
cd tools/demo
python3 build_demo.py        # optional: the demo data is in the repository; this only fetches the photos
mkdir -p demo-data           # as your own user, before the first start (TripAtlas runs as uid 1000)
docker compose up -d
```

`build_demo.py` needs Python 3 with Pillow (`pip install pillow`). Without pip on the machine, run it in a container:
`docker run --rm -u $(id -u) -e HOME=/tmp -v "$PWD":/demo -w /demo python:3.12-slim sh -c "pip -q install pillow && python build_demo.py"`.
Without the photos the demo works too, just with empty photo stacks.

The fake Traccar and Immich install their Python packages at every start: they need internet and take about a
minute before they answer. Names of vehicles and people are German; `DEMO_LANG=en` in `compose.yaml`
(environment of `traccar` and `immich`) makes them English. Port taken? Change `8099` in `compose.yaml`.

To try the import, use `data/sauerland-weekend.gpx` (a weekend in the Sauerland that is not in the tracker data):
*Settings → Import*, pick a tracker, choose the file.

Open <http://localhost:8099> and run the setup wizard:

| | |
|---|---|
| Traccar | `http://traccar:8082`, any e-mail and password |
| Immich | `http://immich:2283`, any API key |

`fake_services.py` stands in for Traccar and Immich: it answers exactly the requests TripAtlas makes. The documentation
screenshots and videos were recorded with this demo (`tools/demo/record.mjs`). Photo credits:
[tools/demo/data/CREDITS.md](../tools/demo/data/CREDITS.md).
