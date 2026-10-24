# Changelog

All notable changes. The format follows [Keep a Changelog](https://keepachangelog.com); versions follow
[Semantic Versioning](https://semver.org).

## [Unreleased]

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
