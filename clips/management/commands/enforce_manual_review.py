from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from clips.models import Clip, ClipEdit
from gamification.models import PointLedger


class Command(BaseCommand):
    help = "Return legacy automatic verdicts to pending; preserve human decisions. Preview by default."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, apply, **kwargs):
        automatic = ClipEdit.objects.filter(reviewed_by__isnull=True, auto_accepted=False).exclude(verdict="redo")
        reset = automatic.exclude(verdict="pending").count()
        points = PointLedger.objects.filter(reason="clip_accepted",
            clip__edits__reviewed_by__isnull=True, clip__edits__auto_accepted=False,
            clip__edits__user_id=F('user_id')).distinct().count()
        if apply:
            actual_reset = actual_removed = 0
            for pk in Clip.objects.filter(edits__isnull=False, edits__reviewed_by__isnull=True,
                                          edits__auto_accepted=False).distinct().values_list("pk", flat=True).iterator():
                with transaction.atomic():
                    clip = Clip.objects.select_for_update().get(pk=pk)
                    for edit in clip.edits.filter(reviewed_by__isnull=True, auto_accepted=False).exclude(verdict="redo"):
                        actual_reset += edit.verdict != "pending"
                        ClipEdit.objects.filter(pk=edit.pk).update(verdict="pending", reviewed_at=None)
                        removed, _ = PointLedger.objects.filter(user_id=edit.user_id, clip=clip, reason="clip_accepted").delete()
                        actual_removed += removed
                    if not clip.is_gold and clip.status == Clip.Status.AGREED:
                        clip.final_text = ""
                        clip.save(update_fields=["final_text", "updated_at"])
            reset, points = actual_reset, actual_removed
        self.stdout.write(f"{'APPLIED' if apply else 'PREVIEW (no changes)'}: automatic_verdicts_to_pending={reset}, automatic_point_entries_removed={points}, human_decisions_preserved=yes")
