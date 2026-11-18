import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clips.models import ClipEdit
from gamification.models import ArchivedRejection
from reading.models import Recording


class Command(BaseCommand):
    help = "Preview or import historical rejection metadata without restoring submissions."

    def add_arguments(self, parser):
        parser.add_argument("manifest", type=Path)
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, manifest, apply, **kwargs):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            records = []
            for key, kind, model, target in (
                ("clips_clipedit", "clip", ClipEdit, "clip_id"),
                ("reading_recording", "recording", Recording, "prompt_id"),
            ):
                source = data[key]
                counts = {"new": 0, "existing": 0, "live": 0}
                for row in source:
                    pk, user_id, target_id = (row[field] for field in ("id", "user_id", target))
                    if any(type(value) is not int or value < 1 for value in (pk, user_id, target_id)):
                        raise ValueError("IDs must be positive integers.")
                    if not get_user_model().objects.filter(pk=user_id).exists():
                        raise ValueError(f"Unknown user ID {user_id}.")
                    if model.objects.filter(pk=pk).exists() or model.objects.filter(
                        user_id=user_id, **{target: target_id}
                    ).exists():
                        counts["live"] += 1
                        continue
                    previous = ArchivedRejection.objects.filter(kind=kind, submission_id=pk).first()
                    if previous:
                        if (previous.user_id, previous.target_id) != (user_id, target_id):
                            raise ValueError(f"Conflicting identity for {kind} {pk}.")
                        counts["existing"] += 1
                        continue
                    records.append(ArchivedRejection(
                        kind=kind, submission_id=pk, target_id=target_id, user_id=user_id))
                    counts["new"] += 1
                self.stdout.write(f"{kind}: {counts}")
            keys = {(record.kind, record.submission_id) for record in records}
            if len(keys) != len(records):
                raise ValueError("Duplicate submission ID in manifest.")
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        if apply:
            ArchivedRejection.objects.bulk_create(records)
        self.stdout.write(f"{'IMPORTED' if apply else 'PREVIEW'}: {len(records)}")
