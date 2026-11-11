from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Prompt, Recording, PromptFeedback
from .views import next_prompt_for


class PromptFeedbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('speaker')
        self.editor = get_user_model().objects.create_user('editor', is_staff=True)
        self.prompt = Prompt.objects.create(text='Исходная фраза')
        self.client.force_login(self.user)

    def report(self):
        return self.client.post(reverse('reading-feedback', args=[self.prompt.pk]),
                                {'original_text': self.prompt.text, 'suggested_text': 'Исправленная фраза'})

    def test_participant_proposal_does_not_change_prompt_or_records(self):
        self.report(); self.report()
        self.prompt.refresh_from_db()
        self.assertEqual(self.prompt.text, 'Исходная фраза')
        self.assertEqual(PromptFeedback.objects.count(), 1)
        self.assertFalse(Recording.objects.exists())
        self.assertIsNone(next_prompt_for(self.user))
        item = PromptFeedback.objects.get()
        response = self.client.post(reverse('reading-feedback-verdict', args=[item.pk]),
                                    {'action': 'apply', 'text': 'Нельзя'})
        self.assertEqual(response.status_code, 403)

    def test_editor_change_preserves_recording_text_and_verdict(self):
        rec = Recording.objects.create(prompt=self.prompt, user=self.user, audio='recordings/existing.wav',
                                       text_snapshot=self.prompt.text, status='accepted')
        self.report()
        item = PromptFeedback.objects.get()
        self.client.force_login(self.editor)
        self.client.post(reverse('reading-feedback-verdict', args=[item.pk]),
                         {'action': 'apply', 'text': item.suggested_text})
        self.prompt.refresh_from_db(); rec.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(self.prompt.text, 'Исправленная фраза')
        self.assertEqual(rec.spoken_text, 'Исходная фраза')
        self.assertEqual(rec.status, 'accepted')
        self.assertEqual(item.status, 'applied')
        self.assertContains(self.client.get(reverse('reading-review')+'?status=accepted'), 'Исходная фраза')
        import csv, tempfile
        from pathlib import Path
        from django.core.management import call_command
        from django.conf import settings
        with tempfile.TemporaryDirectory(dir=settings.BASE_DIR) as tmp:
            call_command('export_corpus', tmp)
            with (Path(tmp)/'recordings.csv').open(encoding='utf-8') as stream:
                exported=list(csv.DictReader(stream))
            self.assertEqual(exported[0]['text'], 'Исходная фраза')
            self.assertEqual(int(exported[0]['speaker_id']), self.user.pk)

    def test_stale_proposal_is_not_applied(self):
        self.report(); item = PromptFeedback.objects.get()
        self.prompt.text = 'Уже исправлено'; self.prompt.save()
        self.client.force_login(self.editor)
        self.client.post(reverse('reading-feedback-verdict', args=[item.pk]),
                         {'action': 'apply', 'text': item.suggested_text})
        self.prompt.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(self.prompt.text, 'Уже исправлено')
        self.assertEqual(item.status, 'pending')

    def test_report_without_note_or_correction_and_disable(self):
        self.client.post(reverse('reading-feedback', args=[self.prompt.pk]), {'original_text':self.prompt.text})
        item = PromptFeedback.objects.get()
        self.client.force_login(self.editor)
        self.client.post(reverse('reading-feedback-verdict',args=[item.pk]), {'action':'disable'})
        self.prompt.refresh_from_db()
        self.assertFalse(self.prompt.is_active)

    def test_existing_recording_backfill(self):
        import importlib
        from django.apps import apps
        from django.db import connection
        from types import SimpleNamespace
        rec = Recording.objects.create(prompt=self.prompt, user=self.user, audio='existing.wav')
        Recording.objects.filter(pk=rec.pk).update(text_snapshot='')
        migration = importlib.import_module('reading.migrations.0002_recording_text_snapshot_promptfeedback')
        migration.snapshot_existing(apps, SimpleNamespace(connection=connection))
        rec.refresh_from_db()
        self.assertEqual(rec.text_snapshot,self.prompt.text)
