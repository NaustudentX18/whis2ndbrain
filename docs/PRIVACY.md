# Privacy, safety & data lifecycle

> Engineering direction, not legal advice or a legal-compliance claim. No real voice-data pilot is authorised by this scaffold.

## The boundary

The intended first prototype is one person's device and private host, reachable on a LAN/private network. No cloud upload, public port forwarding, anonymous audio playback or always-listening mode by default. “Local-first” does not automatically mean encrypted, secure, private or recoverable: those claims require explicit choices and tests.

## Data flow to earn—not assume

```text
voice → local capture file → durable device queue → authenticated encrypted transport
      → durable host receipt → local processing → private review UI
      → owner-confirmed export to an allowlisted vault inbox
```

Every hop has a distinct state. A device health check cannot prove upload. HTTP acceptance cannot prove durable write. A transcript cannot prove what was said. A PWA cache cannot be treated as the canonical copy. Export is not vault sync.

## Non-negotiable rules

1. Keep source audio until a receipt matching capture identity and content hash is confirmed; cleanup requires an independently approved retention policy.
2. Use synthetic or expressly consented test audio. Never commit personal recordings, transcripts, databases, raw model assets, credentials, device identifiers or private-vault exports.
3. Treat audio uploads, transcript text and model output as untrusted data; render safely and never use speech as a command, path or shell input.
4. Separate device credentials from browser sessions; pair explicitly, rotate and revoke; use trusted TLS; do not put secrets in URLs or logs.
5. Bound upload bytes/duration, worker time/concurrency, storage and retries. Preserve the original when a model or browser fails.
6. Export only to an owner-approved allowlisted target; block traversal and symlinks; use atomic creation and conflict rather than overwrite when a person edited an existing note.
7. Distinguish trash, source purge, cache clear, export deletion and backup expiry. Do not imply one action deletes all copies.
8. No external action, automatic task creation, public-network exposure or live-vault writing until a separate explicit review and implementation authorization.

## Threats the future prototype must test

Stolen SD card or host; missing/read-only spool mount; abrupt power loss; disk full; lost upload response; replay or same-ID/different-content conflict; malicious oversized/truncated audio; revoked credential; CSRF/session expiry; leaked transcript in logs/cache/backup; malicious transcript rendering; symlink/path escape on export; model OOM/timeout; browser storage eviction; certificate renewal failure; user-edited export collision; audio-retention mismatch.

## Decisions required before real recordings

- What host and network scope will be used? How is TLS trusted and renewed on actual phones?
- Is device/server/browser storage encrypted at rest? If not, what physical-risk restriction is accepted?
- How long do device audio, server audio, transcripts, browser cache, logs, trash, exports and backups live?
- What consent/authority is required for recordings involving other people and in the owner's context/jurisdiction?
- What backup/restore and deletion guarantees can actually be demonstrated?
- Which host folder can a service account write? How are export conflicts preserved?

Record the owner's decisions before live data. Proposed retention numbers in research notes are candidates only; do not treat them as policy.

## Stop conditions

Stop an implementation or pilot branch if a target disk is uncertain, a battery is swollen/hot/compressed, the persistent data mount is missing, a durable receipt is uncertain, private data may be overwritten/exposed, TLS validation would be bypassed, a model/dependency license is unresolved, or one owner has a conflicting shared-file change. Continue only unrelated safe documentation/mock work within an authorized task.

## Proof required before a bounded pilot

Auth-negative tests; no raw public storage path; no transcript/token log leakage; revoked access denied; restart and lost-response reconciliation; deletion/retention behavior; export traversal and owner-edit conflict tests; trusted phone HTTPS; model runs with declared dependencies and no unexplained outbound request; backup restore; consent and owner-approved retention recorded. Mocks do not close hardware, model, real-browser or security gates.
