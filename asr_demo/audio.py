import shutil
import subprocess
import tempfile
from pathlib import Path


MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PCM_BYTES = 16000 * 2 * 10


def decode_trial(upload, *, recording=False):
    max_seconds = 5 if recording else 10
    if not upload or not 1000 <= upload.size <= MAX_UPLOAD_BYTES:
        raise ValueError("Аудиофайл должен занимать от 1 КБ до 15 МБ.")
    source = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(source) > MAX_UPLOAD_BYTES:
        raise ValueError("Файл превышает 15 МБ.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Обработка аудио временно недоступна.")
    with tempfile.TemporaryDirectory(prefix="avar-asr-trial-") as temp:
        source_path = Path(temp) / "recording"
        source_path.write_bytes(source)
        try:
            result = subprocess.run(
                [ffmpeg, "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                 "-i", str(source_path), "-t", str(max_seconds + 0.1), "-vn", "-ac", "1", "-ar", "16000",
                 "-f", "s16le", "pipe:1"],
                capture_output=True, timeout=12, check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("Не удалось прочитать аудио. Попробуйте WAV, MP3, M4A, OGG, FLAC или WebM.") from exc
    pcm = result.stdout
    duration = len(pcm) / (16000 * 2)
    if not 0.2 <= duration <= max_seconds or len(pcm) > MAX_PCM_BYTES:
        raise ValueError(f"Длительность аудио должна быть от 0,2 до {max_seconds} секунд.")
    return pcm, duration
