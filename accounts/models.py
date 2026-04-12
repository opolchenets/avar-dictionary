from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        CONTRIBUTOR = "contributor", "Переводчик"
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

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self) -> str:
        return self.display_name or self.user.username

    @property
    def is_editor(self) -> bool:
        return self.role == self.Role.EDITOR or self.user.is_staff or self.user.is_superuser
