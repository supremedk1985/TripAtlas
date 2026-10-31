# TripAtlas for Android

A small Android app around the TripAtlas web interface: it remembers the address of **your own** TripAtlas server and
shows its pages in a WebView, plus what a web page cannot do on its own — keep passwords behind the fingerprint
(the [app bridge](../docs/architecture.md#app-bridge)), the file picker for imports, full screen for map and videos.
Without a server it only shows the connect screen; how to run one is in [docs/installation.md](../docs/installation.md).

Google Play: `de.korte_daniel.tripatlas` · privacy policy: [docs/privacy.md](../docs/privacy.md)

## Build

Needs JDK 17+ and the Android SDK (`local.properties` with `sdk.dir=…`).

```bash
./gradlew testDebugUnitTest lintDebug assembleDebug   # debug build: package suffix .debug, WebView debuggable
./gradlew bundleRelease                               # store bundle, minified
```

The release build is signed with the key named in `local.properties` (`RELEASE_STORE_FILE`, `RELEASE_STORE_PASSWORD`,
`RELEASE_KEY_ALIAS`, `RELEASE_KEY_PASSWORD`); without these it falls back to the debug key. Keys never go into the
repository.

## Layout

| | |
|---|---|
| `MainActivity.kt` | first start / "Change server" → `SetupScreen`, otherwise `AtlasScreen` |
| `Server.kt` | turns what the user typed into addresses (https first, then http), checks `GET /api/health` |
| `ui/AtlasScreen.kt` | the WebView: own pages stay in the app, other links open in the browser; bridge `window.TripAtlasApp` only while a page of the server is loaded |
| `AccountVault.kt` | saved passwords, AES-GCM with a keystore key that needs the fingerprint or screen lock; per server |

The launcher shortcut (long press on the icon) and the menu entry "Change server…" in the web interface (shown only
when the bridge offers `changeServer`) lead back to the connect screen.

## Store listing

`store/` holds what `store/play.py` uploads in one edit: bundle, texts (`eintrag-<lang>.json`), release notes
(`neu.json`), icon and feature graphic (`grafik/`, rendered from the HTML files next to them) and the screenshots
(`bilder/<lang>/`). The screenshots show the made-up demo family from `tools/demo` (public-domain photos), taken at
1080×2160 in the emulator.

```bash
python3 store/play.py pruefen                                   # opens and discards an edit: access works?
python3 store/play.py hochladen app/build/outputs/bundle/release/app-release.aab [track] [status]
```

The service account key is read from `~/.config/play-keys/play-dienstkonto.json` and never committed.
