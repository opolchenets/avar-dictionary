from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Batch, Clip, ClipEdit
from .services import submit_edit

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
    def test_stale_third_edit_cannot_change_completed_clip(self):
        for user in self.users[:2]:
            submit_edit(self.clip, user, "same")
        result, _ = submit_edit(self.clip, self.users[2], "different")
        self.assertEqual(result, "closed")
        self.assertEqual(ClipEdit.objects.count(), 2)
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.final_text, "same")
    def test_final_text_uses_project_palochka(self):
        submit_edit(self.clip, self.users[0], "тIехь")
        submit_edit(self.clip, self.users[1], "тӀехь")
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.final_text, "тӀехь")
    def test_private_media_requires_login(self):
        response = self.client.get("/media/clips/example.wav")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
