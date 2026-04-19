from django.conf import settings
from django.db import models

from corpus.models import Sentence


class TranslationSuggestion(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        ACCEPTED = "accepted", "Принято"
        REJECTED = "rejected", "Отклонено"

    sentence = models.ForeignKey(
        Sentence,
        on_delete=models.CASCADE,
        related_name="suggestions",
    )
    # Текст, который может редактировать редактор
    proposed_text_av = models.TextField("Предлагаемый перевод")
    # Исходный текст от пользователя (для расчета рейтинга)
    original_text_av = models.TextField("Исходный текст пользователя", blank=True)
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="translation_suggestions",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Оценка схожести (от 0 до 1)
    similarity_score = models.FloatField("Индекс точности", null=True, blank=True)
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_translation_suggestions",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField("Проверено", null=True, blank=True)
    editor_note = models.TextField("Комментарий редактора", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Предложенная правка"
        verbose_name_plural = "Предложенные правки"

    def __str__(self) -> str:
        return f"{self.sentence_id}: {self.proposed_text_av[:80]}"


class SuggestionVote(models.Model):
    suggestion = models.ForeignKey(
        TranslationSuggestion,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suggestion_votes",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Голос за правку"
        verbose_name_plural = "Голоса за правки"
        constraints = [
            models.UniqueConstraint(
                fields=("suggestion", "user"),
                name="unique_vote_per_user_per_suggestion",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} -> {self.suggestion_id}"
