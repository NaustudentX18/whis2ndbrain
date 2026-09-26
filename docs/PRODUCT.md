# Product guide

> This guide describes the prototype being planned. It does not document a working device, service, model or app.

## One sentence

Whis2ndBrain is a pocketable, push-to-talk voice notebook that aims to capture thoughts offline, make them searchable on an owner-controlled host, and let the owner review and deliberately export useful notes.

## The job

When someone has an idea away from a keyboard, help them capture it in the moment without making them operate a phone app. Later, let them find the original recording, inspect a clearly machine-generated transcript and optional typed triage, correct it, and choose where it belongs.

## Intended first-prototype shape

- **Recorder:** Raspberry Pi Zero 2 W + Whisplay display/audio HAT + PiSugar 3 battery/RTC board, exact revisions still to be inspected.
- **Capture:** one deliberate push-to-talk action; original audio is durably finalised locally; visible recording, queue and fault state.
- **Transport:** outbound authenticated HTTPS to a private host; persistent queue, retries, idempotent receipt and no upload requirement to end a recording.
- **Host:** owner-selected machine; durable files + metadata/job state; a bounded worker for speech recognition and optional classification. No inference on the 512 MB Pi is assumed.
- **Companion:** mobile-first PWA for searchable/paginated notes, authenticated playback, edits/review, device state and opt-in export.
- **Knowledge flow:** safe Markdown download first; a host-side writer may export to one owner-approved Obsidian inbox only after target permissions and conflict behavior are proven.

## Proposed capture-to-memory journey

1. Hold the physical control to start; release to stop (interaction still needs owner approval and commissioning).
2. Finalise, validate and retain the source recording before any network request.
3. Retry uploads safely; mark synced only after a durable host receipt matches capture identity and hash.
4. Process independently: keep audio if ASR/classification is unavailable or fails.
5. Present raw transcript separately from owner edits. Suggestions include category, domain, urgency and actionability, each of which may remain unknown.
6. Let the owner listen, search, correct, review, trash/restore or reprocess without silently overwriting annotations.
7. Export on explicit request to an allowlisted destination. A repeat is a no-op when identical; edited collisions become review conflicts.

## Early taxonomy proposal

Categories: Quick Thought; Project Idea; Task / Todo; Meeting Note; Knowledge / Resource.

Domains: Work; Engineering & Code; Personal & Health; Finance; Creative.

Urgency is 0–3 or unknown. Actionability is true / false / unknown. These are draft enums, not permission to route notes into private vault folders. “Actionable” does not mean a task was created or completed. Out-of-domain or low-confidence outputs stay reviewable; no classifier-triggered action.

## Product boundaries

### In the first prototype direction

- One owner, one recorder, one private host and one browser session model.
- Short offline captures and eventual retry/reconciliation.
- Local processing and human review.
- Explicit Markdown export with provenance and collision safety.
- Synthetic mocks before hardware/model/browser gates.

### Explicitly deferred

Wake word/always-on listening; cloud or multi-user service; public inbound access; automatic calendar/email/webhook/external actions; automatic life-domain vault routing; guaranteed zero transcription errors; production certification; custom PCB; thin-device/battery comparisons; real-time streaming ASR; desktop/Tauri wrapper unless the PWA proves insufficient.

## System seams (proposed, not frozen)

```text
Recorder + durable spool → authenticated ingest → durable host storage + job queue
                                               ├→ ASR worker
                                               ├→ bounded suggestion adapter
                                               └→ notes / telemetry API → PWA review
                                                                    └→ opt-in safe Markdown export
```

The PWA is not a hardware controller, filesystem browser or authority for capture durability. API/schema proposals need review and versioning before implementation. See the canonical owner-held research/architecture materials; the public repo only carries this concise brief.

## Words that mean something

- **Recorded:** a recording operation completed, but durability still needs explicit confirmation.
- **Retained:** the final audio file and queue identity have been durably committed on the device.
- **Received / synced:** host confirms a durable matching receipt for the same capture ID and hash.
- **Processed:** one or more machine stages ran; it is not “correct”.
- **Reviewed:** owner explicitly accepted or edited the triage.
- **Exported:** the approved Markdown file was verified at the configured local destination; it says nothing about downstream vault sync.

Never collapse those into one green “done” badge.
