import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models


def trial_upload_path(instance, filename):
    return f"asr_trials/{instance.user_id}/{instance.public_id}.audio"


def trial_storage():
    return FileSystemStorage(location=settings.ASR_TRIAL_ROOT)


class AsrTrial(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Обрабатывается"
        READY = "ready", "Готово"
        FAILED = "failed", "Ошибка"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="asr_trials")
    audio = models.FileField(upload_to=trial_upload_path, storage=trial_storage, blank=True)
    duration = models.FloatField(default=0)
    result_text = models.TextField(blank=True)
    model_version = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "created_at"))]

    def __str__(self):
        return f"{self.user} — {self.created_at:%Y-%m-%d %H:%M}"
