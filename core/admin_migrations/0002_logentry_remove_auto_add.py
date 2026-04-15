from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("admin", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="logentry",
            name="action_time",
            field=models.DateTimeField(
                default=timezone.now,
                editable=False,
                verbose_name="action time",
            ),
        ),
    ]
