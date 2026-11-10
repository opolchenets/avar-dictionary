"""Validate uploads without trusting filenames or client supplied MIME types."""
import io
import json
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from django.conf import settings

MAX_BYTES = 10 * 1024 * 1024


def validate_audio(upload, claimed_duration):
    if not upload or not 2000 <= upload.size <= MAX_BYTES:
        raise ValueError("Запись должна занимать от 2 КБ до 10 МБ.")
    content = upload.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("Запись больше 10 МБ.")
    if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        ext = "wav"
    elif content.startswith(b"\x1a\x45\xdf\xa3"):
        ext = "webm"
    elif content.startswith(b"OggS"):
        ext = "ogg"
    elif content[4:8] == b"ftyp":
        ext = "m4a"
    else:
        raise ValueError("Файл не похож на поддерживаемую аудиозапись.")
    decoder = shutil.which("ffmpeg")
    if decoder:
        # Decode at most 32 seconds into mono 8 kHz PCM. Count actual decoded
        # samples; browser WebM may not contain a duration in its container.
        with tempfile.TemporaryDirectory(prefix="avar-audio-") as temp:
            path = Path(temp) / ("upload." + ext)
            path.write_bytes(content)
            try:
                result = subprocess.run(
                    [decoder, "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                     "-i", str(path), "-t", "32", "-vn", "-ac", "1", "-ar", "8000",
                     "-f", "s16le", "pipe:1"], capture_output=True, timeout=15, check=True)
                duration = len(result.stdout) / 16000
            except (subprocess.SubprocessError, OSError) as exc:
                raise ValueError("Не удалось прочитать аудиозапись.") from exc
    elif ext == "wav":
        try:
            with wave.open(io.BytesIO(content)) as audio:
                duration = audio.getnframes() / audio.getframerate()
                if len(audio.readframes(audio.getnframes())) != audio.getnframes() * audio.getnchannels() * audio.getsampwidth():
                    raise ValueError("Повреждённая WAV-запись.")
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise ValueError("Не удалось прочитать WAV-запись.") from exc
    else:
        if getattr(settings, "AUDIO_REQUIRE_DECODER", False):
            raise ValueError("Проверка аудио временно недоступна. Попробуйте позже.")
        try:
            duration = float(claimed_duration)
        except (ValueError, TypeError) as exc:
            raise ValueError("Некорректная длительность записи.") from exc
    if not math.isfinite(duration) or not 0.1 <= duration <= 31:
        raise ValueError("Запишите от 0,1 до 30 секунд речи.")
    return content, duration, ext
