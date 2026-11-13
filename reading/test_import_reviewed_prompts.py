import csv
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Prompt


class ImportReviewedPromptsTests(TestCase):
    def write_csv(self, rows):
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", suffix=".csv", delete=False)
        with handle:
            writer = csv.DictWriter(handle, fieldnames=("id", "source", "text", "decision"))
            writer.writeheader()
            writer.writerows(rows)
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_preview_then_imports_only_approved_prompt(self):
        file = self.write_csv([
            {"id": "P0001", "source": "Маргьаби", "text": "Гьаб къокъаб рагӀи буго.", "decision": "да"},
            {"id": "P0002", "source": "Маргьаби", "text": "Гьаб рагӀи тӀадеги буго.", "decision": ""},
        ])
        call_command("import_reviewed_prompts", file)
        self.assertEqual(Prompt.objects.count(), 0)
        call_command("import_reviewed_prompts", file, apply=True)
        self.assertEqual(list(Prompt.objects.values_list("text", flat=True)), ["Гьаб къокъаб рагӀи буго."])

    def test_refuses_existing_prompt(self):
        Prompt.objects.create(text="Гьаб къокъаб рагӀи буго.", source="Старый")
        file = self.write_csv([
            {"id": "P0001", "source": "Маргьаби", "text": "Гьаб къокъаб рагӀи буго.", "decision": "да"},
        ])
        with self.assertRaisesMessage(CommandError, "Duplicate phrase"):
            call_command("import_reviewed_prompts", file, apply=True)
