# Whis2ndBrain

<div align="center">
  <img src="brand/wordmark.svg" width="520" alt="Whis2ndBrain — Catch the thought. Keep the signal." />
  <br /><br />
  <img src="brand/pip-hero.png" width="270" alt="Pip, a smiling cream-and-mint thoughtkeeper with lilac wings, holding a glowing spark" />
  <h2>Catch the thought. Keep the signal.</h2>
  <p><strong>A little pocket companion for ideas that arrive when your hands are busy.</strong></p>
  <p>Press to capture. Return to a clear, reviewable note. Keep the original in your care.</p>
  <p><a href="site/index.html"><strong>Explore the landing page</strong></a> · <a href="docs/PRODUCT.md">The product</a> · <a href="docs/ROADMAP.md">The roadmap</a></p>
  <p><sub>TESTED SOFTWARE PROTOTYPE · PHYSICAL RECORDER NOT YET COMMISSIONED</sub></p>
</div>

---

## A quieter way to remember

Whis2ndBrain is an **owner-controlled, local-first voice notebook in development**. The intended experience pairs a deliberate, push-to-talk pocket recorder with a private host and a mobile-friendly review space. Capture comes first; transcription and suggestions come later. Nothing a model proposes silently becomes your truth or takes an external action.

The planned hardware is a Raspberry Pi Zero 2 W with a Whisplay display/audio HAT and PiSugar 3 power board. **That physical device has not been built or tested.** Today this repository contains a working *software* prototype for portions of the journey, plus design concepts for the device and its companion.

<table><tr>
  <td width="33%" valign="top"><strong>01 · Catch it</strong><br />A deliberate capture should survive disconnection and restart before anything is called “saved”.</td>
  <td width="33%" valign="top"><strong>02 · Make sense of it</strong><br />An owner-controlled host can retain a receipt and offer a machine transcript and bounded suggestions.</td>
  <td width="33%" valign="top"><strong>03 · Make it yours</strong><br />Listen, search, correct and explicitly export a note—without overwriting your edits.</td>
</tr></table>

> **Honest status:** this repository contains a **tested software prototype**: host code that accepts and deduplicates WAV uploads, validates a *provisional* on-wire capture manifest against the received bytes, pairs devices with single-use codes and scoped credentials, queues processing in an isolated and killable transcription subprocess, exposes an owner review API (byte-range audio, trash and restore, edit-conflict protection, cursor pagination), serves the chosen browser shell, reports owner-only metrics, exports deterministic conflict-safe Markdown, and rehearses manifest backup with fail-closed restore. All evidence is synthetic/local test data; the manifest envelope is not a frozen cross-team contract. A single-owner supervised deployment behind TLS exists on a private tailnet as a documented procedure — not a public or multi-user service claim. Verification is automated — unit, integration (including an adversarial matrix of crash boundaries, hostile uploads and tombstone replay), browser end-to-end, Flutter and lint — and a scripted clean-host rehearsal proves the documented install path from the repository alone. None of this proves physical capture, real-phone usability, or an end-to-end commissioned device.

## Meet Pip ✦

**Pip** is a small, friendly thoughtkeeper: a soft mint-and-cream memory moth with lilac wings and a spark to hold onto. The new [Pip illustration](brand/pip-hero.png) is the face of this project; a [240 × 280 screen concept](device/assets/pip-screen-concept.html) explores how the same character might greet you on the future recorder.

Pip is **not** a wake word, an always-listening microphone, a chatbot, or an autonomous agent. On a real device, readable recording, retention, queue, connection and battery states must take priority over character animation. A talking or animated screen has not been implemented. See the [design guide](DESIGN.md) and [brand assets](brand/README.md).

## Built for trust, not magic

| Principle | What it means here |
| --- | --- |
| **Offline first** | The target device keeps a durable local capture queue. A network outage must not prevent recording. |
| **Receipts, not guesses** | “Received” requires a matching durable host receipt; a reachable server alone is not proof of sync. |
| **Machine help stays labelled** | Transcript and category/urgency suggestions remain reviewable, editable and free to say “unknown”. |
| **Your data, your decision** | Processing is planned for an owner-controlled host; export is explicit, allowlisted and conflict-aware. |
| **Retention is explicit** | The host prototype has a 168-hour audio hold; “original kept safe” does not mean indefinite storage. |

### The intended journey

    deliberate capture → durable device queue → matching host receipt
                                                ↓
                                  local processing + labelled suggestions
                                                ↓
                                    human review → opt-in Markdown export

The arrows describe the **design goal**, not a proven hardware-to-vault flow. The [product guide](docs/PRODUCT.md) explains the boundaries; the [privacy guide](docs/PRIVACY.md) explains the safeguards.

## What exists today

