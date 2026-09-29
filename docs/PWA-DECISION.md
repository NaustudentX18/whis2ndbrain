# PWA stack decision (B2 / WB-033, WB-034) — 2026-09-29

**Decision: grow the Python-served review shell as the one browser client.**
The Flutter app (B1) remains the one native mobile client. No standalone
JavaScript SPA, no Flutter-web target. One client per form factor — not two
half-clients.

## Why

- The Python shell (`server/pwa.py`) already renders the owner surface
  (feed, filters, search, edit modal, audio, bounded service-worker cache,
  manifest) behind session auth, and now covers the full item-4 API surface:
  tombstone/restore, trash view, retry, cursor "load more", If-Match edit
  conflicts, logout. Two Chromium e2e scenarios prove it in CI.
- A standalone SPA would add a Node build toolchain to a Python-only host, a
  second auth/session implementation to audit, and another deployable — with
  no owner value for a single-user service.
- Flutter-web would duplicate B1's logic in a heavy canvas bundle and add a
  web build to CI; the Python shell shares templates/auth with the classic
  review page by construction.
- Server-driven pages keep the security story simple: the session CSRF token
  is injected server-side, no client bundle ships secrets, and the service
  worker caches only the shell (never API/audio).

## Consequences

- Shell work stays in this repo (`server/pwa.py`), server-tested via the
  existing e2e (Chromium) — no new toolchain, no npm supply chain.
- Offline behaviour stays deliberately bounded (B3): shell-only cache,
  honest first-load/offline states; capture durability is the device
  spool's job, never the browser's (project invariant #7).
- Revisit only if a second user or a public deployment appears — neither is
  in v1 scope.
