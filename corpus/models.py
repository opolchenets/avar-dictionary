from django.conf import settings
from django.db import models


class Sentence(models.Model):
    class Status(models.TextChoices):
        UNTRANSLATED = "untranslated", "Не переведено"
        PENDING = "pending", "На проверке"
        TRANSLATED = "translated", "Переведено"

    source_text_ru = models.TextField("Русский текст", unique=True)
    text_av = models.TextField("Аварский перевод", blank=True, default="")
    translated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="translated_sentences",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.UNTRANSLATED,
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "Предложение"
        verbose_name_plural = "Предложения"

    def __str__(self) -> str:
        return self.source_text_ru[:80]
