"""Local-only loading of a checksummed ASR release. No training or downloads."""
import hashlib
import json
import re
from pathlib import Path

SAMPLE_RATE = 16000
MAX_PCM_BYTES = SAMPLE_RATE * 2 * 10


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_bundle(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or manifest.get("language") != "ava":
        raise ValueError("Unsupported model bundle")
    files = manifest.get("files", {})
    required = {"model/config.json", "model/model.safetensors", "model/preprocessor_config.json",
                "model/tokenizer_config.json", "model/vocab.json", "avar_4gram.bin", "unigrams.txt"}
    if not required.issubset(files):
        raise ValueError("Incomplete model bundle")
    for name, expected in files.items():
        path = (root / name).resolve()
        if root not in path.parents or not path.is_file() or sha256(path) != expected:
            raise ValueError("Missing or corrupt model file: " + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(files) | {"manifest.json"}:
        raise ValueError("Unexpected files in model bundle")
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        raise ValueError("Model version is missing")
    return manifest


def validate_pcm(pcm):
    if not isinstance(pcm, bytes) or len(pcm) % 2 or not 3200 <= len(pcm) <= MAX_PCM_BYTES:
        raise ValueError("Audio must be 0.1–10 seconds of mono PCM16 at 16000 Hz")


class Recognizer:
    def __init__(self, directory):
        self.manifest = verify_bundle(directory)
        root = Path(directory)
        import numpy as np
        import torch
        from transformers import AutoProcessor, Wav2Vec2ForCTC
        from pyctcdecode import build_ctcdecoder
        torch.set_num_threads(2)
        self.np, self.torch = np, torch
        # The exporter merged the trained adapter into these local weights.
        # Do not request load_adapter or download anything at service startup.
        self.processor = AutoProcessor.from_pretrained(root / "model", target_lang="ava",
                                                       local_files_only=True, trust_remote_code=False)
        self.model = Wav2Vec2ForCTC.from_pretrained(root / "model", local_files_only=True,
                         use_safetensors=True, trust_remote_code=False).eval()
        vocab = self.processor.tokenizer.get_vocab()
        if vocab != self.manifest["vocab"]:
            raise ValueError("Model vocabulary differs from export")
        self.palochka = self.manifest.get("palochka")
        labels = ["" if t == self.processor.tokenizer.pad_token else
                  " " if t == self.processor.tokenizer.word_delimiter_token else t
                  for t, _ in sorted(vocab.items(), key=lambda pair: pair[1])]
        self.decoder = build_ctcdecoder(labels, kenlm_model_path=str(root / "avar_4gram.bin"),
            unigrams=(root / "unigrams.txt").read_text(encoding="utf-8").splitlines(),
            alpha=float(self.manifest["alpha"]), beta=float(self.manifest["beta"]))

    def transcribe(self, pcm):
        validate_pcm(pcm)
        wav = self.np.frombuffer(pcm, dtype="<i2").astype(self.np.float32) / 32768.0
        inputs = self.processor.feature_extractor(wav, sampling_rate=SAMPLE_RATE, return_tensors="pt",
                                                 return_attention_mask=True)
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits[0].float().cpu().numpy()
        text = self.decoder.decode(logits, beam_width=64)
        if self.palochka:
            text = text.replace(self.palochka, "Ӏ")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:1].upper() + text[1:]
