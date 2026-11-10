import io
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.db import connection
from django.urls import reverse
from .models import Prompt, Recording
from .audio_validation import validate_audio


def wav_upload():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 8000)
    return SimpleUploadedFile("speech.wav", stream.getvalue(), content_type="audio/wav")


class RecordingWorkflowTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.override = override_settings(MEDIA_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.override.disable)
        self.user = get_user_model().objects.create_user(username="speaker")
        self.other = get_user_model().objects.create_user(username="other")
        self.prompt = Prompt.objects.create(text="ТӀехь")
        self.client.force_login(self.user)

    def upload(self):
        return self.client.post(reverse("reading-record", args=[self.prompt.pk]),
                                {"consent": "1", "duration": "999", "audio": wav_upload()})

    def test_duration_measured_and_duplicate_not_saved(self):
        self.assertEqual(self.upload().status_code, 200)
        rec = Recording.objects.get()
        self.assertAlmostEqual(rec.duration, 1.0)
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(Recording.objects.count(), 1)

    def test_second_speaker_cannot_submit_busy_phrase(self):
        self.upload()
        self.client.force_login(self.other)
        self.assertEqual(self.upload().status_code, 409)

    def test_redo_preserves_old_file_on_database_failure(self):
        self.upload()
        rec = Recording.objects.get()
        old = Path(rec.audio.path)
        rec.status = "redo"
        rec.save()
        with patch.object(Recording, "save", side_effect=RuntimeError("simulated database error")):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertTrue(old.is_file())
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.wav"))), 1)
        rec.refresh_from_db()
        self.assertEqual(rec.audio.path, str(old))

    def test_redo_replaces_only_after_commit(self):
        self.upload()
        rec = Recording.objects.get()
        old = Path(rec.audio.path)
        rec.status = "redo"
        rec.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.upload().status_code, 200)
        self.assertFalse(old.exists())
        rec.refresh_from_db()
        self.assertEqual(rec.attempts, 2)
        self.assertTrue(Path(rec.audio.path).is_file())

    def test_other_user_cannot_download_recording(self):
        self.upload()
        rec = Recording.objects.get()
        response = self.client.get(rec.audio.url)
        self.assertEqual(response.status_code, 200)
        # Exhaust the test client's iterator: its wrapper closes the file while
        # shielding the enclosing TestCase transaction from request cleanup.
        with patch.object(connection, "close_if_unusable_or_obsolete", wraps=connection.close_if_unusable_or_obsolete) as cleanup:
            content = b"".join(response.streaming_content)
        cleanup.assert_not_called()
        self.assertTrue(content)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(rec.audio.url).status_code, 404)

    def test_fake_audio_rejected(self):
        response = self.client.post(reverse("reading-record", args=[self.prompt.pk]),
            {"consent": "1", "duration": "-10", "audio": SimpleUploadedFile("fake.webm", b"fake" * 1000)})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Recording.objects.exists())

    @override_settings(AUDIO_REQUIRE_DECODER=True)
    @patch("reading.audio_validation.shutil.which", return_value=None)
    def test_production_refuses_unverified_webm(self, which):
        with self.assertRaises(ValueError):
            validate_audio(SimpleUploadedFile("record.webm", b"\x1a\x45\xdf\xa3" + b"x" * 3000), "1")
