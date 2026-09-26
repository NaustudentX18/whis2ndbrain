# Whis2ndBrain roadmap

> **Status: 0 of 8 delivery milestones accepted.** This is the public, milestone-level progress view. It does not claim any product implementation. The detailed 60-packet task board in the owner's canonical Obsidian project notes remains authoritative; an unchecked box here is not an instruction to execute work without an assigned packet.

**Guiding order:** evidence and safety → contracts → durable capture → durable host processing → human review → operations/mechanics → adversarial proof → bounded pilot and release. Do not polish the dashboard ahead of proving capture and recovery. Do not convert estimates into delivery promises.

## How to use this roadmap

- A milestone checkbox is for an entire evidence-gated phase, not for code being started or merged.
- Check it only after every exit criterion has a reviewed evidence record and the canonical task board's corresponding packets/gate are accepted.
- Keep the canonical task board as the single source of detailed WB task status. Reconcile this summary only after its phase gate has been accepted.
- Put evidence outside private voice-data paths and link safe command output/hash/reviewer/date. Never commit raw audio, transcripts, credentials, databases, model files, personal identifiers or private vault exports.
- If a hardware/model/browser gate cannot be reached, mark the scope deferred and explain why; do not treat a mock as equivalent.
- Phases are ordered but some mock-only backend/AI/web work may run in parallel after shared contracts freeze. Exact dependencies in the canonical board override this abbreviated view.

## At a glance

| Phase | Theme | Packet range | Exit gate | State |
| --- | --- | --- | --- | --- |
| 0 | Research and build baseline | WB-001–005 | G0 documentation / G1 approved baseline | In preparation; hardware uncommissioned |
| 1 | Contracts and test scaffolding | WB-006–011 | Shared interfaces + green mock/CI baseline | Not started |
| 2 | Hardware bring-up and durable capture | WB-012–019 | Reboot-safe offline capture / network replay | Not started |
| 3 | Server, ASR and typed suggestions | WB-020–032 | G2 model feasibility / G3 physical thin slice | Not started |
| 4 | PWA and human review | WB-033–040 | Accessible, honest, real-phone experience | Not started |
| 5 | Operations and measured enclosure | WB-041–047 | Restore/update safety + measured fit | Not started |
| 6 | Adversarial verification and pilot | WB-048–053 | G4 safety/reliability / G5 bounded pilot | Not started |
| 7 | Release and maintenance | WB-054–060 | G6 recoverable prototype + handoff | Not started |

---

## Phase 0 — Research and build baseline

**Purpose:** agree what the first prototype is; replace unverified prompt assumptions with evidence from the exact hardware, host, browser and privacy requirements.

**Canonical work:** WB-001 confirm MVP/interaction scope; WB-002 inventory boards and safety; WB-003 select host/browser/vault topology; WB-004 approve privacy/retention/performance budgets; WB-005 close hardware compatibility and HAT daemon ownership.

### Kickoff checklist

- [ ] Confirm one-owner/one-device MVP and deliberate push-to-talk gesture; explicitly defer always-listening, public access, cloud/multi-user, automated external actions and desktop wrapper.
- [ ] Photograph/record exact Pi, HAT, PiSugar and microSD revisions; inspect battery condition and connectors before applying power.
- [ ] Confirm hardware signal map and audio/codec facts against the actual revision and pinned vendor evidence. Never carry forward prompt GPIO/audio pin assumptions blindly.
- [ ] Determine safe OS/vendor-driver candidate path and the boundary between vendor daemon and appliance-owned hardware access.
- [ ] Identify processing host, supported phone/browser matrix, network topology and where the Obsidian vault is mounted.
- [ ] Approve consent, data retention, at-rest exposure, backup, storage and measured performance budgets before real data.
- [ ] Record unresolved risks and explicitly accepted trade-offs with owner and evidence.

### Exit evidence

- [ ] **G0:** planning links/requirements/caveats are reconciled; future workers have exact owners and boundaries.
- [ ] **G1:** WB-001–005 accepted; actual hardware inventory and safety review captured; OS/driver/host/browser candidate path is justified; unknowns remain visible.
- [ ] No device provisioning/flash unless the exact target, backup, installer and destructive-operation gates are separately approved.

**Current note:** desk research and repo scaffold exist; exact hardware is not inventoried or commissioned. G1 remains open. The research corrects several candidate pin/API assumptions, but this is not proof about the owned board.

## Phase 1 — Contracts and test scaffolding

**Purpose:** create stable seams before device, backend, AI and web lanes can diverge.

