"""Remove collected audio/text payloads while retaining decisions and statistics."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from gamification.rejection_archive import preserve_rejections
from django.db.models import Sum
from django.db.models import Q

from clips.models import Batch, Clip, ClipEdit
from reading.models import Prompt, PromptFeedback, Recording


class Command(BaseCommand):
    help = "Archive all existing clip and reading payloads after an independently verified full backup. Preview by default."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--expected-clips", type=int, required=True)
        parser.add_argument("--expected-prompts", type=int, required=True)
        parser.add_argument("--expected-recordings", type=int, required=True)
        parser.add_argument("--expected-completed", type=int, required=True)
        parser.add_argument("--expected-accepted", type=int, required=True)

    def handle(self, apply, expected_clips, expected_prompts, expected_recordings,
               expected_completed, expected_accepted, **kwargs):
        counts = (Clip.objects.count(), Prompt.objects.count(), Recording.objects.count())
        expected = (expected_clips, expected_prompts, expected_recordings)
        if counts != expected:
            raise CommandError(f"Counts changed: actual clips/prompts/recordings={counts}, expected={expected}. No changes.")
        clip_audio = set(Clip.objects.exclude(audio="").values_list("audio", flat=True))
        recording_audio = set(Recording.objects.exclude(audio="").values_list("audio", flat=True))
        completed = Clip.objects.filter(is_gold=False, status=Clip.Status.RESOLVED).count()
        accepted = Recording.objects.filter(status=Recording.Status.ACCEPTED).count()
        if (completed, accepted) != (expected_completed, expected_accepted):
            raise CommandError(f"Accepted corpus changed: clips={completed}, recordings={accepted}. No changes.")
        seconds = Recording.objects.filter(status=Recording.Status.ACCEPTED).aggregate(total=Sum("duration"))["total"] or 0
        self.stdout.write(f"{'APPLY' if apply else 'PREVIEW'}: clips={counts[0]} (completed={completed}); "
                          f"prompts={counts[1]}; recordings={counts[2]} (accepted_minutes={seconds / 60:.2f}); "
                          f"clip_audio={len(clip_audio)}; recording_audio={len(recording_audio)}")
        if not apply:
            return
        with transaction.atomic():
            preserve_rejections(ClipEdit.objects.all(), Recording.objects.all())
            ClipEdit.objects.filter(Q(verdict__in=["pending", "redo", "rejected"]) |
                                    Q(verdict="accepted", reviewed_by__isnull=True, auto_accepted=False)).delete()
            Recording.objects.exclude(status=Recording.Status.ACCEPTED).delete()
            Batch.objects.update(is_open=False)
            Prompt.objects.update(is_active=False, text="")
            Clip.objects.update(audio="", draft_text="", final_text="", gold_text="")
            ClipEdit.objects.update(text="")
            Recording.objects.update(audio="", text_snapshot="")
            # Feedback text can reproduce the same phrase after its prompt is archived.
            PromptFeedback.objects.update(original_text="", suggested_text="")

            def remove_audio():
                clip_storage = Clip._meta.get_field("audio").storage
                recording_storage = Recording._meta.get_field("audio").storage
                for name in clip_audio:
                    if not Clip.objects.filter(audio=name).exists() and not Recording.objects.filter(audio=name).exists():
                        clip_storage.delete(name)
                for name in recording_audio - clip_audio:
                    if not Recording.objects.filter(audio=name).exists() and not Clip.objects.filter(audio=name).exists():
                        recording_storage.delete(name)

            transaction.on_commit(remove_audio)
        self.stdout.write(self.style.SUCCESS("Archived payloads; decision rows and durations retained."))
