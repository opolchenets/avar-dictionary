import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from clips.models import Clip
from reading.models import Recording
from common.normalizer import fix_palochka


class Command(BaseCommand):
    help = "Export accepted corpus metadata; audio paths are relative to media/."

    def add_arguments(self, parser):
        parser.add_argument("directory")

    def handle(self, directory, **kwargs):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "transcriptions.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "audio", "text", "seconds", "source", "kind"])
            for clip in Clip.objects.filter(is_gold=False, status__in=["agreed", "resolved"]).select_related("batch").iterator():
                writer.writerow([clip.pk, clip.audio.name, fix_palochka(clip.final_text), clip.duration, clip.batch.source, "transcription"])
            for clip in Clip.objects.filter(is_gold=True).exclude(gold_text="").select_related("batch").iterator():
                writer.writerow([clip.pk, clip.audio.name, fix_palochka(clip.gold_text), clip.duration, clip.batch.source, "reference"])
        with (directory / "recordings.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "audio", "text", "seconds", "source", "speaker_id"])
            for rec in Recording.objects.filter(status="accepted").select_related("prompt").iterator():
                writer.writerow([rec.pk, rec.audio.name, fix_palochka(rec.prompt.text), rec.duration, rec.prompt.source, rec.user_id])
        self.stdout.write(self.style.SUCCESS(str(directory)))
