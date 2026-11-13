from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from clips.models import Batch, Clip
from .models import Prompt, Recording


class PromptManagementTests(TestCase):
    def setUp(self):
        self.editor = get_user_model().objects.create_user(username="editor")
        self.editor.profile.role = "editor"
        self.editor.profile.save()
        self.member = get_user_model().objects.create_user(username="member")
        self.prompt = Prompt.objects.create(text="Старый проверенный текст")
        self.recording = Recording.objects.create(prompt=self.prompt, user=self.member,
                                                   audio="recordings/sample.wav", status="accepted")

    def test_editor_updates_prompt_without_changing_recording_snapshot(self):
        self.client.force_login(self.editor)
        self.assertContains(self.client.get(reverse("reading-home")), "Исправить текст фраз")
        response = self.client.post(reverse("reading-prompt-update", args=[self.prompt.pk]),
                                    {"original_text": self.prompt.text, "text": "Исправленный текст"})
        self.assertEqual(response.status_code, 302)
        self.prompt.refresh_from_db()
        self.recording.refresh_from_db()
        self.assertEqual(self.prompt.text, "Исправленный текст")
        self.assertEqual(self.recording.spoken_text, "Старый проверенный текст")

    def test_member_cannot_update_prompt(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse("reading-prompt-update", args=[self.prompt.pk]),
                                    {"original_text": self.prompt.text, "text": "Подмена"})
        self.assertEqual(response.status_code, 403)
        self.prompt.refresh_from_db()
        self.assertEqual(self.prompt.text, "Старый проверенный текст")

    def test_import_preview_is_read_only_and_apply_is_idempotent(self):
        batch = Batch.objects.create(name="Фазу", source="Фазу Алиева")
        for index in range(3):
            Clip.objects.create(batch=batch, audio=f"{index}.wav", status="resolved",
                                final_text=f"Проверенная длинная фраза номер {index}")
        output = StringIO()
        call_command("add_verified_prompts", count=2, stdout=output)
        self.assertEqual(Prompt.objects.count(), 1)
        call_command("add_verified_prompts", count=2, apply=True, stdout=output)
        self.assertEqual(Prompt.objects.count(), 3)
        call_command("add_verified_prompts", count=1, apply=True, stdout=output)
        self.assertEqual(Prompt.objects.count(), 4)
