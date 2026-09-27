# Design

## Source of truth

- **Status:** Draft — early software prototype direction; physical device uncommissioned
- **Date:** 2026-09-26
- **Product surfaces:** static project / pre-launch page (`site/`), future Raspberry Pi recorder display, future mobile-first PWA.
- **Evidence reviewed:** the project README and scaffold; canonical mission, PWA experience, architecture/data contracts, security/privacy, research synthesis, master plan and task board in the owner's Obsidian project notes. The assets and static page in this repo are original concept work, not screenshots or evidence of an implemented product.
- The static page is a visual welcome and loading-state concept only. Do not treat it as the recorder UI or as an indication that a service is running.

## Brand

**Whis2ndBrain** helps a person catch a fleeting thought and return to it later. Brand promise: **Catch the thought. Keep the signal.**

- Personality: quietly capable, tactile, curious, calm, kind, a little magical, never cutesy at the expense of trust.
- Trust signals: show the current build stage; distinguish unknown/stale/queued/received/processed/reviewed; make original audio and machine suggestions distinct; use explicit consent and owner-confirmed actions.
- Original mark: an open memory loop with a small thought-spark, representing a thought retained without implying omniscience.
- Wordmark: the lowercase `whis` + mint `2nd` + lowercase `brain` treatment in `brand/wordmark.svg` is the project's original vector logotype. It is a bespoke rendered wordmark, not a licensed external font or a claim of a custom installable typeface. Keep the SVG as the source; do not substitute text with an unrelated font treatment.
- Mascot: **Pip**, a friendly memory moth with a cream-and-mint body, lilac wings and a held thought-spark. Pip is a visual companion, not a live assistant, wake word, listener, chatbot, or actor. The current hero concept is `brand/pip-hero.png`; the earlier editable vector exploration remains at `brand/pip-mascot.svg`. Neither is device-runtime artwork yet.
- Avoid: surveillance/sci-fi tropes, opaque “AI knows best” language, cold enterprise dashboards, fake hardware renders, borrowed commercial-product branding, alarmist privacy copy, and claims of certification, perfect accuracy, battery life or latency.

## Product goals

### Goals

1. Capture a short voice note with one deliberate physical action, even without a network.
2. Preserve the original and make interruption, queueing, receipt and recovery understandable.
3. Offer searchable, reviewable machine assistance without hiding uncertainty or overwriting a person's corrections.
4. Let the owner explicitly export a note to a safe, approved Obsidian inbox.
5. Make the future web experience feel welcoming, legible and dependable on a phone.

### Non-goals for the first prototype

Always-listening/wake-word mode, autonomous external actions, cloud/multi-user service, medical or financial decision support, public Internet exposure, a chatbot, guaranteed transcription/classification correctness, desktop wrapper, automatic movement through vault folders, and commercial-device thinness or battery targets.

### Success signals

Real hardware capture survives offline restart; identical uploads reconcile to one durable receipt; processing failure preserves source audio; people can find and correct a note on a supported phone; export is opt-in and never overwrites an owner edit; accessibility and recovery gates pass with recorded evidence. No numeric performance goal is frozen until host and privacy budgets are agreed.

## Personas and jobs

- **Primary — the owner/capturer:** has a thought while walking, working with hands, or away from a keyboard; needs capture to be quick and understandable.
- **Primary — the reviewer:** later searches, listens, corrects and decides what is useful; needs provenance and an easy way to say “not sure”.
- **Operator — the same owner:** pairs one device, maintains a private host, reviews storage/health and recovery; needs honest diagnostics without a generic remote shell.

All roles are initially one person. Do not imply team collaboration or multi-user permissions before the product model supports them.

## Information architecture

### Static project introduction

`site/index.html`: project status → the human problem → intended capture journey → trust principles → roadmap. Every proposed product flow has a “planned”, “concept” or equivalent truthful qualifier.

### Future companion PWA

Primary navigation: **Notes / Device / Settings**. Notes opens a searchable, paginated feed; note detail supports playback and review; Device separates backend reachability from device heartbeat/telemetry and queue; Settings holds session, pairing, approved export target, retention, model suggestion, cache and about information. No AI chat in MVP.

### Future recorder display

Proposed 240 × 280 px screen: connection/battery with stale/unknown state; central idle clock or recording elapsed state; bottom queue/saved/error message. `device/assets/pip-screen-concept.html` is a static layout proposal using the current Pip art, not firmware. The physical button remains authoritative even if display, browser, model or network fails.

## Design principles

1. **Truth in every state.** Unknown is not green, a health response is not sync, a suggestion is not an action, and upload receipt is not export.
2. **Capture before cleverness.** Preserve short tactile capture and durable recovery before building dashboard polish.
3. **Human review is a feature.** Machine transcript, category and urgency remain labelled, editable, provenance-aware and allowed to abstain.
4. **Privacy is visible and bounded.** Owner-controlled host, private-network-first, explicit export target; no surprising background work.
5. **Quiet warmth, low cognitive load.** Pip and the color glow add care; they never obscure status, urgency, controls or accessibility.
6. **Fail soft, recover clearly.** Errors explain what remains safe, what needs attention, and the next reversible action.

## Visual language

