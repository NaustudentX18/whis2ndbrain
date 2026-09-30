#!/usr/bin/env python3
"""Real-model transcription latency harness (Lane C2 / WB-052 prep).

Measures p50/p95/max wall-clock latency of the production isolated
transcriber across synthetic samples of several durations, and compares the
result against budget targets from a JSON file.

Honest scope (do not weaken):
  * Samples are SYNTHETIC SILENCE. They measure pipeline + model overhead
    (process spawn, load, decode of silence), not real-speech latency and
    not transcription quality. A real-voice corpus waits on consent (WB-004).
  * Budgets are PLACEHOLDERS until the BP2 owner session fixes real ones;
    comparison is report-only unless --enforce is passed.
  * Requires already-local model weights (like scripts/smoke_model.py);
    weights are never downloaded here.

Usage:
    .venv/bin/python scripts/latency_harness.py                 # defaults
    .venv/bin/python scripts/latency_harness.py --durations 1,30 --samples 10
    .venv/bin/python scripts/latency_harness.py --json out.json --enforce
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from server.pass1 import MODEL_ID
from server.pipeline.transcriber import (
    IsolatedTranscriber,
    TranscriberTimeout,
    TranscriberUnavailable,
)

DEFAULT_BUDGETS = REPO / "scripts" / "latency_budgets.json"
SAMPLE_RATE_HZ = 16000


def synthetic_wav(path: Path, seconds: float) -> Path:
    """Write deterministic silence of ``seconds`` to ``path``."""
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE_HZ)
        audio.writeframes(b"\x00\x00" * int(seconds * SAMPLE_RATE_HZ))
    return path


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (matches statistics.quantiles)."""
    if not values:
        raise ValueError("values must be non-empty")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


def summarise(seconds: list[float]) -> dict:
    return {
        "n": len(seconds),
        "min_s": round(min(seconds), 3),
        "p50_s": round(percentile(seconds, 50), 3),
        "p95_s": round(percentile(seconds, 95), 3),
        "max_s": round(max(seconds), 3),
        "mean_s": round(statistics.fmean(seconds), 3),
    }


def budget_verdict(stats: dict, budgets: dict, duration_s: int) -> tuple[str, float | None]:
    """Compare a duration's p95 against its budget key.

    Returns (verdict, budget): verdict in {"within", "exceeded", "no-budget"}.
    Placeholder budgets never count as failures.
    """
    key = f"transcribe_p95_s_for_{duration_s}s_audio"
    budget = budgets.get(key)
    if budget is None:
        return "no-budget", None
    if budgets.get("status") == "placeholder-until-BP2":
        return "within (placeholder)", budget
    return ("within", budget) if stats["p95_s"] <= budget else ("exceeded", budget)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--durations", default="1,5,15,30",
                        help="comma-separated synthetic sample durations in seconds")
    parser.add_argument("--samples", type=int, default=5,
                        help="samples per duration (sample size per row)")
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS)
    parser.add_argument("--json", type=Path, default=None, help="also write results as JSON")
    parser.add_argument("--enforce", action="store_true",
                        help="exit 1 when a non-placeholder budget is exceeded")
    args = parser.parse_args()

    durations = [int(d) for d in args.durations.split(",") if d.strip()]
    if not durations or args.samples < 1:
        parser.error("need at least one duration and samples >= 1")

    try:
        budgets = json.loads(args.budgets.read_text())
    except FileNotFoundError:
        budgets = {}

    transcriber = IsolatedTranscriber()
    results: dict[int, dict] = {}
    failures = 0
    with tempfile.TemporaryDirectory(prefix="whis-latency-") as temp:
        for duration in durations:
            timings: list[float] = []
            errors: list[str] = []
            for i in range(args.samples):
                path = synthetic_wav(Path(temp) / f"s{duration}_{i}.wav", duration)
                started = time.monotonic()
                try:
                    transcriber(path)
                except TranscriberTimeout:
                    errors.append("timeout")
                except TranscriberUnavailable:
                    errors.append("model-missing")
                except RuntimeError as exc:
                    errors.append(str(exc)[:80])
                timings.append(time.monotonic() - started)
            stats = summarise(timings)
            verdict, budget = budget_verdict(stats, budgets, duration)
            results[duration] = {**stats, "verdict": verdict, "budget_p95_s": budget,
                                 "errors": errors}
            if verdict == "exceeded":
                failures += 1
            print(f"{duration:>3}s audio | n={stats['n']} "
                  f"p50={stats['p50_s']:>7.2f}s p95={stats['p95_s']:>7.2f}s "
                  f"max={stats['max_s']:>7.2f}s | budget={budget} -> {verdict}"
                  + (f" | errors={errors}" if errors else ""))

    print(f"model={MODEL_ID}")
    print(f"host={platform.node()} python={platform.python_version()} "
          f"machine={platform.machine()}")
    print(f"budgets={args.budgets} status={budgets.get('status', 'none')}")

    if args.json is not None:
        args.json.write_text(json.dumps({
            "model": MODEL_ID,
            "host": platform.node(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "budgets_status": budgets.get("status", "none"),
            "results": results,
        }, indent=2))
        print(f"wrote {args.json}")

    if failures and args.enforce:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
