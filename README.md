# Whis2ndBrain

<div align="center">
  <img src="brand/wordmark.svg" width="520" alt="Whis2ndBrain — Catch the thought. Keep the signal." />
  <br /><br />
  <img src="brand/pip-hero.png" width="270" alt="Pip, a smiling cream-and-mint thoughtkeeper with lilac wings, holding a glowing spark" />
  <h2>Catch the thought. Keep the signal.</h2>
  <p><strong>A little pocket companion for ideas that arrive when your hands are busy.</strong></p>
  <p>Press to capture. Return to a clear, reviewable note. Keep the original in your care.</p>
  <p><a href="site/index.html"><strong>Explore the landing page</strong></a> · <a href="docs/PRODUCT.md">The product</a> · <a href="docs/ROADMAP.md">The roadmap</a></p>
  <p><sub>EARLY SOFTWARE PROTOTYPE · PHYSICAL RECORDER NOT YET COMMISSIONED</sub></p>
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

> **Honest status:** local host code can accept and deduplicate WAV uploads, queue processing, expose review routes, and produce conflict-safe Markdown. A software device spool and Python-served browser shell are being tested locally and may not yet be on GitHub. None of this proves physical capture, real-phone usability, or an end-to-end commissioned device.

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
| Host | Python receipt/storage, idempotent ingest, job queue, review API, local transcription path and conflict-safe export. No production deployment claim. |
| Device software | Durable spool/uploader prototype; **no microphone, button, display, power or reboot-on-Pi proof**. |
| Browser | Python-served mobile-first PWA shell in server/pwa.py; local HTTP and desktop Chromium mobile-width checks only. The web/ directory is still a scaffold; no real-phone proof. |
| AI | faster-whisper CPU transcription path and simple lexical category/urgency suggestions. A public English sample is not a personal-note quality evaluation. |
| Hardware & enclosure | Uncommissioned and unmeasured. No battery-life, fit, release or certification claim. |

The public [roadmap](docs/ROADMAP.md) remains **0 of 8 evidence-gated milestones accepted**. Code presence is not gate acceptance; the owner's private task board is the detailed source of truth.

## Explore the repository

| Where | What you will find |
| --- | --- |
| [Landing page](site/index.html) | Dependency-free project introduction; not the review app. |
| [Brand](brand/README.md) · [Design](DESIGN.md) | Original identity, Pip artwork and design/accessibility direction. |
| [Device](device/) · [Contracts](contracts/) | Software spool and in-progress shared data contracts; no physical runtime. |
| [Server](server/) | Host receipt, processing, review, PWA shell and export code. |
| [Tests](tests/) · [Check script](scripts/check.sh) | Synthetic/unit/integration/browser checks; not hardware or real-device proof. |
| [Docs](docs/) · [Contributing](CONTRIBUTING.md) | Product, privacy, roadmap and safe contribution guidance. |

For a quick local **syntax and unit** check, run **bash scripts/check.sh** from the repository root with its existing Python virtual environment installed. It does not prove model, browser, integration or hardware readiness. Do not point experimental export at a live vault or add real recordings, transcripts, credentials or model weights to Git.

---

<div align="center"><p><strong>For the thought you almost forgot.</strong></p><sub>Made carefully, one honest state and one verified step at a time.</sub></div>
