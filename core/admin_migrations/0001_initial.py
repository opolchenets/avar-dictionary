import django.contrib.admin.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="LogEntry",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action_time",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="action time",
                    ),
                ),
                (
                    "object_id",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="object id",
                    ),
                ),
                (
                    "object_repr",
                    models.CharField(max_length=200, verbose_name="object repr"),
                ),
                (
                    "action_flag",
                    models.PositiveSmallIntegerField(verbose_name="action flag"),
                ),
                (
                    "change_message",
                    models.TextField(blank=True, verbose_name="change message"),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="contenttypes.contenttype",
                        verbose_name="content type",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "ordering": ["-action_time"],
                "db_table": "django_admin_log",
                "verbose_name": "log entry",
                "verbose_name_plural": "log entries",
            },
            managers=[
                ("objects", django.contrib.admin.models.LogEntryManager()),
            ],
        ),
    ]
