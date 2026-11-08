import difflib
import re

from django.conf import settings
from django.db import models

PAL = "Ӏ"  # Ӏ — единая палочка


def normalize(text: str) -> str:
    """Для сравнения правок: палочка → Ӏ, без регистра, пунктуации и лишних пробелов."""
    t = re.sub(r"(?<=[А-Яа-яЁё])[IlІіӀӏ1|]", PAL, text or "")
    t = t.lower().replace("ё", "е").replace(PAL.lower(), PAL)
    t = re.sub(r"[^\w\sӀ-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


class Batch(models.Model):
    name = models.CharField("Название", max_length=150)
    source = models.CharField("Источник (книга, диктор)", max_length=255, blank=True)
    is_open = models.BooleanField("Открыта для правки", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Пачка фрагментов"
        verbose_name_plural = "Пачки фрагментов"
        ordering = ("-created_at",)

    def __str__(self):
        return self.name


class Clip(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Ждёт правок"
        AGREED = "agreed", "Готово (совпало)"
        DISPUTED = "disputed", "Спор — у редактора"
        RESOLVED = "resolved", "Готово (редактор)"

    REQUIRED_EDITS = 2

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="clips", verbose_name="Пачка")
    audio = models.FileField("Аудио", upload_to="clips/")
    duration = models.FloatField("Длительность, с", default=0)
    draft_text = models.TextField("Черновик (ASR)", blank=True)
    final_text = models.TextField("Итоговый текст", blank=True)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.OPEN)
    is_gold = models.BooleanField("Контрольный", default=False)
    gold_text = models.TextField("Эталон (для контрольных)", blank=True)
    source_ref = models.CharField("Откуда (файл/блок)", max_length=255, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Фрагмент"
        verbose_name_plural = "Фрагменты"
        ordering = ("id",)

    def __str__(self):
        return f"#{self.id} {self.draft_text[:40]}"

    @property
    def is_done(self):
        return self.status in (self.Status.AGREED, self.Status.RESOLVED)


class ClipEdit(models.Model):
    clip = models.ForeignKey(Clip, on_delete=models.CASCADE, related_name="edits", verbose_name="Фрагмент")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clip_edits")
    text = models.TextField("Текст правщика")
    gold_score = models.FloatField("Совпадение с эталоном", null=True, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Правка фрагмента"
        verbose_name_plural = "Правки фрагментов"
        unique_together = ("clip", "user")
        ordering = ("created_at",)