**Canonical work:** WB-006 repository/tooling; WB-007 versioned API/data/state contracts; WB-008 taxonomy/export schema; WB-009 mock fixtures; WB-010 CI/quality baseline; WB-011 TLS/pairing/credential lifecycle design.

### Build checklist

- [ ] Select repository runtime/tool versions with reproducible, reviewable lockfiles; keep dependency selection separate from research examples.
- [ ] Freeze capture identity, timestamps/clock quality, sequence, hash, encoding metadata, limits, receipt semantics, status enums and versioning.
- [ ] Define idempotency, same-ID/different-bytes conflict, retry policy, queue ownership, failure codes, unknown values and retention boundaries.
- [ ] Freeze category/domain/urgency/actionability schemas and Obsidian YAML export contract; preserve machine outputs separately from user edits.
- [ ] Create synthetic WAV/metadata fixtures and contract tests; label them mock-only.
- [ ] Add CI for formatting/lint/type/test/security baseline and clearly report skipped physical/model/browser gates.
- [ ] Define separate device and browser credentials, pairing, trusted TLS, revocation, CSRF/session, rate limits and redacted logs.

### Exit evidence

- [ ] Device, server, AI, web and QA can test against the same versioned schema and fixture package.
- [ ] Mock tests prove schema validation, idempotency/conflict and state transitions; no hardware/model claim inferred.
- [ ] CI is reproducible from documented setup and has no secret/private-data fixture.

## Phase 2 — Hardware bring-up and durable capture

**Purpose:** produce a trustworthy offline voice capture before adding dashboard or AI polish.

**Canonical work:** WB-012 approved OS/driver; WB-013 native audio; WB-014 controls/display/RGB; WB-015 PiSugar socket client; WB-016 durable spool/recovery; WB-017 recording state machine; WB-018 outbound replay/sync; WB-019 shutdown/power reserve.

### Bring-up checklist

- [ ] Provision only the reviewed, positively identified device/media; record OS/image, source hashes, exact board revision and restoration path.
- [ ] Verify native audio device/codec and encoding; don't assume card numbering, sample width or mono capability from an example.
- [ ] Validate button/display/RGB mappings and exclusive ownership against the real HAT/vendor runtime; no overlapping GPIO/audio assumptions.
- [ ] Parse the actual PiSugar model's framed socket responses; distinguish missing/invalid battery metrics from 0%; characterize safe power behavior under load.
- [ ] Write capture into a confirmed persistent data mount; close/validate/fsync/atomic-finalize before showing “saved”; reconcile partial files and journal after reboot.
- [ ] Keep a bounded retry queue with sequence, identity, hash and attempt state. Interruptions cannot duplicate notes or delete pending originals.
- [ ] Prove capture remains usable with Wi-Fi/backend/browser/model unavailable; error state must not block the physical button path.
- [ ] Confirm “synced” only after the host's durable matching receipt; health response is not receipt.
- [ ] Measure reserve/threshold/delay and prove safe shutdown; do not assume a universal 5% cutoff.

### Exit evidence

- [ ] Start with 20 controlled captures and reboot recovery; then complete expanded gesture/longer-session QA at the board-defined sample size.
- [ ] Offline captures remain readable/recoverable after power/restart fault injection; malformed/partial recordings are quarantined, not silently deleted.
- [ ] Valid audio metadata matches actual bytes; clock uncertainty, queue and power state are truthful; no GPIO conflicts.
- [ ] Physical test evidence includes device/revision, OS/driver, environment, sample count, result and reviewer. Mock evidence cannot close this phase.

## Phase 3 — Server persistence, speech and bounded decisions

**Purpose:** receive first; process later. A worker or model failure must not destroy the source capture.

**Canonical work:** WB-020 schema/files/migrations; WB-021 durable bounded ingest; WB-022 owner sessions/device auth; WB-023 persistent worker; WB-024 faster-whisper integration/benchmark; WB-025 Laya adapter/smoke; WB-026 consented labelled evaluation corpus; WB-027 quality/policy decision; WB-028 notes/search/edit/media API; WB-029 telemetry/SSE/sync requests; WB-030 safe Markdown/vault export; WB-031 backup/restore; WB-032 physical vertical slice.

### Backend and evaluation checklist