- **Palette:** deep evergreen-charcoal canvas `#101A1D`; layered slate/forest panels `#172427`, `#1C2A2B`; warm mist text `#F1F4E9`; muted sage copy `#ADBBB1`; mint trust/active `#BDF4D7` / `#8FDFBD`; soft lilac companion accent `#C4B6FF`. Red/amber semantic states must be added separately and never replaced with mint.
- **Typography:** editorial serif for large emotional statements paired with a neutral system sans for UI and monospaced labels for metadata. The brand wordmark is a custom vector treatment; the app uses system fallbacks until a properly licensed custom font is selected and bundled.
- **Spacing:** 4 px base; 8/12/16/24/32/48/64 px working rhythm. Keep generous page margins and dense data only inside clearly grouped cards.
- **Shape/elevation:** 12–24 px radius for soft UI cards, pill shape for compact status; subtle hairline borders; one restrained diffuse shadow. Avoid glass effects as a default interaction layer.
- **Motion:** brief transitions for meaningful state changes; Pip may gently float on the public concept page only. Honor reduced-motion; no endless attention-grabbing animation or animation that competes with recording.
- **Imagery/iconography:** project-owned SVG line/glow identity and Pip artwork; icons pair with text on important status/actions. Do not use the mascot as a state substitute or inferable status color.

## Components

No application component library exists yet. Concept surface currently contains a compact brand navigation, build-status ribbon, hero + illustration, three principle cards, staged journey list, privacy callout and roadmap panel. Future shared PWA patterns to design after WB-007/WB-033: status badge with age, paginated note card, transcript/audio player, review editor, device metric row, offline snapshot banner, sync request acknowledgement, export confirmation/conflict panel, empty/loading/error states. Component ownership/tokens should live in the chosen app framework; do not create parallel design-system layers prematurely.

## Accessibility

- Target WCAG 2.2 AA for the future web surface; verify actual color contrast (including mint, muted and semantic states) before release.
- Semantic landmarks/headings; keyboard access and visible focus; labelled icon buttons; logical reading order; text plus icon/state rather than color alone.
- Target 44 × 44 CSS px touch controls, usable 320 px view, and reflow at 200% zoom.
- Screen-reader transcript; accessible native audio fallback; no autoplay; announce save/export/error without repetitive live-region chatter.
- Honor `prefers-reduced-motion`; no recording state communicated by animation alone.
- Device screen uses high-contrast recording state, readable labels and no false “saved” state before durable finalisation.

## Responsive behavior

- **Wide desktop (> 1000 px):** editorial two-column hero; roomy content; future notes dashboard may use feed + detail/filter layout after actual information density is tested.
- **Tablet (600–1000 px):** one-column hero with illustration below; preserve tap targets and card rhythm.
- **Phone (≤ 600 px):** single-column; compact nav; stacked cards; one dominant action; keep status and short evidence visible without hover.
- **Tiny widths (320 px):** no horizontal page overflow, long transcripts/names wrap, controls remain reachable. Hover is only a supplement; all affordances must work by touch and keyboard.

## Interaction states

Design and test distinct loading, empty, ready, processing, review-required, failed/retryable, offline/stale, conflict, success and disabled states. Initial offline shell works only after a valid prior cache; no promise that the PWA records or runs continuously in the background. Uncached audio, expired auth, unavailable model, unknown telemetry and pending sync requests must explain their actual state. Never imply all pending work has completed merely because the page rendered.

## Content voice

Clear, warm, modest and specific. Prefer “suggested”, “machine transcript”, “last seen 2 min ago”, “queued for next connection”, “not sure”, and “exported to [approved target]”. Avoid “perfect”, “understands you”, “always-on”, “synced” without receipt evidence, and “task created” unless it really was created. Pip's voice (if ever added) should be short and optional, not infantilising.

## Implementation constraints

- Keep `site/` static, dependency-free and clearly separate from future PWA implementation.
- The desired PWA framework and package versions are not selected. Current product research proposes a same-origin authenticated PWA but does not authorise dependency installation.
- Respect repository privacy rules: generated/synthetic fixtures only; no audio, transcripts, credentials, real vault exports, DBs or model files in Git.
- Do not make direct browser filesystem assumptions; safe vault export requires a host-side allowlisted path and conflict detection.
- Verify the static page with local HTML checks and viewport/accessibility review. Future PWA requires real phone/browser HTTPS proof, keyboard/screen-reader checks, performance and privacy tests.

## Open questions

- [ ] Confirm intended capture gesture, double-click/short press semantics and whether the user wants any tactile review gesture; owner, affects device UI/state machine.
- [ ] Inventory actual Pi Zero, Whisplay and PiSugar revisions before choosing drivers, pins or enclosure; owner, safety-critical.
- [ ] Select processing host, phone OS/browser support matrix and where the Obsidian vault lives; owner, affects architecture/export/security.
- [ ] Approve at-rest encryption trade-off, retention, consent and storage budget before real voice data; owner, privacy-critical.
- [ ] Choose and measure display brightness, haptics/chime, mascot presence and reduced-motion behavior; owner, affects device and PWA.
- [ ] Evaluate whether a bundled display font adds value; owner, licensing/legibility/performance impact. Until selected, system fonts only.
- [ ] Decide if voice-language support beyond initial English evaluation is in the first pilot; owner, quality/evaluation impact.
