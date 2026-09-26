<div align="center">
  <img src="brand/wordmark.svg" alt="Whis2ndBrain — Catch the thought. Keep the signal." width="560" />
  <br />
  <img src="brand/pip-mascot.svg" alt="Pip, a tiny glowing thoughtkeeper companion" width="190" />
  <h3>Your thoughts deserve somewhere safe to land.</h3>
  <p>A pocket-sized, local-first voice notebook in the making.<br />Press. Speak. Let the thought go. Find it when you need it.</p>
  <p><strong>🌱 EARLY BUILD · Research + project scaffolding · No working product yet</strong></p>
  <p><a href="site/index.html">Explore the launch page</a> · <a href="docs/ROADMAP.md">Follow the roadmap</a> · <a href="DESIGN.md">Read the design brief</a></p>
</div>

---

## The idea

Whis2ndBrain is an independent, owner-controlled pocket recorder and companion PWA for catching thoughts away from a keyboard. The north star is simple: capture first, organise later—with the original recording kept safe, machine suggestions kept humble, and the human always in charge.

The intended prototype pairs a **Raspberry Pi Zero 2 W**, **Whisplay** display/audio HAT and **PiSugar 3** power board with a private host for durable receipt, local transcription and optional typed triage. A mobile-friendly web companion is planned for search, listening, review and carefully scoped Markdown export to an Obsidian inbox.

> **Truth before hype:** the hardware is not commissioned and no firmware, app, API, model integration or test has been implemented. This repository currently contains the project structure, research-informed design direction and build plan—not a usable recorder. Every product capability below is a target until verified.

## The feeling

**Quietly capable. Tactile. Kind. Private by design.** A little companion named **Pip**—a luminous memory-moth—will make the future interface feel warm without pretending to be an autonomous assistant. Pip can celebrate a saved capture, keep watch over a queue, or sit quietly in the corner. The actual mascot screen states, behaviours and animations still need implementation and accessibility review.

| The promise we are designing toward | How we intend to earn it |
| --- | --- |
| **Capture without a connection** | A durable on-device queue; no cloud required to press record. |
| **Know what happened** | Clear states for recording, retained, uploaded, processing and reviewed. |
| **Keep the person in the loop** | Transcripts and categories are suggestions, never silent truth or automatic actions. |
| **Keep data in your hands** | Owner-controlled processing host; private-network-first plan; explicit, conflict-safe export. |

## A thought’s intended journey

```text
HOLD TO CAPTURE
      ↓  original audio is finalised and retained on the device
PRIVATE SYNC
      ↓  matching durable receipt; safe to retry after interruption
LOCAL PROCESSING
      ↓  transcript + optional typed suggestions, each clearly machine-made
HUMAN REVIEW
      ↓  edit, keep, retry, trash or leave uncertain for later
OBSIDIAN INBOX
         explicit opt-in Markdown export; never overwrite an owner edit
```

This is the design target, **not a live data flow**. See the [product guide](docs/PRODUCT.md) for intended scope and the [privacy guide](docs/PRIVACY.md) for the non-negotiable boundaries.

## What makes this different

- **Offline capture comes before AI.** A model or Wi-Fi outage must never make the physical capture path disappear.
- **Durable means durable.** “Saved” should only appear after a recording is safely finalised; “synced” should mean a matching, durable server receipt—not a health-check response.
- **AI can be unsure.** Preserve the source audio, separate machine transcript from edits, abstain when uncertain, and make manual triage useful on its own.
- **No surprise actions.** A suggested task is not a created task. A transcript is data—not a command to run, send, or move something.
- **Human-scale design.** One-owner, one-device and private-network-first before any multi-user or cloud ambitions.

## Project map

```text
.
├── brand/              Original wordmark, icon, palette and Pip mascot artwork
├── site/               Standalone, dependency-free pre-launch / loading page
├── docs/               Product, privacy, contributor and milestone guides
├── contracts/          Future versioned interfaces shared by device/server/web
├── device/              Future offline recorder runtime (not implemented)
├── server/              Future durable API and processing workers (not implemented)
├── web/                 Future PWA companion (not implemented)
├── tests/               Future synthetic, integration, browser and hardware tests
├── enclosure/           Future measured mechanical design (not implemented)
├── scripts/              Future safe, reviewed helpers
└── deploy/               Future private-host deployment (not implemented)
```

`site/` is a static project introduction and visual direction only. It is not the PWA, does not collect data, and does not connect to a recorder or backend.

## Follow along

The [roadmap](docs/ROADMAP.md) breaks the work into evidence-gated milestones with checkboxes, acceptance criteria and source packet IDs. Current planning is **pre-build**: hardware, host, browser and privacy decisions still need owner review. Completion boxes are not a promise or a substitute for test evidence; no milestone should be checked until its criteria are demonstrated.

Start here:

1. [Product guide](docs/PRODUCT.md) — the job, intended flow, MVP and explicit non-goals.
2. [Privacy guide](docs/PRIVACY.md) — data boundaries, safety rules and what “local-first” does and does not mean.
3. [Design brief](DESIGN.md) — brand, mascot, visual system, interaction states and accessibility targets.
4. [Roadmap](docs/ROADMAP.md) — phases, gates, dependencies and verification expectations.
5. [Contributing](CONTRIBUTING.md) — the safe route from scaffold to implementation.

The detailed requirements, research citations and canonical task board remain in the owner's private Obsidian project notes. Only public-safe summaries are reproduced here; do not add private vault exports, voice samples, recordings, secrets, model weights or personal identifiers to this repository.

## Status

| Area | Current state |
| --- | --- |
| Product & technical research | Prepared; physical hardware and target host remain unverified |
| Repository | New scaffold and public-facing project materials |
| Device, server, PWA | Not implemented |
| AI / transcription | Not integrated or evaluated on this project |
| Hardware / enclosure | Not inspected, measured or commissioned |
| Release / certification | None; no performance or battery-life claims |

<div align="center">
  <sub>Made for the thought you almost forgot. Built carefully, one verified step at a time.</sub>
</div>
