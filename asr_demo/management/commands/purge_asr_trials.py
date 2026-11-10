from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from asr_demo.models import AsrTrial


class Command(BaseCommand):
    help = "Удалить тестовые записи модели старше заданного срока"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=settings.ASR_TRIAL_RETENTION_HOURS)
        trials = AsrTrial.objects.filter(created_at__lt=cutoff)
        count = 0
        for trial in trials.iterator():
            if trial.audio:
                trial.audio.delete(save=False)
            trial.delete()
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Удалено испытаний модели: {count}"))