| Surface | Evidence and limit |
| --- | --- |
| Host | Python receipt/storage, idempotent manifest-checked ingest, job queue with isolated killable transcription, pair-once device auth with owner sessions, byte-range audio API, tombstones with restore, If-Match edit conflicts, deterministic conflict-safe export, owner-only metrics, manifest backup with fail-closed restore rehearsal, adversarial crash/hostile-upload integration matrix, scripted clean-host install rehearsal. Documented single-owner supervised deploy on a private tailnet; no public-service claim. |
| Device software | Durable spool/uploader prototype; **no microphone, button, display, power or reboot-on-Pi proof**. |
| Browser | Python-served mobile-first PWA shell — the chosen single browser client ([decision](docs/PWA-DECISION.md)) covering the full notes/media surface (feed, trash/restore, retry, pagination, edit conflicts, logout); desktop-Chromium end-to-end coverage, bounded offline snapshot with honest offline states and logout cache-clear, automated accessibility checks (320 px reflow, keyboard focus, contrast, control names). The web/ directory is still a scaffold; no real-phone proof. |
| App | Flutter companion client wired to the real API — pairing, cursor-paginated feed, header-authenticated byte-range playback, trash and restore, retry, If-Match conflict UX; CI builds a debug APK. No real-phone qualification. |
| AI | faster-whisper CPU transcription in an isolated subprocess (hard timeout, memory cap, honest failure states, manual retry) plus simple lexical category/urgency suggestions that remain a labelled stub. A public English sample is not a personal-note quality evaluation. |
| Hardware & enclosure | Uncommissioned and unmeasured. No battery-life, fit, release or certification claim. |

The public [roadmap](docs/ROADMAP.md) remains **0 of 8 evidence-gated milestones accepted**. Code presence is not gate acceptance; the owner's private task board is the detailed source of truth.

## Known limitations

- **Evidence is synthetic.** Tests, rehearsals and deployment checks run on synthetic
  audio and disposable data; no real-voice corpus exists in this repository, and none
  will until consent and retention decisions are made.
- **No commissioned device.** Microphone, button, display, power and reboot behaviour
  on the intended Pi Zero 2 W hardware are unproven; the recorder has not been built.
- **No real-phone qualification.** Neither the browser shell nor the debug APK has been
  exercised on the owner's actual phone.
- **Single-user by design.** One owner, one device fleet, private network; no
  multi-user tenancy, scaling or availability claims.
- **Bounded retention.** The host holds audio for 168 hours by default; "original kept
  safe" is not indefinite storage.
- **Suggestions are stubs.** Category/urgency suggestions are simple lexical
  heuristics, clearly labelled; they will misclassify.
- **Performance only smoke-measured.** A real-model latency harness ships in the repo and
  reports facts, but budget targets are not owner-agreed yet; storage and battery are
  unmeasured. The metrics endpoint reports facts, not verdicts.
- **Independent review pending.** Adversarial campaigns, a security/privacy review by
  a reviewer independent of the implementer, and a seven-day real-use pilot remain
  open roadmap gates.

## Explore the repository

| Where | What you will find |
| --- | --- |
| [Landing page](site/index.html) | Dependency-free project introduction; not the review app. |
| [Brand](brand/README.md) · [Design](DESIGN.md) | Original identity, Pip artwork and design/accessibility direction. |
| [Device](device/) · [Contracts](contracts/) | Software spool and in-progress shared data contracts; no physical runtime. |
| [Server](server/) | Host receipt, processing, review, PWA shell, settings/telemetry and at-rest encryption code. |
| [App](app/) | Flutter companion client wired to the real API (pairing, feed, playback, trash, settings); no real-phone qualification. |
| [CI](.github/workflows/ci.yml) | GitHub Actions: Python unit+lint and Flutter analyze/test/debug-APK; green on the latest push. |
| [Tests](tests/) · [Check script](scripts/check.sh) | Unit, integration (incl. the adversarial matrix), browser e2e and Flutter checks, plus a clean-host install rehearsal script and a real-model latency harness; not hardware or real-device proof. |
| [Docs](docs/) · [Contributing](CONTRIBUTING.md) | Product, privacy, roadmap, security, deployment, model, contracts, provenance & SBOM, accessibility and safe contribution guidance. |

For a quick local **syntax, unit and integration** check, run **bash scripts/check.sh** from the repository root with its existing Python virtual environment installed. It does not prove model, browser e2e or hardware readiness; the clean-host rehearsal (**scripts/clean_host_rehearsal.sh**) proves the documented install path end-to-end on a disposable directory. Do not point experimental export at a live vault or add real recordings, transcripts, credentials or model weights to Git.

---

<div align="center"><p><strong>For the thought you almost forgot.</strong></p><sub>Made carefully, one honest state and one verified step at a time.</sub></div>
