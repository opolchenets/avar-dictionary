from django.conf import settings
from django.db import models

from corpus.models import Sentence


class Achievement(models.Model):
    name = models.CharField("Название", max_length=100)
    threshold = models.IntegerField("Порог (кол-во переводов)")
    icon = models.CharField("Иконка/Эмодзи", max_length=10, blank=True)

    class Meta:
        verbose_name = "Достижение"
        verbose_name_plural = "Достижения"
        ordering = ("threshold",)

    def __str__(self) -> str:
        return f"{self.icon} {self.name} ({self.threshold})"


class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
    )
    earned_at = models.DateTimeField("Дата получения", auto_now_add=True)

    class Meta:
        verbose_name = "Достижение пользователя"
        verbose_name_plural = "Достижения пользователей"
        unique_together = ("user", "achievement")

    def __str__(self) -> str:
        return f"{self.user} - {self.achievement}"


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
