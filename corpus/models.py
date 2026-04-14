from django.conf import settings
from django.db import models


class Category(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField("Слаг", max_length=100, unique=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self) -> str:
        return self.name


class Sentence(models.Model):
    class Status(models.TextChoices):
        UNTRANSLATED = "untranslated", "Не переведено"
        PENDING = "pending", "На проверке"
        TRANSLATED = "translated", "Переведено"

    source_text_ru = models.TextField("Русский текст", unique=True)
    text_av = models.TextField("Аварский перевод", blank=True, default="")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sentences",
        verbose_name="Категория",
    )
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


class Terminology(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="terms",
        verbose_name="Категория",
    )
    word_ru = models.CharField("Слово (RU)", max_length=255)
    word_av = models.CharField("Перевод (AV)", max_length=255)

    class Meta:
        verbose_name = "Термин"
        verbose_name_plural = "Терминология"
        ordering = ("word_ru",)
        unique_together = ("category", "word_ru")

    def __str__(self) -> str:
        return f"{self.word_ru} -> {self.word_av}"
