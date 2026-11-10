from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from clips.models import AudioIssue, Batch, Clip, ClipEdit
from gamification.models import PointLedger

class CompactEditorTests(TestCase):
    def test_compact_form_and_report_without_comment(self):
        user=get_user_model().objects.create_user("reporter")
        clip=Clip.objects.create(batch=Batch.objects.create(name="batch"), audio="clips/a.wav")
        self.client.force_login(user)
        url=reverse("clip-edit",args=[clip.pk])
        response=self.client.get(url)
        self.assertContains(response,'problemToggle')
        self.assertNotContains(response,'Палочка: кнопка')
        self.assertNotContains(response,'Литературная норма.</b>')
        for _ in range(2):
            self.client.post(url,{"action":"report","text":"unsaved"})
        self.assertEqual(AudioIssue.objects.count(),1)
        self.assertEqual(AudioIssue.objects.get().note,"")
        self.assertFalse(ClipEdit.objects.exists())
        self.assertFalse(PointLedger.objects.exists())
