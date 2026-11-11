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
    text_snapshot = models.TextField("Текст при записи", blank=True, editable=False)

    @property
    def spoken_text(self):
        return self.text_snapshot or self.prompt.text

    def save(self, *args, **kwargs):
        if self._state.adding and not self.text_snapshot:
            self.text_snapshot = self.prompt.text
        super().save(*args, **kwargs)
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


class PromptFeedback(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ждёт проверки"
        APPLIED = "applied", "Исправлено"
        DISMISSED = "dismissed", "Рассмотрено без изменения"

    prompt = models.ForeignKey(Prompt, on_delete=models.PROTECT, related_name="feedback")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    original_text = models.TextField()
    suggested_text = models.TextField(blank=True)
    note = models.CharField(max_length=1000, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="prompt_feedback_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("prompt", "user"),
                       condition=models.Q(status="pending"), name="one_pending_prompt_feedback")]
