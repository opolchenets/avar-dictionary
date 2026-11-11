from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from asr_demo.models import AsrTrial


class Command(BaseCommand):
    help = "Удалить все сохранённые аудио демо и метаданные старше 24 часов"

    def handle(self, *args, **options):
        # Audio is no longer retained, including files left by the previous version.
        for trial in AsrTrial.objects.exclude(audio="").iterator():
            trial.audio.delete(save=True)
        root = Path(settings.ASR_TRIAL_ROOT).resolve()
        directory = root / "asr_trials"
        if directory.exists() and not directory.is_symlink():
            for path in directory.rglob("*"):
                if path.is_file() and not path.is_symlink() and root in path.resolve().parents:
                    path.unlink()
        cutoff = timezone.now() - timedelta(hours=24)
        trials = AsrTrial.objects.filter(created_at__lt=cutoff)
        count = 0
        for trial in trials.iterator():
            if trial.audio:
                trial.audio.delete(save=False)
            trial.delete()
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Удалено испытаний модели: {count}"))
