from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("clips", "0004_audio_problem")]
    operations = [migrations.AddField(model_name="clipedit", name="auto_accepted",
                                    field=models.BooleanField(default=False, verbose_name="Принято по трём совпадениям"))]
