# Whis2ndBrain

<div align="center">
  <img src="brand/wordmark.svg" width="520" alt="Whis2ndBrain — Catch the thought. Keep the signal." />
  <br /><br />
  <img src="brand/pip-hero.png" width="270" alt="Pip, a smiling cream-and-mint thoughtkeeper with lilac wings, holding a glowing spark" />
  <h2>Your best ideas don’t wait for you to sit down.</h2>
  <p><strong>A pocket thoughtkeeper for the thoughts that find you mid-walk, mid-moment, mid-everything.</strong></p>
  <p>Press. Speak. Release. The thought is durably caught, transcribed on your own machine,<br />and waiting as a note you’ll actually find again.</p>
  <p>
    <a href="site/index.html"><strong>Feel the page</strong></a> ·
    <a href="docs/PRODUCT.md"><strong>The product</strong></a> ·
    <a href="docs/ROADMAP.md"><strong>The roadmap</strong></a>
  </p>
  <p><sub>TESTED SOFTWARE PROTOTYPE, LIVE TODAY · THE POCKET RECORDER IS IN COMMISSIONING</sub></p>
</div>

---

## Why this exists

The crossing-light idea. The almost-remembered name. The perfect sentence that arrived while your hands were full. **They deserve better than “note to self, later.”**

Whis2ndBrain is a deliberate, push-to-talk pocket recorder paired with a private host: capture that survives disconnection, transcription that runs on hardware you own, and review/export that never loses your edits. Nothing listens unless you’re holding the button. Nothing leaves your machines. Nothing a model suggests silently becomes your truth.

The hardware is a Raspberry Pi Zero 2 W with a Whisplay display/audio HAT and a PiSugar 3 power board — **commissioning now, after the software reached proof** (see [the build log](#the-build-log)). Until the device is proven, this repository ships the fully tested host, clients and QA stack the recorder will plug into.

## The loop — four steps, no hidden fifth

1. **Capture offline.** Hold to record, release to stop. The recording hits durable storage on the device before anything is called “saved” — a dead network never costs you a thought.
2. **Keep it, provably.** The host accepts an upload only when the bytes match, then returns a cryptographically verifiable receipt. “Sent” is never a guess.
3. **Make it searchable.** Transcription runs in a sealed, killable subprocess — hard timeout, memory cap, and the honesty to say *not transcribed* instead of inventing text.
4. **Make it yours.** Listen, correct, label, then export clean Markdown into your own vault — explicitly, conflict-safely, never overwriting a hand edit.

## Proof over promises

| | |
| --- | --- |
| **287 automated checks** | unit, integration, browser and app suites, green on every push |
| **9 adversarial crash tests** | killed processes, hostile uploads, forged labels, tombstone replay — the system keeps its promises anyway |
| **One live deployment** | a supervised service behind private TLS, verified end to end: pair → upload → receipt → transcript → export |
| **A clean-host rehearsal** | a scripted install that proves the documented path from this repository alone, on a throwaway machine |
| **Apache-2.0** | open source, with a full [provenance & SBOM](docs/PROVENANCE.md) inventory |

> **Honest status:** everything above is real and tested — on synthetic data, on the software stack. No real-voice corpus exists here; none will until consent and retention policy are on record (they now are). The physical recorder is in commissioning; real-hardware proof lands in the build log the day it exists.

## What’s in the box today

| Surface | State |
| --- | --- |
| **Host** | Receipt-guarded ingest, idempotent manifest-checked uploads, pair-once device auth, isolated transcription with manual retry, byte-range audio, tombstones, edit-conflict protection, deterministic export, owner metrics, fail-closed backup/restore. Deployed and live. |
| **Browser client** | The single chosen web client — full notes surface, bounded offline snapshot with honest offline states, automated accessibility checks. |
| **Phone client** | A Flutter app wired to the real API — pairing, feed, playback, trash, conflicts; debug APK built in CI. |
| **Device software** | Durable spool + uploader prototype, proven against crash and replay. Microphone, button, display and power come with the hardware lane. |
| **Hardware** | In commissioning. Not claimed until measured. |

## Meet Pip ✦

**Pip** is the face of the project: a small memory moth who carries one glowing spark at a time — the shape of the job. Pip is **not** a wake word, not an always-listening microphone, and not an agent acting on your behalf. On the device, readable recording, retention, queue and battery states outrank any animation. See the [design guide](DESIGN.md) and [brand assets](brand/README.md).

## The build log

Receipts, not roadmaps. Newest first — and the full history is in the [commit log](https://github.com/NaustudentX18/whis2ndbrain/commits/main).

- **Oct 1 — the owner decision gate passed.** Scope, host, security, retention and privacy policy decided and recorded; Apache-2.0 adopted; performance targets set for measurement. Hardware commissioning formally open.
- **Oct 1 — adversarial hardening and honest rehearsals.** Crash-boundary test matrix, offline lifecycle bounds, accessibility automation, real-model latency harness, scripted clean-host install rehearsal.
- **Sep 30 — one honest deploy.** The single-owner deployment live behind private TLS, verified end to end.
- **Sep 29 — the hardening pass.** Killable transcription, pair-once credentials, byte-range audio, deterministic export, owner metrics, fail-closed backup.
- **Sep 28 — CI live and green.** Sep 27 — the bounded host prototype published.

The public [roadmap](docs/ROADMAP.md) remains **0 of 8 evidence-gated milestones accepted** — milestones move on evidence and review, never on enthusiasm.

## The fine print, in plain sight

- All evidence to date is **synthetic test data** on the software stack; real-voice evaluation is owner-consent-gated and hasn’t happened.
- **No commissioned device yet.** Microphone, button, display, power and reboot behaviour on the Pi are unproven until the hardware lane proves them.
- **No real-phone qualification yet.** Neither the web client nor the debug APK has run on the owner’s phone.
- **Single-user by design**, private network, no multi-user or availability claims. Audio is held **168 hours** by policy; transcripts and history stay until you delete them.
- Suggestions are labelled heuristics that will misclassify; performance targets are adopted but **unmeasured until the campaign**; an independent security review is still pending.

## Explore the repository

| Where | What you’ll find |
| --- | --- |
| [Landing page](site/index.html) | The project, told properly — including the capture gesture you can try in a browser. |
| [Docs](docs/) | Product, privacy, security, deployment, model, contracts, accessibility, provenance & SBOM. |
| [Server](server/) · [Device](device/) · [Contracts](contracts/) | The host, the spool, and the shared data contracts. |
| [App](app/) | The Flutter client. |
| [Tests](tests/) · [Check script](scripts/check.sh) | The evidence behind every claim above. |

Quick local check: **bash scripts/check.sh** (syntax, unit and integration). The clean-host rehearsal (**scripts/clean_host_rehearsal.sh**) proves the full documented install on a throwaway directory. Do not point experimental export at a live vault, and never add real recordings, transcripts, credentials or model weights to Git.

---

<div align="center"><p><strong>For the thought you almost forgot.</strong></p><sub>Made carefully, one honest state at a time.</sub></div>
