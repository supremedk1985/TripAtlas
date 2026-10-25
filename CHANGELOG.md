# Changelog

All notable changes. The format follows [Keep a Changelog](https://keepachangelog.com); versions follow
[Semantic Versioning](https://semver.org).

## [Unreleased]

### Added
- Automatic import: a tracker gets an import key (*Settings → Trackers → Automatic import*, shown once, only its
  hash is kept); an app sends each recording to `POST /api/imports/push` with `Authorization: Bearer <key>` — no
  sign-in, only to that tracker, wrong keys are slowed down (migration 0008)
- *Hide day trips without photos* per tracker: a bike's daily ride to work is not a trip
- Delete a photo or video from the viewer (*i* → *Delete (also in Immich)*), after two clear questions; it goes to
  Immich's trash with the user's Immich access; children cannot
- *Does not belong to this trip* also for the cover photo, the map stacks of an open trip and the diary
- Take photos out of a trip: *We were not there – no photos* (a car lent to someone) or *Does not belong to this
  trip* in the photo viewer; kept per trip in `trip_photo_choices` (migration 0007), surviving recomputation;
  `PUT /api/trips/{id}/photo-choice`, `POST /api/trips/{id}/photos/{asset}/exclude`
- *Where I've been* by year: a row of years (all years, 2026, 2025, …) limits pins, countries, flights and a
  place's photos to that year (household time zone); `GET /api/visited?year=` and `years` in the answer
- Diary: a third view next to *Map* and *Where I've been* — every trip as a picture card by year, opened as a story
  with the route, one chapter per place (notes, photos, videos, *All n photos*, text about the place); the same
  presentation as the children's view, which now shares it. *As diary* on a trip and *On the map* switch between them
- Zoom into a photo in the viewer: pinch, double tap (or double click) and mouse wheel, drag to move; past 1.6×
  the full resolution is loaded (Immich "fullsize"); swiping pages only while not zoomed
- A button on the map (under full screen) hides or shows the photo stacks — also with a trip open and in full
  screen, so the route stays visible
- A note in the video viewer and on the status page when Immich streams videos at full size (they stutter on
  a weak connection), with the steps to make Immich keep 720p copies for playback
- Storage on this device: map tiles, photos and trip data that were looked at stay on the device up to a chosen size
  (Settings → Profile; 1 GB unless changed), least recently used first out; a bucket per account, so switching
  accounts keeps everything and never mixes them up. *Save for offline* on a trip stores its map area, photos and
  details ahead of a journey; TripAtlas also starts without network (needs HTTPS)

### Changed
- The photo overview with one or two columns uses a medium size (about 50 KB instead of 500 KB per photo), made
  once from Immich's preview and kept in `<data>/cache/medium` (limit `TRIPATLAS_MEDIUM_CACHE_MB`, default 2048)
- The photo positions for the map are sent again only when they changed (ETag)

### Fixed
- The same ride imported twice was added twice when one export wrote milliseconds and the other did not (or cut
  the seconds off): import times are rounded to whole seconds and a point within 4 s of an existing one is the same
- A vehicle with higher photo priority claimed photos near it also while parked at home — a bike ride round the
  village got none of its photos; it now claims only while away
- Bike lengths no longer count gaps between recordings (the bike on the camper's rack): a holiday with rides from
  the campsite showed 1,173 instead of 483 km. Bike settings now also apply to the timeline and drives
- Phone layout chosen from the measured window instead of CSS orientation: an Android WebView reports 0 px height
  to media queries, so an upright phone got the side-by-side layout; full screen filled only half the map
- Service worker: a damaged Cache Storage (app killed while writing) made every request fail with "server cannot
  be reached"; storage faults now fall back to the network and clear that store; a new worker takes over at once
- No drawing on a map that was already removed (TypeError reading `getSource` after leaving a page)
- Back (Android's gesture, the browser's button) closes what is open first — photo viewer (a photo opened from the
  overview goes back to the overview), info panel, account menu, map full screen, place cards, notes — instead of
  leaving the page behind them; "All trips" really goes back, so back afterwards does not reopen the trip
- A phone turned sideways: list and map side by side instead of a thin strip under the map; a photo fits the screen
  after turning (it stayed at its old size and was cut off); the overview keeps its tile size (more columns instead
  of a few huge tiles); cover photos and the children's globe no longer taller than the screen
- Account menu opened off the left edge of the screen when its button sat on the left (children's view on a
  phone); the countries note on the children's globe was covered by the map's sources
- Sign-in page: every letter typed into the user name jumped to the password field
- A single corrupt GPS fix far away (e.g. one dashcam point near London on a drive in Germany) pulled the map view of
  a trip off centre and zoomed it far out; such spikes are now left out of routes, trips and map bounds
- Back from a trip is a clear "‹ All trips" button, with the vehicle's pictogram and name next to it
- Many photos at once (an overview opened for the first time) failed after 30 s or restarted the server: every
  request kept a database connection while it waited, and each worker thread kept its own memory arena. Requests now
  hand the connection back before waiting for Immich, scale at most three photos at a time (JPEG decoded at reduced
  size) and the image sets `MALLOC_ARENA_MAX=2`; 120 new photos at once now take 4 s and 234 MB
- Photo strips in the trip timeline showed the thumbnails on top of each other instead of side by side
- Trip list and vehicle filter show the vehicle's pictogram instead of a coloured dot (a red dot means "on the road")
- The map could stay at half height when the page grew while the map was starting (in an app: the keyboard closing
  after signing in)

## [0.2.0] – 2026-10-25

### Added
- Tracker kind *Bicycle*: every ride counts, also without a night away ("day ride"); bike pictogram on the map
- Tracker kind can be chosen in *Settings → Trackers*
- Notes on the map: pin a note to the place of a photo ("our first campsite"); everyone sees them, children
  cannot change them; *Photos from here* opens the photos around a note

- Photo viewer: date, place and camera under each photo; the i button shows all details and every EXIF
  entry of the file

### Changed
- GPX is imported as a stream (files of several hundred MB, e.g. a bike app's export of all rides)
- Imports keep at most one point every 10 seconds; the import message says how many were read, kept and new

### Fixed (independent release review)
- Making an account a child now takes live access away (it kept seeing current positions)
- A failed import leaves nothing behind (part of a broken file used to stay); impossible coordinates are skipped
- "Where I've been" works without Immich (tracker pins only) instead of failing
- Place search no longer breaks when two results have the same label
- Accounts without live access no longer see photos from the last 6 hours (they could tell where someone is)
- Sparse recordings (a point every 10–15 min) count their distance; GPS jumps still do not
- Login throttle per account and device instead of locking every account behind an address; unknown user names
  take as long as wrong passwords; `X-Forwarded-For` trusted only from private networks (`FORWARDED_ALLOW_IPS`)
- Map notes can be changed or removed only by their author or an administrator; long notes are limited in the
  dialog and errors are shown; notes can also be pinned from a trip's photos
- Status page shows Traccar errors; database files are readable for TripAtlas only; changing your password signs
  out your other devices; children cannot rename themselves; numbers in the UI language; day rides named after
  where they went; sharper overview tiles on large screens; a missing video answers 404

### Changed (test with a non-technical user)
- New accounts see every vehicle by default; the role is explained in the form; empty lists say why
  ("no vehicle shared with your account" instead of "no trips yet")
- The setup counts as finished as soon as "Done!" shows
- Connection errors in plain words with the likely fix (e.g. `localhost` means TripAtlas itself); `http://` is
  added when left out
- Map labels and country names in the reader's language; times of notes and imports in local time
- Tracker kind *Camper van* with its own pictogram; trips without photos show the vehicle's symbol
- Children's texts no longer fall back to an article about the whole country; no links out of the children's view
- Short explanations next to home radius, minimum distance, photo priority, display and user name
- Trips get their title as soon as the place name is known (no more "Trip" after an import)
- Docs: how to edit compose.yaml, Traccar/Immich on the same machine

## [0.1.0] – 2026-10-24

First public version.

### Trips
- Trips, overnight stays and drives recognised automatically from Traccar positions (a trip = at least one night
  away from home); thresholds adjustable per household
- Trip details: day-coloured route, replay slider with two handles, timeline, titles and rich-text notes for trips
  and overnight stays
- Import of GPX, Google location history (Takeout `Records.json` and the on-device Timeline export) and GeoJSON

### Photos
- Photos from Immich on the map as clustered stacks — per trip and all of them, independent of any tracker
- Photos without GPS placed along the route; priority between vehicles travelling together
- Videos play in the viewer (streamed from Immich, seekable); overview of all photos and videos, 3/2/1 per row
- Photos taken on board an aircraft recognised by GPS altitude and shown as flights

### Places
- "Where I've been": globe with every place and the visited countries
- Place names from OpenStreetMap, summaries and nearby sights from Wikipedia, child-friendly texts from Klexikon
  (German) and Simple English Wikipedia — can be switched off

### Family
- Accounts with roles: administrator, member, child; trackers assigned per person
- Children's view: picture cards, trips as stories, read-only, never live positions (enforced by the API)

### Accounts
- Account menu with the accounts used on a device; profile pictures, cropped in the browser
- Optional app bridge (`window.TripAtlasApp`) so a host app can keep passwords behind the fingerprint

### Running it
- One Docker image (web UI + API), SQLite, migrations at start, daily consistent database snapshot
- Setup wizard that suggests the home location from where the trackers spend the nights
- Installable web app (PWA); English and German
- Demo with a made-up family, fake Traccar/Immich and public-domain photos (`tools/demo`)
