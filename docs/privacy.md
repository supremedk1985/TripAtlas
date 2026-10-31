# TripAtlas for Android – Privacy policy

*Deutsch weiter unten.*

As of 31 October 2026 · Provider: Daniel Korte

TripAtlas for Android (`de.korte_daniel.tripatlas`) shows the web interface of a TripAtlas server **that you run
yourself**. The developer runs no server for the app and receives no data from it: there is no developer account,
no advertising, no analytics or crash reporting and no sharing with third parties.

## What the app sends, and where

- **Only to the server address you enter.** The app loads that server's pages and the photos, maps and data your
  server provides. Who runs that server and what it stores is up to you (or whoever runs it); the TripAtlas server
  software keeps its data on that server only.
- When you check an address, the app asks `/api/health` on it to confirm it is a TripAtlas server.
- Links to other sites (Wikipedia, OpenStreetMap, Immich) open in your browser; their own policies apply there.
- The map background on your server's pages may be loaded from public tile services (OpenFreeMap / OpenStreetMap)
  configured on your server; place information comes from Wikipedia and Nominatim if your server has this turned on.

## What stays on the phone

- **The server address**, in the app's private storage.
- **Saved passwords** – only if you choose "Save" after signing in. They are encrypted with a key in the phone's
  keystore that only works after your fingerprint or screen lock, and never leave the phone. Adding a new fingerprint
  deletes them.
- **Cookies and cached pages** of your server, like in a browser, to keep you signed in.

The app is excluded from cloud backups. Uninstalling it deletes everything listed above.

## Permissions

- **Internet** – to reach your server. No other permission is requested; files for imports are picked with Android's
  own file picker, which gives the app access only to the files you choose.

## Contact

Questions via the contact address in the Google Play listing or an issue at
<https://github.com/supremedk1985/TripAtlas>.

---

# TripAtlas für Android – Datenschutzerklärung

Stand: 31. Oktober 2026 · Anbieter: Daniel Korte

TripAtlas für Android (`de.korte_daniel.tripatlas`) zeigt die Weboberfläche eines TripAtlas-Servers, **den du selbst
betreibst**. Der Entwickler betreibt für die App keinen Server und erhält keine Daten aus ihr: kein Konto beim
Entwickler, keine Werbung, keine Analyse- oder Absturzdienste, keine Weitergabe an Dritte.

## Was die App sendet, und wohin

- **Nur an die Serveradresse, die du einträgst.** Die App lädt die Seiten dieses Servers und die Fotos, Karten und
  Daten, die er liefert. Wer den Server betreibt und was er speichert, entscheidest du (bzw. sein Betreiber); die
  TripAtlas-Serversoftware hält ihre Daten nur auf diesem Server.
- Beim Prüfen einer Adresse fragt die App dort `/api/health` ab, um zu erkennen, ob es ein TripAtlas-Server ist.
- Links auf andere Seiten (Wikipedia, OpenStreetMap, Immich) öffnen im Browser; dort gelten deren Bedingungen.
- Der Kartenhintergrund auf den Seiten deines Servers kann von öffentlichen Kartendiensten (OpenFreeMap /
  OpenStreetMap) kommen, Ortsinformationen von Wikipedia und Nominatim – je nachdem, wie dein Server eingestellt ist.

## Was auf dem Handy bleibt

- **Die Serveradresse**, im privaten Speicher der App.
- **Gespeicherte Passwörter** – nur, wenn du nach der Anmeldung „Speichern“ wählst. Sie sind mit einem Schlüssel im
  Schlüsselspeicher des Handys verschlüsselt, der nur nach Fingerabdruck oder Displaysperre funktioniert, und
  verlassen das Handy nie. Kommt ein neuer Fingerabdruck dazu, werden sie gelöscht.
- **Cookies und zwischengespeicherte Seiten** deines Servers, wie im Browser, damit du angemeldet bleibst.

Die App ist von Cloud-Sicherungen ausgenommen. Deinstallieren löscht alles oben Genannte.

## Berechtigungen

- **Internet** – um deinen Server zu erreichen. Weitere Berechtigungen fragt die App nicht an; Dateien für Importe
  wählst du mit Androids eigener Dateiauswahl, die der App nur die gewählten Dateien zugänglich macht.

## Kontakt

Fragen über die Kontaktadresse im Google-Play-Eintrag oder als Issue unter
<https://github.com/supremedk1985/TripAtlas>.
