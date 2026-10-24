# Changelog

All notable changes. The format follows [Keep a Changelog](https://keepachangelog.com); versions follow
[Semantic Versioning](https://semver.org).

## [Unreleased]

### Added
- Account menu: switch between the accounts used on a device without retyping the user name; sign-in page lists them
- Optional app bridge (`window.TripAtlasApp`) so a host app can keep passwords behind the fingerprint

### Fixed
- After signing out or switching, the next account no longer lands on the previous account's page
- Country names were missing from a fresh clone (excluded by `.gitignore`)

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
- Videos play in the viewer (streamed from Immich, seekable)
- Photos taken on board an aircraft recognised by GPS altitude and shown as flights

### Places
- "Where I've been": globe with every place and the visited countries
- Place names from OpenStreetMap, summaries and nearby sights from Wikipedia, child-friendly texts from Klexikon
  (German) and Simple English Wikipedia — can be switched off

### Family
- Accounts with roles: administrator, member, child; trackers assigned per person
- Children's view: picture cards, trips as stories, read-only, never live positions (enforced by the API)

### Running it
- One Docker image (web UI + API), SQLite, migrations at start, daily consistent database snapshot
- Setup wizard that suggests the home location from where the trackers spend the nights
- Installable web app (PWA); English and German
- Demo with a made-up family, fake Traccar/Immich and public-domain photos (`tools/demo`)
