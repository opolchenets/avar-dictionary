import shutil
from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def production_requirements(app_configs, **kwargs):
    errors = []
    if not settings.DEBUG:
        if len(settings.SECRET_KEY) < 50 or settings.SECRET_KEY.startswith("django-insecure-") or "REPLACE" in settings.SECRET_KEY or settings.SECRET_KEY == "change-me":
            errors.append(Error("Set a random DJANGO_SECRET_KEY of at least 50 characters.", id="core.E001"))
        if not settings.ALLOWED_HOSTS or "*" in settings.ALLOWED_HOSTS:
            errors.append(Error("Set explicit DJANGO_ALLOWED_HOSTS.", id="core.E002"))
        if not settings.AUDIO_REQUIRE_DECODER or not shutil.which("ffmpeg"):
            errors.append(Error("Production audio uploads require AUDIO_REQUIRE_DECODER=True and ffmpeg.", id="core.E003"))
    return errors
