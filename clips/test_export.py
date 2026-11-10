import csv
import tempfile
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from .models import Batch, Clip
from reading.models import Prompt, Recording


class CorpusExportTests(TestCase):
    def test_export_only_final_or_reference_material_and_accepted_recordings(self):
        batch = Batch.objects.create(name="Batch")
        Clip.objects.create(batch=batch, audio="clips/open.wav", draft_text="unverified")
        Clip.objects.create(batch=batch, audio="clips/final.wav", status="resolved", final_text="тIехь")
        Clip.objects.create(batch=batch, audio="clips/automatic.wav", status="agreed", final_text="unreviewed")
        Clip.objects.create(batch=batch, audio="clips/gold.wav", is_gold=True, gold_text="тӀехь")
        user = get_user_model().objects.create_user(username="private-name")
        prompt = Prompt.objects.create(text="phrase")
        Recording.objects.create(prompt=prompt, user=user, audio="recordings/pending.wav")
        other_prompt = Prompt.objects.create(text="accepted phrase")
        Recording.objects.create(prompt=other_prompt, user=user, audio="recordings/accepted.wav", status="accepted", duration=1)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            call_command("export_corpus", temp, verbosity=0)
            path = Path(temp)
            with (path/"transcriptions.csv").open(encoding="utf-8") as f:
                clips = list(csv.DictReader(f))
            with (path/"recordings.csv").open(encoding="utf-8") as f:
                recs = list(csv.DictReader(f))
            self.assertEqual({row["kind"] for row in clips}, {"reference", "transcription"})
            self.assertTrue(all(row["text"] == "тӀехь" for row in clips))
            self.assertEqual(len(recs), 1)
            self.assertNotIn("private-name", (path/"recordings.csv").read_text(encoding="utf-8"))
