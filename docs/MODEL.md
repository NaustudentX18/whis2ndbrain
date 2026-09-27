# Pass-1 speech model

- **Pinned checkpoint:** `Systran/faster-distil-whisper-medium.en`
- **Runtime:** faster-whisper 1.2.1, CPU int8
- **Language:** English only
- **License:** MIT

This is the CTranslate2 build of [distil-whisper/distil-medium.en](https://huggingface.co/distil-whisper/distil-medium.en). The model card recommends it over `distil-small.en` for most applications: 394M parameters, better published WER, and a higher relative speed than that smaller distill. Short-form WER on the card is 11.1, long-form 12.8. That is not large-v3 accuracy. Human review stays mandatory.

`whisper.cpp` is not the pass-1 runtime. Its own model notes say distilled checkpoints do not yet use chunked long-form transcription, and a hold in this project can run until the battery or the card stops. faster-whisper chunks. The same English model family can move to the later S25 APK; this pass does not claim that phone run.

Weights live outside git, under `/data/models/whis2ndbrain` on the sleeper. Do not commit them.
