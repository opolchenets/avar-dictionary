"""Clear trial submissions without replacing the corpus or deleting accounts."""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clips.models import Clip, ClipEdit
from gamification.models import PointLedger
from reading.models import Consent, Prompt, Recording


class Command(BaseCommand):
    help = "Preview/reset ALL clip edits and reading recordings. Keep sources and accounts. Stop web first."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backup-confirmed", action="store_true",
                            help="Confirm a fresh database+media backup is verified on your computer.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["apply"] and not options["backup_confirmed"]:
            raise CommandError("First verify a fresh database+media backup on your computer; then use --backup-confirmed.")
        points = PointLedger.objects.filter(reason=PointLedger.Reason.CLIP_ACCEPTED)
        counts = {
            "clip_edits_to_delete": ClipEdit.objects.count(),
            "recordings_to_delete": Recording.objects.count(),
            "clip_points_to_delete": points.count(),
            "clips_to_reopen": Clip.objects.exclude(status=Clip.Status.OPEN, final_text="").count(),
            "clips_preserved": Clip.objects.count(),
            "prompts_preserved": Prompt.objects.count(),
            "users_preserved": get_user_model().objects.count(),
            "voice_consents_preserved": Consent.objects.count(),
        }
        self.stdout.write(json.dumps(counts, sort_keys=True))
        if not options["apply"]:
            self.stdout.write("PREVIEW ONLY. No changes. Stop web and verify a fresh backup before applying.")
            return
        points.delete()
        ClipEdit.objects.all().delete()
        Recording.objects.all().delete()
        Clip.objects.all().update(status=Clip.Status.OPEN, final_text="")
        self.stdout.write("APPLIED. Sources, gold references, users, roles, passwords and consents preserved. "
                          "Recording files retained for recovery; no media files deleted. "
                          "Translation materials/results and their points are unchanged.")
