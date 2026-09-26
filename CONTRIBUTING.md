# Contributing safely

Whis2ndBrain is at research/scaffold stage. There is no working application yet. Contributions should make the prototype more verifiable, not make an unverified feature look complete.

## Before changing a lane

1. Read this file, root `AGENTS.md` and the closest folder `AGENTS.md`.
2. Check the current owner-approved task packet and contract revision in the project's canonical planning board. Board ownership names are suggestions until a task is explicitly assigned.
3. Confirm exact paths, prerequisites, acceptance criteria, tests, privacy constraints and stop conditions. One owner per file.
4. Read relevant product, architecture, privacy and verification guides. Requirements outrank sample code.
5. Make a small scoped change. Report blockers or cross-lane contract changes rather than silently broadening the task.

## Safety and data

- No device flashing, system/service changes, GPIO/power operations, production deployment, public exposure, real-vault export, real speech fixture, package install or model download without a later exact, authorized task and its gates.
- Never store secrets, private audio/transcripts, personal identifiers, databases, model weights, build caches or live-vault exports in Git.
- Use synthetic fixtures. Do not run an unreviewed installer as root. Preserve pending recordings and existing data.
- AI output is an untrusted suggestion. No automatic external action; unknown/low-confidence results remain reviewable.

## Evidence and review

Every completion claim needs the exact command/observation, environment and fixture, result/exit status, evidence pointer or hash, reviewer and date. Mocks, host tests, physical Pi results, model evaluation and real-phone PWA evidence are different gates.

Run the focused test first, then relevant lint/type/build/security checks. Never mark a roadmap phase complete from a passing mock alone. The private canonical board is the authoritative detailed task check-off surface; this repository roadmap is a public milestone summary.

## Change hygiene

- Keep design/assets original and preserve their source files in `brand/`.
- Keep `site/` dependency-free and clearly labelled as a static concept page, not the future app.
- Update product/design/privacy/roadmap docs when behavior or a contract changes; do not let copied examples silently outrank approved contracts.
- Coordinate schema/API changes before consumer edits. Update fixtures and migrations with approved contract changes.
- No new dependencies without explicit review.

## Current quick check

The static page requires no install or build tool. Open `site/index.html` locally and check phone-width layout, navigation targets, reduced-motion behavior and browser console. This check proves only the static concept page renders; it does not prove a PWA, API, hardware feature or privacy gate.
