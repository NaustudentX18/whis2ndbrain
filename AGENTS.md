# Whis2ndBrain repository instructions

## Project state and plan authority
This is an early prototype, not a commissioned product. The repository contains a public scaffold and bounded host, software-spool, API and browser-shell prototype code. Verify the current tree and test evidence before claiming any feature, driver, model, browser or hardware gate complete. Hardware remains uncommissioned. Detailed requirements/research/risks/checklist source of truth: the owner's private canonical Obsidian project notes (entry: `overview.md`; board: `notes/swarm-task-board.md`). Read its `notes/agent-execution-contract.md` before taking a packet. Private vault notes are not part of this repository.

## Execution boundary
No device flashing, OS/service configuration, GPIO/power operations, production deployment, live-vault export, public network exposure, external webhook, real speech fixture, package install or model download is authorised by this scaffold alone. A later explicit assigned WB packet must name exact target and gates. Never request credentials in notes. Never run unreviewed install scripts as root. Preserve pending recordings and existing data; no destructive disk assumptions.

## Ownership
| Paths | Owner | Boundary |
|---|---|---|
| Root, contracts, dependency locks, cross-lane schemas | Integrator | One source of truth; coordinate breaking changes
| `device/` | Device | Offline recorder/physical peripherals only
| `server/` | Backend; AI owns only explicitly split pipeline files | Durable ingest and processing; no overwrite of owner edits
| `web/` | Web | PWA; no direct hardware or unrestricted filesystem
| `tests/` | QA | synthetic/consented fixtures; mocks do not close real gates
| `scripts/`, `deploy/` | Operations | reviewed reproducible safe procedures
| `enclosure/` | Mechanical | measurements before CAD; LiPo clearance
| `docs/`, `DESIGN.md`, `brand/`, `site/` | Integrator/design owner | public-safe summaries and original concept assets; roadmap mirrors milestones only, canonical task board remains private source of detailed status

Each subfolder has an `AGENTS.md` that narrows this policy. One agent owns a file at a time. Do not revert shared edits. Contract change requires owner approval, fixture/migration update and all consumer updates.

## Data, quality and verification
- Never commit credentials, real audio/transcripts, databases, model weights, private vault exports, build caches or personal identifiers. Use generated fixtures.
- Durable device capture and idempotent server receipt outrank UI/AI polish. No memory-only queue, silent fallback mount, implicit deletion, or health-check-as-sync claim.
- Treat speech and model output as untrusted suggestions. No automatic external actions. Unknown/low-confidence stays reviewable.
- Pin runtime/model/driver provenance and licences before calling it reproducible. Test each boundary; mock, real Pi, real model, real phone, and recovery evidence are distinct.
- Keep code changes small and in the assigned lane; run focused tests then lint/type/build and security checks for changed surfaces. Report exact evidence and remaining gaps.

## Task protocol
1. Confirm owner assignment, WB dependencies, state and contract revision from the vault.
2. Claim only bounded owned paths; post status/evidence through the leader/team contract.
3. Implement only acceptance criteria, no scope creep. Stop on data-loss, battery, privacy, certificate or ownership conflict.
4. Obtain independent review and fresh verification. The integrator reconciles the canonical Obsidian checkboxes and aggregate gates.
