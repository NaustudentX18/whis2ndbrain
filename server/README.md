# `server`

**Purpose:** Backend owner — prototype HTTP server, persistence, auth, job state and API. A full FastAPI application is not implemented. Enforce durable receipt before ACK, bounded untrusted uploads, least privilege and restart-safe processing. Coordinate schema changes with contracts and integrator.

`pass1.py` is the first host slice: durable WAV receipt, local English transcription, and conflict-safe Markdown export. It is not the full FastAPI app, and it does not touch a Pi or the live vault.

Host run 2 records a host receipt time, holds audio for 168 hours, and refuses an export whose resolved path is inside `~/Documents/Vault`. `python -m server purge --root PATH` unlinks expired audio only. Notes and owner corrections stay. A row with no receipt time is not purged. `export` exits 2 and prints `export refused` when the destination is the vault. The default guard is specific to that home-directory path; it does not detect a bind mount or another vault location.
