from django.conf import settings
from django.db import models

from corpus.models import Sentence


class PointLedger(models.Model):
    class Reason(models.TextChoices):
        FIRST_TRANSLATION = "first_translation", "Первый перевод"
        SUGGESTION_SUBMITTED = "suggestion_submitted", "Предложена правка"
        SUGGESTION_ACCEPTED = "suggestion_accepted", "Правка принята"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="point_entries",
    )
    reason = models.CharField("Причина", max_length=40, choices=Reason.choices)
    points = models.IntegerField("Очки")
    sentence = models.ForeignKey(
        Sentence,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="point_entries",
    )
    suggestion = models.ForeignKey(
        "suggestions.TranslationSuggestion",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="point_entries",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Начисление очков"
        verbose_name_plural = "Начисления очков"

    def __str__(self) -> str:
        return f"{self.user} {self.points:+} ({self.reason})"
