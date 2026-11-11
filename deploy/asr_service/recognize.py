"""Offline smoke test: input WAV must be PCM16, mono, 16 kHz, at most 5 seconds."""
import argparse
import json
import resource
import time
import wave

from bundle import MAX_PCM_BYTES, Recognizer, validate_pcm, verify_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dir")
    parser.add_argument("wav", nargs="?")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps({"verified": True, "version": verify_bundle(args.model_dir)["version"]}))
        return
    if not args.wav:
        parser.error("Supply a short WAV or --verify-only")
    with wave.open(args.wav) as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, 16000):
            parser.error("WAV must be mono PCM16 16000 Hz")
        pcm = stream.readframes(MAX_PCM_BYTES // 2 + 1)
        validate_pcm(pcm)
        if len(pcm) != stream.getnframes() * 2:
            parser.error("Truncated or oversized WAV")
    start = time.monotonic()
    model = Recognizer(args.model_dir)
    loaded = time.monotonic()
    text = model.transcribe(pcm)
    print(json.dumps({"text": text, "version": model.manifest["version"],
        "load_seconds": round(loaded - start, 2), "inference_seconds": round(time.monotonic() - loaded, 2),
        "max_rss_mib_linux": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
