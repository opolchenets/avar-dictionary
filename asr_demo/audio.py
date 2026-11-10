import shutil
import subprocess
import tempfile
from pathlib import Path


MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_PCM_BYTES = 16000 * 2 * 5


def decode_trial(upload):
    if not upload or not 1000 <= upload.size <= MAX_UPLOAD_BYTES:
        raise ValueError("Запись должна занимать от 1 КБ до 4 МБ.")
    source = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(source) > MAX_UPLOAD_BYTES:
        raise ValueError("Запись превышает 4 МБ.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Обработка аудио временно недоступна.")
    with tempfile.TemporaryDirectory(prefix="avar-asr-trial-") as temp:
        source_path = Path(temp) / "recording"
        source_path.write_bytes(source)
        try:
            result = subprocess.run(
                [ffmpeg, "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                 "-i", str(source_path), "-t", "5.1", "-vn", "-ac", "1", "-ar", "16000",
                 "-f", "s16le", "pipe:1"],
                capture_output=True, timeout=12, check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("Не удалось прочитать запись. Запишите её заново.") from exc
    pcm = result.stdout
    duration = len(pcm) / (16000 * 2)
    if not 0.2 <= duration <= 5.0 or len(pcm) > MAX_PCM_BYTES:
        raise ValueError("Запишите от 0,2 до 5 секунд речи.")
    return source, pcm, duration