- [ ] Commit audio and metadata/job state durably before acknowledging; startup reconciles file/DB/job crash windows.
- [ ] Bound body size, duration, decode, rate, quota, path generation, worker concurrency, runtime and retries; reject bad media safely.
- [ ] Keep database/files local to the approved host; use migrations, versioned state transitions, leases and restart recovery.
- [ ] Pair/revoke device and browser independently; protect authenticated playback, media range requests, mutations, events and export.
- [ ] Process ASR asynchronously; keep immutable source audio, raw transcript, user-edited transcript and provenance distinct.
- [ ] Verify real candidate model/API/license/runtime on selected host; don't infer speed, capability, semantics or memory from model marketing.
- [ ] Build a consented, labelled held-out evaluation set under approved privacy policy; report coverage, errors and abstentions, not just schema-valid outputs.
- [ ] Treat Laya/classifier output as optional typed suggestions; unknown/out-of-domain stays review-required. Manual-only path is acceptable if model does not qualify.
- [ ] Export through an allowlisted target with YAML serialization, safe path resolution, atomic write, stable identity and edited-file conflict handling.
- [ ] Back up and restore metadata/audio/jobs/export receipts; don't claim a backup until hashes and relations reconcile.

### Gates and exit evidence

- [ ] **G2:** ASR and classifier evaluated separately with runtime/model/licence/memory/offline-load evidence; fail closed to manual review if a model is not qualified.
- [ ] **G3:** one synthetic and one physical capture travel through durable ingest, restart-safe processing, reviewable note and conflict-safe export; exact hashes/receipt IDs reconcile.
- [ ] Lost response, retry and same-ID/different-hash tests preserve one record and never replace originals.
- [ ] Export tests cover special characters/YAML, repeat export, owner edit, collision, symlink and traversal in a disposable target.

## Phase 4 — PWA and human review

**Purpose:** make the capture library calm, useful and honest on the actual supported phone/browser.

**Canonical work:** WB-033 approve responsive UX/error states; WB-034 shell/navigation; WB-035 paginated search; WB-036 authenticated playback; WB-037 review/edit/trash; WB-038 telemetry/sync UI; WB-039 bounded offline lifecycle; WB-040 export/privacy settings.

### Experience checklist

- [ ] Confirm screen/state design at WB-033 against `DESIGN.md`, actual browser matrix and contract version.
- [ ] Implement Notes / Device / Settings navigation, accessible search/filter, cursor pagination, useful empty/loading/error/review states.
- [ ] Clearly distinguish capture time, receipt time, processing time, stale telemetry, last-seen and cache snapshot age.
- [ ] Lazily allocate waveforms; use authenticated audio/range handling, explicit play, one active player and native controls as fallback.
- [ ] Preserve transcript provenance and owner edits through reprocessing; version updates, show conflict and provide recovery.
- [ ] Show sync requests as queued until the device acknowledges; never imply an offline/sleeping device executed the request.
- [ ] Bound cache; honestly explain first-load/offline/background limits; logout/clear-cache behavior is tested and not canonical storage deletion.
- [ ] Settings expose independent pairing, approved export-target ID, retention, model suggestion, cache and privacy facts.
- [ ] Keyboard, visible focus, screen reader, contrast, reduced motion, 320 px/200% zoom and touch-target checks pass.

### Exit evidence

- [ ] Supported real phone installs/reopens cached shell over trusted HTTPS; this is not established by localhost devtools.
- [ ] Mobile + desktop flows show empty, ready, needs-review, queued/offline, export, conflict, auth-expired and recovery states.
- [ ] Browser console/network/accessibility evidence is reviewed; uncached audio and unavailable service fail clearly.

## Phase 5 — Operations, recovery and mechanical prototype

**Purpose:** make a tested thin slice maintainable; only then protect it with system hardening and measured housing.

**Canonical work:** WB-041 reproducible host deployment; WB-042 redacted observability; WB-043 persistent-data/root-overlay policy; WB-044 reversible updates/recovery; WB-045 real stack/acoustic measurements; WB-046 parametric CAD/fit coupons; WB-047 printed enclosure qualification.

### Operations / mechanical checklist

- [ ] Deploy with documented pins/provenance, unprivileged service accounts, private binds, quotas and explicit dependency health.
- [ ] Redact logs: IDs, state, timings and error codes only by default; no transcript/audio/token contents.
- [ ] Prove storage-mount-before-service, free-space reserve, backup/recovery and cold startup before changing root-overlay behavior.
- [ ] Apply update transactionally with migration backup, health check and rollback; preserve capture spool across failed update.
- [ ] Measure owned stack, ports, controls, clearances, battery temperature, speaker/mic paths and wireless behavior before CAD.
- [ ] Print fit coupons before full enclosure; check board stress, cell clearance, airflow, thermal path, acoustic ports, charging/SD/USB and servicing.
- [ ] Verify overlay exception / persistent data mount / recovery maintenance path on actual assembly. No reliance on RAM-only recording or logs.

