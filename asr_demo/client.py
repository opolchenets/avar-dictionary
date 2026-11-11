import json
import urllib.error
import urllib.request

from django.conf import settings


class AsrUnavailable(Exception):
    pass


def recognize(pcm):
    if not settings.ASR_SERVICE_URL or len(settings.ASR_INTERNAL_TOKEN) < 32:
        raise AsrUnavailable("Модель пока не подключена к сайту.")
    request = urllib.request.Request(
        settings.ASR_SERVICE_URL + "/transcribe",
        data=pcm,
        method="POST",
        headers={
            "Authorization": "Bearer " + settings.ASR_INTERNAL_TOKEN,
            "Content-Type": "audio/pcm",
            "Content-Length": str(len(pcm)),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 503:
            raise AsrUnavailable("Модель занята другой записью. Повторите через несколько секунд.") from exc
        raise AsrUnavailable("Модель временно недоступна.") from exc
    except (OSError, ValueError, TimeoutError) as exc:
        raise AsrUnavailable("Модель не ответила вовремя. Попробуйте ещё раз.") from exc
    text = str(payload.get("text", "")).strip()
    version = str(payload.get("version", ""))[:100]
    if not text:
        raise AsrUnavailable("Речь не удалось распознать. Попробуйте говорить ближе к микрофону.")
    return text, version
