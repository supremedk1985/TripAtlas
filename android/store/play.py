#!/usr/bin/env python3
"""Kleiner Google-Play-Helfer (Android Publisher API v3) ohne Zusatzpakete: signiert das JWT mit openssl.
Schlüssel: ~/.config/play-keys/play-dienstkonto.json (nie ins Repo). Aufruf siehe android/store/README.md."""
import base64, json, os, subprocess, sys, tempfile, time, urllib.parse, urllib.request

PAKET = "de.korte_daniel.tripatlas"
API = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PAKET}"
UPLOAD = f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{PAKET}"
SCHLUESSEL = os.path.expanduser("~/.config/play-keys/play-dienstkonto.json")

def b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=")

def token():
    k = json.load(open(SCHLUESSEL))
    jetzt = int(time.time())
    kopf = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    inhalt = b64(json.dumps({"iss": k["client_email"], "scope": "https://www.googleapis.com/auth/androidpublisher",
                             "aud": k["token_uri"], "iat": jetzt, "exp": jetzt + 3600}).encode())
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        os.chmod(f.name, 0o600); f.write(k["private_key"]); pfad = f.name
    try:
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", pfad], input=kopf + b"." + inhalt,
                             capture_output=True, check=True).stdout
    finally:
        os.unlink(pfad)
    daten = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                    "assertion": (kopf + b"." + inhalt + b"." + b64(sig)).decode()}).encode()
    return json.load(urllib.request.urlopen(k["token_uri"], daten))["access_token"]

_t = None
def anfrage(methode, url, daten=None, art="application/json"):
    global _t
    _t = _t or token()
    if isinstance(daten, (dict, list)): daten = json.dumps(daten).encode()
    r = urllib.request.Request(url, data=daten, method=methode, headers={"Authorization": "Bearer " + _t, "Content-Type": art})
    try:
        with urllib.request.urlopen(r, timeout=300) as a:
            t = a.read(); return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"{methode} {url} -> {e.code}: {e.read().decode()[:800]}")

if __name__ == "__main__" and sys.argv[1:] == ["pruefen"]:
    e = anfrage("POST", f"{API}/edits")
    print("Bearbeitung geöffnet:", e["id"])
    print("Spuren:", [t.get("track") for t in anfrage("GET", f"{API}/edits/{e['id']}/tracks").get("tracks", [])])
    print("Einträge:", [l.get("language") for l in anfrage("GET", f"{API}/edits/{e['id']}/listings").get("listings", [])])
    anfrage("DELETE", f"{API}/edits/{e['id']}")
    print("wieder verworfen")

def bild(edit, sprache, art, pfad):
    with open(pfad, "rb") as f:
        art_typ = "image/jpeg" if pfad.lower().endswith((".jpg", ".jpeg")) else "image/png"
        anfrage("POST", f"{UPLOAD}/edits/{edit}/listings/{sprache}/{art}?uploadType=media", f.read(), art_typ)

def hochladen(aab, spur="production", status="draft"):
    """Bündel, Texte, Bilder und eine Freigabe auf `spur` in EINER Bearbeitung; erst das Bestätigen macht sie gültig."""
    hier = os.path.dirname(os.path.abspath(__file__))
    e = anfrage("POST", f"{API}/edits")["id"]
    with open(aab, "rb") as f:
        b = anfrage("POST", f"{UPLOAD}/edits/{e}/bundles?uploadType=media", f.read(), "application/octet-stream")
    print("Bündel hochgeladen, versionCode", b["versionCode"])
    neu = json.load(open(f"{hier}/neu.json"))
    for sprache in ("de-DE", "en-US"):
        anfrage("PUT", f"{API}/edits/{e}/listings/{sprache}", json.load(open(f"{hier}/eintrag-{sprache}.json")))
        for art in ("icon", "featureGraphic", "phoneScreenshots"):
            anfrage("DELETE", f"{API}/edits/{e}/listings/{sprache}/{art}")
        bild(e, sprache, "icon", f"{hier}/grafik/symbol-512.png")
        bild(e, sprache, "featureGraphic", f"{hier}/grafik/titelgrafik-{sprache[:2]}.png")
        for name in sorted(os.listdir(f"{hier}/bilder/{sprache}")):
            bild(e, sprache, "phoneScreenshots", f"{hier}/bilder/{sprache}/{name}")
        print("Eintrag", sprache, "mit Bildern")
    anfrage("PUT", f"{API}/edits/{e}/tracks/{spur}", {"track": spur, "releases": [{
        "versionCodes": [str(b["versionCode"])], "status": status,
        "releaseNotes": [{"language": s, "text": t} for s, t in neu.items()]}]})
    print("Freigabe auf", spur, "als", status)
    print("Bestätigt:", anfrage("POST", f"{API}/edits/{e}:commit").get("id"))

if __name__ == "__main__" and sys.argv[1:2] == ["hochladen"]:
    hochladen(sys.argv[2], *sys.argv[3:])