### Exit evidence

- [ ] Clean install, offline restart, update rollback, backup restore and data-mount failure behaviors have evidence.
- [ ] Mechanical revision links to measured dimensions/material/clearance test and real assembly fit. No commercial thinness/battery claims transfer.

## Phase 6 — Adversarial verification and bounded pilot

**Purpose:** find the failures the happy path hides before entrusting normal use to the prototype.

**Canonical work:** WB-048 device recovery; WB-049 backend/export adversarial; WB-050 security/privacy review; WB-051 real browser/accessibility; WB-052 end-to-end performance/storage/battery; WB-053 bounded seven-day real-use pilot.

### Adversarial checklist

- [ ] Fault-inject power loss at capture finalise, queue commit, upload, receipt, processing and export boundaries; reconcile source hash and job state.
- [ ] Exercise full/read-only/missing media, disk full, clock skew, bad mount, network loss, lost ACK, server restart, auth revoke, storage quota and model unavailable.
- [ ] Reject oversized/chunked/truncated/falsely labelled media without resource exhaustion; no public raw-file path.
- [ ] Attack export with `../`, absolute paths, symlink swap, edited collision, Unicode/YAML delimiters and interrupted writes.
- [ ] Check anonymous access, revoked device, CSRF, expired session, playback range auth, SSE reconnection and secret/transcript leakage.
- [ ] Review dependency/model/asset licences, provenance and data consent; security/privacy reviewer signs off unresolved risks.
- [ ] Measure real browser/device and selected host with sample size, p50/p95, queue/storage, failure coverage, power and battery reserve—not cherry-picked best runs.
- [ ] Run a bounded pilot only after consent, retention, backup, restore, monitor, recovery and stop conditions are accepted.

### Gates and exit evidence

- [ ] **G4:** no silent loss of accepted notes; retry/dedup/recovery correct; no unauthorized audio/export access; real phone, shutdown and restore proven.
- [ ] **G5:** at least seven calendar days of explicitly bounded use, with consent/retention/logging rules and no unresolved critical issue.
- [ ] A synthetic campaign or mocked phone is useful coverage but does not substitute for real-hardware/model/browser results.

## Phase 7 — Release, recovery and maintenance

**Purpose:** release a bounded prototype that a future owner can understand, reproduce and recover—not a polished promise without evidence.

**Canonical work:** WB-054 user/operator docs/licence inventory; WB-055 clean install/disaster recovery rehearsal; WB-056 tagged prototype release; WB-057 maintenance cadence/pilot changes; WB-058 optional desktop feasibility; WB-059 optional reference-video study; WB-060 final handoff/task reconciliation.

### Release checklist

- [ ] Publish user/operator docs, supported hardware/OS/host/browser tuple, known limitations, data lifecycle and license/provenance inventory.
- [ ] Rehearse install + backup restore on a clean approved target from documented source pins; capture checksum/reviewer evidence.
- [ ] Resolve or explicitly exclude critical/high-risk issues; no certification, guaranteed transcription accuracy, battery or latency statements without evidence.
- [ ] Tag a bounded prototype with matching source, migration/contracts, release notes and recovery path.
- [ ] Set maintenance and vulnerability review cadence; decide changes from pilot evidence, not novelty.
- [ ] Complete owner handoff and reconcile the canonical board.
- [ ] Decide optional desktop packaging and optional time-coded video study independently; deferred is a valid explicit outcome.

### Gate G6

- [ ] Evidence, limitations, source tag, clean recovery and owner handoff are reviewed; release is reproducible within the stated environment and scope.

## Critical path (high level)

```text
Scope + physical/host/privacy facts
  → contracts, test harness and identity/security design
  → device capture + persistent spool + safe replay
  → durable ingest + restart-safe worker + model qualification
  → one real vertical slice (device → durable receipt → reviewable note → safe export)
  → phone PWA and human review
  → recovery/operations + measured enclosure
  → adversarial evidence + approved pilot
  → reproducible release + maintenance handoff
```

Exact dependencies in the canonical packet board govern. Device/HAT access is serially owned; do not run two installers or GPIO owners on the same unit. Backend, AI, and web mocks can diverge only after contracts and fixtures freeze.

## Packet index (titles for traceability)

Titles below are a public navigation aid only. Packet acceptance details, exact prerequisites, owner dispatch and per-task checkboxes live in the canonical board; no duplicate task-state boxes are maintained here.

