from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Batch, Clip, ClipEdit
from .services import submit_edit, accept_edit

class ClipWorkflowTests(TestCase):
    def setUp(self):
        self.users = [get_user_model().objects.create_user(username=n) for n in ("a", "b", "c")]
        self.batch = Batch.objects.create(name="Batch")
        self.clip = Clip.objects.create(batch=self.batch, audio="dummy.wav")
    def test_closed_batch_rejects_direct_post(self):
        self.batch.is_open = False
        self.batch.save()
        self.client.force_login(self.users[0])
        self.assertEqual(self.client.post(reverse("clip-edit", args=[self.clip.pk]), {"text":"test"}).status_code, 404)
        self.assertEqual(ClipEdit.objects.count(), 0)
    def test_disagreement_waits_for_more_people(self):
        for user in self.users[:2]:
            submit_edit(self.clip, user, "same")
        result, _ = submit_edit(self.clip, self.users[2], "different")
        self.assertEqual(result, "saved")
        self.assertEqual(ClipEdit.objects.count(), 3)
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.final_text, "")
        self.assertFalse(self.clip.is_done)
        self.assertFalse(self.clip.edits.exclude(verdict="pending").exists())
    def test_final_text_uses_project_palochka(self):
        submit_edit(self.clip, self.users[0], "тIехь")
        submit_edit(self.clip, self.users[1], "тӀехь")
        accept_edit(self.clip.edits.first(), self.users[2])
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.final_text, "тӀехь")
    def test_three_exact_answers_are_accepted(self):
        for user in self.users:
            submit_edit(self.clip, user, "гьаб текст")
        self.clip.refresh_from_db()
        self.assertTrue(self.clip.is_done)
        self.assertEqual(self.clip.final_text, "гьаб текст")
        self.assertEqual(self.clip.edits.filter(verdict="accepted", auto_accepted=True).count(), 3)
    def test_spaces_do_not_count_as_same_answer(self):
        for user, text in zip(self.users, ("гьаб текст", "гьаб  текст", "гьаб текст")):
            submit_edit(self.clip, user, text)
        self.clip.refresh_from_db()
        self.assertFalse(self.clip.is_done)
    def test_private_media_requires_login(self):
        response = self.client.get("/media/clips/example.wav")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
