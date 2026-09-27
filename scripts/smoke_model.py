"""Transcribe one public English sample with already-local model weights.

The sample may be downloaded; model weights are never downloaded by this script.
This is not a quality evaluation. It proves the local checkpoint loads on this host.
"""

import urllib.request
from pathlib import Path

from server.pass1 import MODEL_ID, load_runner

SAMPLE = "https://cdn-media.huggingface.co/speech_samples/sample1.flac"
DEST = Path("/data/models/whis2ndbrain/smoke/sample1.flac")


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if not DEST.exists():
        urllib.request.urlretrieve(SAMPLE, DEST)
    runner = load_runner()
    text = runner(DEST)
    print(f"model={MODEL_ID}")
    print(f"sample={DEST}")
    print(f"transcript={text}")
    if "slushy" not in text.lower():
        raise SystemExit("model ran but did not return the expected sample word")


if __name__ == "__main__":
    main()