| Phase | ID | Canonical packet title |
| --- | --- | --- |
| 0 | WB-001 | Confirm MVP and interaction scope |
| 0 | WB-002 | Inventory actual hardware and safety |
| 0 | WB-003 | Select host, browser and vault topology |
| 0 | WB-004 | Approve privacy, retention and performance budgets |
| 0 | WB-005 | Close hardware compatibility and daemon ownership |
| 1 | WB-006 | Initialise source repository and reproducible tooling |
| 1 | WB-007 | Freeze versioned API, data and state contracts |
| 1 | WB-008 | Freeze taxonomy, routing and export schema |
| 1 | WB-009 | Create mock and fixture test harness |
| 1 | WB-010 | Establish CI and quality baseline |
| 1 | WB-011 | Design TLS, pairing and credential lifecycle |
| 2 | WB-012 | Provision approved Pi OS and vendor driver |
| 2 | WB-013 | Implement and qualify native audio capture |
| 2 | WB-014 | Implement button, display and RGB adapters |
| 2 | WB-015 | Implement robust PiSugar socket client |
| 2 | WB-016 | Implement durable local spool and recovery |
| 2 | WB-017 | Integrate recording state machine and gestures |
| 2 | WB-018 | Implement outbound sync and request polling |
| 2 | WB-019 | Integrate shutdown sequencing and power reserve |
| 3 | WB-020 | Implement server schema, files and migrations |
| 3 | WB-021 | Implement durable bounded ingest |
| 3 | WB-022 | Implement owner sessions and device auth |
| 3 | WB-023 | Implement persistent processing worker |
| 3 | WB-024 | Integrate and benchmark faster-whisper |
| 3 | WB-025 | Implement validated Laya adapter and smoke |
| 3 | WB-026 | Create consented labelled evaluation corpus |
| 3 | WB-027 | Evaluate ASR/routing and decide bounded policy |
| 3 | WB-028 | Implement notes, search, edits and media API |
| 3 | WB-029 | Implement telemetry, SSE and sync requests |
| 3 | WB-030 | Implement safe Markdown and vault export |
| 3 | WB-031 | Implement backup and restore tooling |
| 3 | WB-032 | Prove thin physical end-to-end slice |
| 4 | WB-033 | Approve responsive UX and error states |
| 4 | WB-034 | Build PWA shell and navigation |
| 4 | WB-035 | Build searchable paginated note feed |
| 4 | WB-036 | Build authenticated waveform playback |
| 4 | WB-037 | Build review, correction and trash flows |
| 4 | WB-038 | Build device telemetry and sync UI |
| 4 | WB-039 | Implement bounded offline PWA lifecycle |
| 4 | WB-040 | Build export and privacy settings UI |
| 5 | WB-041 | Package reproducible host deployment |
| 5 | WB-042 | Add redacted operational observability |
| 5 | WB-043 | Enable root overlay with persistent exceptions |
| 5 | WB-044 | Implement reversible update and recovery procedure |
| 5 | WB-045 | Measure real assembly and acoustic constraints |
| 5 | WB-046 | Create parametric CAD and fit coupons |
| 5 | WB-047 | Print and qualify safe enclosure |
| 6 | WB-048 | Run adversarial device recovery campaign |
| 6 | WB-049 | Run adversarial server/export campaign |
| 6 | WB-050 | Perform security and privacy review |
| 6 | WB-051 | Qualify real-browser PWA and accessibility |
| 6 | WB-052 | Measure complete performance, storage and battery |
| 6 | WB-053 | Run bounded seven-day real-use pilot |
| 7 | WB-054 | Finish user/operator docs and licence inventory |
| 7 | WB-055 | Rehearse clean install and disaster recovery |
| 7 | WB-056 | Tag and release bounded prototype |
| 7 | WB-057 | Set maintenance cadence and evaluate pilot changes |
| 7 | WB-058 | Optional desktop companion feasibility (deferred) |
| 7 | WB-059 | Optional time-coded reference-video study (deferred) |
| 7 | WB-060 | Final handoff and task reconciliation |

## Estimates are not dates

The private planning source suggests sessions per technical phase and multiple sessions plus a minimum seven-calendar-day pilot, but exact effort depends on hardware revision/driver risk, selected host, privacy choices, model quality and printer/phone access. No target delivery date has been committed.

## Reference sources and verification

See the private canonical research synthesis and source notes for pinned vendor/framework/model references and evidence limits. Read [`PRODUCT.md`](PRODUCT.md), [`PRIVACY.md`](PRIVACY.md), [`../DESIGN.md`](../DESIGN.md) and [`../CONTRIBUTING.md`](../CONTRIBUTING.md) before a future implementation task. No feature is complete because its phase appears here; require the phase-specific evidence and canonical WB acceptance.
