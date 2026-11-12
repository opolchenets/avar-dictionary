from django.conf import settings
from django.db import models

from common.normalizer import char_errors, normalize, similarity  # noqa: F401 (реэкспорт для clips.services)


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
        AGREED = "agreed", "Совпали — ждёт редактора"
        DISPUTED = "disputed", "Спор — у редактора"
        RESOLVED = "resolved", "Готово (редактор)"

    REQUIRED_EDITS = 3

    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="clips", verbose_name="Пачка")
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
        return self.status == self.Status.RESOLVED


def texts_match(a: str, b: str) -> bool:
    """Тот же порог, что для проверочных: от 30 знаков — расхождение не больше 1 символа, короче — ни одного."""
    errs = char_errors(a, b)
    n = max(len(normalize(a)), len(normalize(b)))
    return errs <= 1 if n >= 30 else errs == 0


def gold_is_correct(text: str, gold: str) -> bool:
    """≥ 30 символов: верно, если ошибок ≤ 1. Короче 30: верно только без ошибок."""
    errs = char_errors(text, gold)
    return errs <= 1 if len(normalize(gold)) >= 30 else errs == 0


class ClipEdit(models.Model):
    class Verdict(models.TextChoices):
        PENDING = "pending", "Ждёт оценки"
        REDO = "redo", "Нужно исправить"
        ACCEPTED = "accepted", "Принята"
        REJECTED = "rejected", "Отклонена"

    clip = models.ForeignKey(Clip, on_delete=models.PROTECT, related_name="edits", verbose_name="Фрагмент")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="clip_edits")
    text = models.TextField("Текст правщика")
    gold_score = models.FloatField("Совпадение с эталоном", null=True, blank=True)
    errors = models.IntegerField("Ошибок (символов) относительно эталона", null=True, blank=True)
    verdict = models.CharField("Оценка", max_length=10, choices=Verdict.choices, default=Verdict.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="clip_reviews", verbose_name="Оценил")
    reviewed_at = models.DateTimeField("Оценено", null=True, blank=True)
    auto_accepted = models.BooleanField("Принято по трём совпадениям", default=False)
    reviewer_note = models.CharField("Что исправить", max_length=1000, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    @property
    def is_reviewed(self):
        return (self.reviewed_by_id is not None or self.auto_accepted) and self.verdict in (self.Verdict.ACCEPTED, self.Verdict.REJECTED)

    class Meta:
        verbose_name = "Правка фрагмента"
        verbose_name_plural = "Правки фрагментов"
        unique_together = ("clip", "user")
        ordering = ("created_at",)


class AudioIssue(models.Model):
    class Reason(models.TextChoices):
        HESITATION = "hesitation", "Оговорка или повтор"
        CUT = "cut", "Обрезано слово или фраза"
        NOISE = "noise", "Шум / речь не разобрать"
        PLAYBACK = "playback", "Аудио не воспроизводится"
        OTHER = "other", "Другая проблема"

    clip = models.ForeignKey(Clip, on_delete=models.CASCADE, related_name="audio_issues")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                             related_name="audio_issues")
    reason = models.CharField("Причина", max_length=20, choices=Reason.choices)
    note = models.CharField("Комментарий участника", max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="reviewed_audio_issues")
    reviewed_at = models.DateTimeField("Рассмотрено", null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "Проблема в аудиофрагменте"
        verbose_name_plural = "Проблемы в аудиофрагментах"
        constraints = [models.UniqueConstraint(fields=("clip", "user"), name="one_audio_issue_per_user_clip")]
