# Security

TripAtlas holds location histories of families — please report vulnerabilities privately via
[GitHub Security Advisories](https://github.com/supremedk1985/tripatlas/security/advisories/new), not as a public issue.

What TripAtlas does to protect its data:

- Passwords hashed with Argon2; sessions are random tokens, only their SHA-256 is stored.
- Login throttling (5 failures per user or address → 15 minutes pause).
- Cookie sessions are `HttpOnly`, `SameSite=Lax` and must come from the same origin for changes (CSRF).
- Stored Traccar/Immich credentials are encrypted (Fernet) with a key outside the database.
- Notes are sanitised on the server (allow-list) and again in the browser.
- Children's accounts are read-only and never receive live positions or ongoing trips; users without live access see
  positions only after a 6-hour delay.

Recommended operation: run behind HTTPS when reachable from the internet (`TRIPATLAS_SECURE_COOKIES=true`), give
TripAtlas a read-only Traccar user, and back up `secret.key` together with the database.
