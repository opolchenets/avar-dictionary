import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from clips.models import Batch, Clip, ClipEdit
from gamification.models import PointLedger
from gamification.ranking import user_rows
from reading.models import Consent, Prompt, Recording


class ResetTrialTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("owner", password="test", is_superuser=True)
        self.clip = Clip.objects.create(batch=Batch.objects.create(name="source"), audio="clips/source.wav",
            draft_text="draft", gold_text="reference", is_gold=True, final_text="trial", status="resolved")
        ClipEdit.objects.create(clip=self.clip, user=self.user, text="trial", verdict="accepted", reviewed_by=self.user)
        self.prompt = Prompt.objects.create(text="original")
        Recording.objects.create(prompt=self.prompt, user=self.user, audio="recordings/trial.wav", status="accepted")
        Consent.objects.create(user=self.user)
        PointLedger.objects.create(user=self.user, clip=self.clip, reason="clip_accepted", points=10)

    def test_preview_and_missing_backup_confirmation_never_change_data(self):
        call_command("reset_trial", stdout=io.StringIO())
        with self.assertRaises(CommandError):
            call_command("reset_trial", apply=True, stdout=io.StringIO())
        self.assertEqual(ClipEdit.objects.count(), 1)
        self.assertEqual(Recording.objects.count(), 1)
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.final_text, "trial")

    def test_apply_preserves_sources_accounts_consents_and_allows_retry(self):
        password = self.user.password
        for _ in range(2):
            call_command("reset_trial", apply=True, backup_confirmed=True, stdout=io.StringIO())
        self.clip.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual((self.clip.status, self.clip.final_text), ("open", ""))
        self.assertEqual((self.clip.draft_text, self.clip.gold_text, self.clip.audio.name),
                         ("draft", "reference", "clips/source.wav"))
        self.assertTrue(self.clip.is_gold)
        self.assertEqual(self.user.password, password)
        self.assertTrue(self.user.is_superuser)
        self.assertEqual(Consent.objects.count(), 1)
        self.assertEqual(Prompt.objects.get().text, "original")
        self.assertFalse(ClipEdit.objects.exists())
        self.assertFalse(Recording.objects.exists())
        self.assertFalse(PointLedger.objects.exists())
        self.assertEqual(user_rows(), [])
        ClipEdit.objects.create(clip=self.clip, user=self.user, text="new")
        Recording.objects.create(prompt=self.prompt, user=self.user, audio="recordings/new.wav")
