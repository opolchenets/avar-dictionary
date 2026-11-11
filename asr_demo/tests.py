import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AsrTrial


class AsrDemoTests(TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="avar-asr-test-", dir=settings.BASE_DIR)
        self.settings = override_settings(
            ASR_TRIAL_ROOT=self.temp,
            ASR_SERVICE_URL="http://private-asr:8090",
            ASR_INTERNAL_TOKEN="x" * 64,
        )
        self.settings.enable()
        self.audio_field = AsrTrial._meta.get_field("audio")
        self.original_storage = self.audio_field.storage
        self.audio_field.storage = FileSystemStorage(location=self.temp)
        self.user = get_user_model().objects.create_user("speaker", password="password123")

    def tearDown(self):
        self.audio_field.storage = self.original_storage
        self.settings.disable()
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_login_required(self):
        response = self.client.get(reverse("asr-demo"))
        self.assertEqual(response.status_code, 302)

    @patch("asr_demo.views.recognize", return_value=("Гьаб текст буго", "test-version"))
    @patch("asr_demo.views.decode_trial", return_value=(b"\0" * 6400, 0.2))
    def test_trial_is_saved_and_result_returned(self, decode, recognize):
        self.client.force_login(self.user)
        response = self.client.post(reverse("asr-demo"), {
            "audio": SimpleUploadedFile("voice.webm", b"not-trusted-by-test")
        })
        self.assertEqual(response.status_code, 200)
        trial = AsrTrial.objects.get()
        self.assertEqual(trial.status, AsrTrial.Status.READY)
        self.assertEqual(trial.result_text, "Гьаб текст буго")
        self.assertContains(response, "Гьаб текст буго")
        self.assertFalse(trial.audio)
        self.assertFalse(any(__import__('pathlib').Path(self.temp).rglob('*.audio')))

    @patch("asr_demo.views.decode_trial", return_value=(b"\0" * 6400, 0.2))
    def test_limit_is_enforced_server_side(self, decode):
        AsrTrial.objects.bulk_create([AsrTrial(user=self.user, audio=f"x/{n}") for n in range(15)])
        self.client.force_login(self.user)
        response = self.client.post(reverse("asr-demo"), {
            "audio": SimpleUploadedFile("voice.webm", b"x")
        })
        self.assertEqual(response.status_code, 429)
        self.assertEqual(AsrTrial.objects.count(), 15)

    def test_cleanup_deletes_database_row_and_file(self):
        trial = AsrTrial(user=self.user, duration=1)
        trial.audio.save("voice.webm", SimpleUploadedFile("voice.webm", b"audio"), save=True)
        path = trial.audio.path
        AsrTrial.objects.filter(pk=trial.pk).update(created_at=timezone.now() - timedelta(hours=49))
        call_command("purge_asr_trials")
        self.assertFalse(AsrTrial.objects.filter(pk=trial.pk).exists())
        self.assertFalse(__import__("pathlib").Path(path).exists())
