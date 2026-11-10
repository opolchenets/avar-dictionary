from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from .models import Prompt, Recording

class RecordingValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="speaker")
        self.client.force_login(self.user)
        self.prompt = Prompt.objects.create(text="Phrase")
    def upload(self):
        return self.client.post(reverse("reading-record", args=[self.prompt.pk]), {"consent":"1", "duration":"-10", "audio":SimpleUploadedFile("fake.webm", b"fake"*1000, content_type="audio/webm")})
    def test_non_audio_rejected(self):
        self.assertEqual(self.upload().status_code, 400)
        self.assertFalse(Recording.objects.exists())
    def test_inactive_prompt_rejected(self):
        self.prompt.is_active=False
        self.prompt.save()
        self.assertEqual(self.upload().status_code, 404)
