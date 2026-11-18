from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from clips.models import ClipEdit
from gamification.rejection_archive import preserve_rejections
from reading.models import Recording


class Command(BaseCommand):
    help = "Preview or remove rejected and redo submissions, preserving clips, prompts, accepted and pending work."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Delete matching submissions and unreferenced recording audio.")

    @transaction.atomic
    def handle(self, apply, **kwargs):
        edit_qs = ClipEdit.objects.filter(verdict__in=[ClipEdit.Verdict.REJECTED, ClipEdit.Verdict.REDO])
        recording_qs = Recording.objects.filter(status__in=[Recording.Status.REJECTED, Recording.Status.REDO])
        edits = edit_qs.count()
        recordings = recording_qs.count()
        seconds = recording_qs.aggregate(total=Sum("duration"))["total"] or 0
        paths = list(recording_qs.exclude(audio="").values_list("audio", flat=True).distinct())
        if not apply:
            self.stdout.write(f"PREVIEW: clip_edits={edits}; recordings={recordings}; recording_minutes={seconds / 60:.2f}; audio_files={len(paths)}; no changes")
            return

        preserve_rejections(edit_qs, recording_qs)
        deleted_edits, _ = edit_qs.delete()
        deleted_recordings, _ = recording_qs.delete()

        def remove_orphan_audio():
            for name in paths:
                if not Recording.objects.filter(audio=name).exists():
                    Recording._meta.get_field("audio").storage.delete(name)

        transaction.on_commit(remove_orphan_audio)
        self.stdout.write(self.style.SUCCESS(
            f"PURGED: clip_edits={edits}; recordings={recordings}; audio_files_checked={len(paths)}; "
            f"audio_minutes_removed={seconds / 60:.2f}; db_rows_deleted={deleted_edits + deleted_recordings}"
        ))
