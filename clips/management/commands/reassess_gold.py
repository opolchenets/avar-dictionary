from django.core.management.base import BaseCommand
from clips.models import Clip
from clips.services import reassess_gold_clip
from common.normalizer import char_errors


class Command(BaseCommand):
    help = "Preview/recompute advisory control scores only; never change verdicts."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, apply, **kwargs):
        clips = Clip.objects.filter(is_gold=True, edits__isnull=False).distinct()
        edits = verdict_changes = metric_changes = manual = 0
        for clip in clips.iterator():
            for edit in clip.edits.all():
                edits += 1
                metric_changes += edit.errors != char_errors(edit.text, clip.gold_text)
                if edit.reviewed_by_id is not None:
                    manual += 1
            if apply:
                reassess_gold_clip(clip)
        self.stdout.write(f"{'APPLIED' if apply else 'PREVIEW (no changes)'}: edits={edits}, verdict_changes={verdict_changes}, error_count_changes={metric_changes}, manual_verdicts_preserved={manual}")
