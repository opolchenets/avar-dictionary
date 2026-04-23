from django.conf import settings
from django.db import models


class Alliance(models.Model):
    name = models.CharField("Название", max_length=100, unique=True)
    color = models.CharField("Цвет", max_length=50, blank=True)
    icon = models.ImageField("Иконка", upload_to="alliances/", blank=True, null=True)

    class Meta:
        verbose_name = "Альянс"
        verbose_name_plural = "Альянсы"

    def __str__(self) -> str:
        return self.name


class District(models.Model):
    name = models.CharField("Название", max_length=150, unique=True)
    alliance = models.ForeignKey(
        Alliance,
        on_delete=models.CASCADE,
        related_name="districts",
        verbose_name="Альянс",
    )

    class Meta:
        verbose_name = "Район"
        verbose_name_plural = "Районы"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class UserProfile(models.Model):
    class Role(models.TextChoices):
        CONTRIBUTOR = "contributor", "Переводчик"
        CO_EDITOR = "co_editor", "Соредактор"
        EDITOR = "editor", "Редактор"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField("Отображаемое имя", max_length=150, blank=True)
    role = models.CharField(
        "Роль",
        max_length=20,
        choices=Role.choices,
        default=Role.CONTRIBUTOR,
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
        verbose_name="Район",
    )
    
    # Метрики качества
    average_quality_score = models.FloatField("Среднее качество", default=0.0)
    accepted_suggestions_count = models.IntegerField("Принято правок", default=0)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self) -> str:
        return self.display_name or self.user.username

    @property
    def is_editor(self) -> bool:
        return self.role == self.Role.EDITOR or self.user.is_staff or self.user.is_superuser

    @property
    def is_co_editor(self) -> bool:
        return self.role == self.Role.CO_EDITOR
    
    @property
    def quality_percentage(self) -> int:
        return int(self.average_quality_score * 100)


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    suggestion = models.ForeignKey(
        "suggestions.TranslationSuggestion",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    is_read = models.BooleanField("Прочитано", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self) -> str:
        return f"{self.user} -> {self.suggestion_id}"
