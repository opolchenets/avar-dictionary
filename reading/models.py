from django.conf import settings
from django.db import models


class Prompt(models.Model):
    """Фраза из книги без озвучки, которую предлагают прочитать."""
    text = models.TextField("Текст")
    source = models.CharField("Источник (книга)", max_length=255, blank=True)
    is_active = models.BooleanField("Выдавать участникам", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Фраза для чтения"
        verbose_name_plural = "Фразы для чтения"
        ordering = ("id",)

    def __str__(self):
        return f"#{self.id} {self.text[:50]}"


class Recording(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ждёт проверки"
        ACCEPTED = "accepted", "Принята"
        REDO = "redo", "Нужно переозвучить"
        REJECTED = "rejected", "Отклонена"

    prompt = models.ForeignKey(Prompt, on_delete=models.PROTECT, related_name="recordings", verbose_name="Фраза")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recordings")
    audio = models.FileField("Аудио", upload_to="recordings/")
    duration = models.FloatField("Длительность, с", default=0)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.PENDING)
    note = models.CharField("Комментарий проверяющего", max_length=255, blank=True)
    attempts = models.PositiveSmallIntegerField("Попыток", default=1)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="recording_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField("Записано", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Озвучка"
        verbose_name_plural = "Озвучки"
        unique_together = ("prompt", "user")
        ordering = ("-updated_at",)


class Consent(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reading_consent")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Согласие на использование голоса"
        verbose_name_plural = "Согласия на использование голоса"
