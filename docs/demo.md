# The demo

Try TripAtlas without Traccar or Immich — or develop the web UI without a real installation. The demo brings a
made-up family ("Familie Beispiel", home in Kassel) with a camper van and a car, five trips (Brittany, Lake Garda,
the Dutch coast, the Harz mountains, a weekend in Hamburg), a flight to Mallorca and about 50 public-domain photos.

```bash
cd tools/demo
python3 build_demo.py        # once, needs internet: real roads from OSRM, CC0 photos from Openverse
docker compose up -d
```

Open <http://localhost:8099> and run the setup wizard:

| | |
|---|---|
| Traccar | `http://traccar:8082`, any e-mail and password |
| Immich | `http://immich:2283`, any API key |

`fake_services.py` stands in for Traccar and Immich: it answers exactly the requests TripAtlas makes. The documentation
screenshots and videos were recorded with this demo (`tools/demo/record.mjs`). Photo credits:
[tools/demo/data/CREDITS.md](../tools/demo/data/CREDITS.md).
