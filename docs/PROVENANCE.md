# Provenance & SBOM

Software bill of materials and provenance inventory for the Whis2ndBrain prototype.
This is a point-in-time inventory (see verification stamp below), maintained as part of
release readiness; it records facts, not compliance claims. Licence information comes
from package metadata at the versions listed — always re-verify against the actual
artifacts you ship.

**Verified at:** `main` @ `afd1d75`, production venv Python 3.14.7 (Omarchy sleeper),
2026-09-30. CI runs the same suite on Python 3.12 and Flutter 3.47.5 (pins below).

## Direct Python dependencies (`requirements.txt`)

| Package | Version | Licence | Role |
| --- | --- | --- | --- |
| `cryptography` | 50.0.1 | Apache-2.0 OR BSD-3-Clause | At-rest encryption, token hashing |
| `faster-whisper` | 1.2.1 | MIT | Speech-to-text (CTranslate2) |
| `PyYAML` | 6.0.3 | MIT | Markdown frontmatter + manifest serialisation |

## Transitive Python closure (installed venv, metadata-declared licences)

| Package | Version | Licence |
| --- | --- | --- |
| `anyio` | 4.15.1 | MIT |
| `av` | 18.1.0 | BSD-3-Clause |
| `certifi` | 2026.7.22 | MPL-2.0 |
| `cffi` | 2.1.1 | MIT-0 |
| `click` | 8.5.0 | BSD-3-Clause |
| `ctranslate2` | 4.8.2 | MIT |
| `filelock` | 4.0.3 | MIT |
| `flatbuffers` | 25.12.19 | Apache 2.0 |
| `fsspec` | 2026.9.0 | BSD-3-Clause |
| `h11` | 0.16.0 | MIT |
| `hf-xet` | 1.6.0 | Apache-2.0 |
| `httpcore` | 1.0.9 | BSD-3-Clause |
| `httpx` | 0.28.1 | BSD-3-Clause |
| `huggingface_hub` | 1.33.0 | Apache-2.0 |
| `idna` | 3.20 | BSD-3-Clause |
| `numpy` | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `onnxruntime` | 1.30.0 | MIT |
| `packaging` | 26.3 | Apache-2.0 OR BSD-2-Clause |
| `protobuf` | 7.36.2 | 3-Clause BSD |
| `pycparser` | 3.0 | BSD-3-Clause |
| `tokenizers` | 0.23.2 | Apache-2.0 |
| `tqdm` | 4.70.1 | MPL-2.0 AND MIT |
| `typing_extensions` | 4.16.0 | PSF-2.0 |

The full pinned closure lives in the deployment venv; `requirements.txt` deliberately
pins only direct dependencies. See "Known gaps" for the release-tag recommendation.

## Flutter companion app (`app/`)

SDK constraint `>=3.4.0 <4.0.0`; resolved versions from `app/pubspec.lock`:

| Package | Resolved | Notes |
| --- | --- | --- |
| `http` | 1.6.0 | API client |
| `flutter_secure_storage` | 9.2.4 | Token storage |
| `just_audio` | 0.9.46 (+ `audio_session` 0.1.25) | Byte-range playback with auth headers |
| `shared_preferences` | 2.5.5 | Non-secret preferences |
| `google_sign_in` | 6.3.0 | Planned Drive integration |
| `googleapis` / `googleapis_auth` | 13.2.0 / 1.6.0 | Planned Drive integration |
| `intl` | 0.19.0 | Date formatting |
| `flutter_lints` | 4.0.0 | dev |
| `mockito` / `build_runner` | 5.8.1 / 2.16.1 | dev |

All are published on pub.dev under their respective licences (BSD-style for most
Flutter ecosystem packages; the lock file records the exact sources).

## Model

| Item | Value |
| --- | --- |
| Model | `Systran/faster-distil-whisper-medium.en` (distil-whisper family) |
| Licence | MIT (see `docs/MODEL.md`) |
| Execution | Isolated subprocess, int8 CT2 quantisation, hard timeout + memory cap |
| Distribution | Fetched via `huggingface_hub` at runtime; **no weights are committed to Git** |
| Evaluation | A public English sample smoke test only; not a personal-note quality evaluation |

## Assets

| Asset | Provenance |
| --- | --- |
| `brand/mark.svg`, `brand/wordmark.svg`, `brand/pip-mascot.svg` | Original authored vector artwork for this project |
| `brand/pip-hero.png` | Generated with OpenAI built-in image generation from an original project prompt; no external character reference supplied (details in `brand/README.md`) |
| `site/index.html` | Dependency-free static page; system font stacks; no web-font or CDN dependency |
| `device/assets/pip-screen-concept.html` | Design concept, not a running device surface |

## CI pins (`.github/workflows/ci.yml`)

| Pin | Value |
| --- | --- |
| `actions/checkout` | `@v4` |
| `actions/setup-python` | `@v5`, Python 3.12, pip cache |
| `subosito/flutter-action` | `@v2`, Flutter 3.47.5 stable, cache |
| Lint | `pip install ruff` — **unpinned** (see gaps) |

## Data & consent

No real-voice recordings, personal transcripts or credentials exist in this
repository. All test fixtures and deployment verification use synthetic audio;
real-voice evaluation is gated on the owner's consent/retention decisions.

## Known gaps (recorded, not fixed here)

1. `ruff` is installed unpinned in CI — lint results can drift between runs.
   Recommendation: pin before the v0.1.0 tag.
2. GitHub Actions use major-version tags, not commit-SHA pins.
3. No committed lock file for the Python transitive closure — `requirements.txt`
   pins direct deps only. A constraints file generated from the verified venv
   would make CI/deploy bit-reproducible.

These are inputs to the release checklist, tracked with the release lane.
