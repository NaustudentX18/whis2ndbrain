# Deployment & secure origin

The review unit is a loopback-only HTTP service put behind TLS by Tailscale Serve.
Plaintext HTTP is loopback-test-only; the only sanctioned remote origin is HTTPS.

## Topology (current, 2026-09-29)

```
device / phone / browser                sleeper host (omarchy)
        |                                        |
        |  https://omarchy.tail9760ad.ts.net:8765
        |                          tailscaled (Let's Encrypt for *.tail9760ad.ts.net,
        |                          tailnet-only, auto-renewed)
        |                                        |
        |                          http://127.0.0.1:8765  (python -m server serve,
        |                                                   binds loopback only)
```

- **TLS termination:** `tailscale serve --bg --https 8765 http://127.0.0.1:8765`.
  Cert is issued by Let's Encrypt for `omarchy.tail9760ad.ts.net` and renewed by
  tailscaled automatically. Reachable only inside the tailnet (no funnel).
- **App binding:** always `--host 127.0.0.1`. The app never binds a remote
  interface itself.
- **Cookies:** the session cookie is `Secure; HttpOnly; SameSite=Strict` — it only
  works over the HTTPS origin, which is the intent.

## Starting the unit

```
.venv/bin/python -m server serve \
  --root /data/whis2ndbrain/review \
  --token-file /data/whis2ndbrain/review/token \
  --host 127.0.0.1 --port 8765
```

(Owner decision pending: a supervised unit — systemd user service — so the
review unit survives reboots. Until then it is started by hand.)

## Pairing a device

1. Owner: sign in at the HTTPS origin → `/devices` → *Generate pairing code*
   (single use, 10 minutes).
2. Device/laptop: `python3 scripts/pair_device.py --server https://omarchy.tail9760ad.ts.net:8765 \
   --code <code> --name "bench pi" --out device-creds.json` (credentials file is mode 600).
3. The uploader takes `--server <https origin>` plus the paired token; plaintext
   `http://` is rejected unless it is loopback AND the test-only
   `allow_insecure_loopback` flag is set in tests.

## Verified end-to-end (2026-09-29, evidence in the vault build-pass plan)

Health/live 200 over TLS; owner form login → `Secure` session cookie works;
pairing-code create → device pair via `scripts/pair_device.py` from a second
machine → device-token capture upload 201 with receipt; device token rejected
403 on the review surface; anonymous 401. A silence capture through the live
stack returned an honest empty transcript (`transcript_source=model`, exit-5
no-speech path).

## Rollback / changes

- Remove the HTTPS origin: `tailscale serve --https=8765 off`.
- Re-add: `tailscale serve --bg --https 8765 http://127.0.0.1:8765`.
- Changing the tailnet name or tailnet DNS changes the origin URL; paired
  devices keep working (token-based, not name-based) but the configured
  `server` URL in device credentials must be updated.
