import csv
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.normalizer import normalize
from reading.models import Prompt


class Command(BaseCommand):
    help = "Preview or import reading prompts marked approved in a reviewed CSV."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, file, apply, **kwargs):
        with open(file, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"id", "source", "text", "decision"}
            if not required.issubset(reader.fieldnames or []):
                raise CommandError("CSV must have id, source, text, decision columns")
            rows = list(reader)
        approved = [row for row in rows if row["decision"].strip().casefold() in {"да", "approved", "approve"}]
        if not approved:
            raise CommandError("No approved rows. Mark decision=да after review.")
        known = {normalize(text) for text in Prompt.objects.values_list("text", flat=True)}
        pending = []
        ids = set()
        for row in approved:
            identifier = row["id"].strip()
            text = row["text"].strip()
            source = row["source"].strip()
            if not identifier or identifier in ids:
                raise CommandError(f"Duplicate or empty ID: {identifier}")
            ids.add(identifier)
            if not source or not 21 <= len(text) <= 180 or not text.endswith((".", ",")):
                raise CommandError(f"Invalid source, length, or punctuation: {identifier}")
            if re.search(r"[\x00-\x1f\ufffd]", text):
                raise CommandError(f"Unresolved control character: {identifier}")
            normalized = normalize(text)
            if normalized in known:
                raise CommandError(f"Duplicate phrase already on site or in CSV: {identifier}")
            known.add(normalized)
            pending.append(Prompt(text=text, source=source))
        if apply:
            Prompt.objects.bulk_create(pending)
        by_source = {}
        for prompt in pending:
            by_source[prompt.source] = by_source.get(prompt.source, 0) + 1
        self.stdout.write(f"{'ADDED' if apply else 'PREVIEW'}: {len(pending)}; {by_source}")
