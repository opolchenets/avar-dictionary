import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from common.normalizer import char_errors, normalize
from gamification.models import PointLedger
from .models import Batch, Clip, ClipEdit
from .services import submit_edit, set_verdict


class ModerationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.worker = User.objects.create_user(username="worker")
        self.reviewer = User.objects.create_user(username="reviewer")
        self.reviewer.profile.role = "co_editor"
        self.reviewer.profile.save()
        self.batch = Batch.objects.create(name="Control batch")
        self.clip = Clip.objects.create(batch=self.batch, audio="test.wav", is_gold=True,
            gold_text="Дагь-дагьккун гьей ботӀрол,")
        self.client.force_login(self.reviewer)

    def test_punctuation_case_and_word_boundaries_do_not_count(self):
        pairs = [
            ("Дагь-дагьккун гьей ботӀрол,", "ДАГЬ дагьккун гьей ботӀрол"),
            ("«ТӀехь» — тӀехь!", "тIехьт1ехь"),
            ("слово,слово", "слово слово"),
            ("Глодобцинабизе.", "Глодоб цинабизе"),
        ]
        for gold, text in pairs:
            with self.subTest(gold=gold):
                self.assertEqual(char_errors(gold, text), 0)
        self.assertEqual(char_errors("кот", "кит"), 1)
        self.assertNotEqual(normalize("#"), normalize("..."))

    def test_automatic_control_only_suggests_even_when_formatting_matches(self):
        text = "ДАГЬ дагьккун гьей ботӀрол"
        _, edit = submit_edit(self.clip, self.worker, text)
        edit.refresh_from_db()
        self.assertEqual(edit.verdict, "pending")
        self.assertFalse(PointLedger.objects.filter(clip=self.clip).exists())
        self.assertEqual(edit.errors, 0)
        self.assertEqual(edit.text, text)
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.gold_text, "Дагь-дагьккун гьей ботӀрол,")

    def rejected_edit(self):
        _, edit = submit_edit(self.clip, self.worker, "совсем другой ответ")
        return edit

    def test_coeditor_can_accept_rejected_control_and_reverse_decision(self):
        edit = self.rejected_edit()
        set_verdict(edit, "rejected", self.reviewer)
        url = reverse("clip-verdict", args=[edit.pk])
        for verdict, points in [("accepted", 1), ("accepted", 1), ("rejected", 0), ("accepted", 1)]:
            response = self.client.post(url, {"verdict": verdict, "next": "/clips/review/?status=gold"})
            self.assertEqual(response.status_code, 302)
            edit.refresh_from_db()
            self.assertEqual(edit.verdict, verdict)
            self.assertEqual(edit.reviewed_by_id, self.reviewer.pk)
            self.assertEqual(PointLedger.objects.filter(user=self.worker, clip=self.clip).count(), points)
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.status, "open")

    def test_control_override_does_not_change_other_users_or_reference(self):
        edit = self.rejected_edit()
        other = get_user_model().objects.create_user(username="other")
        _, other_edit = submit_edit(self.clip, other, "тоже неверно")
        self.client.post(reverse("clip-verdict", args=[edit.pk]), {"verdict": "accepted"})
        other_edit.refresh_from_db()
        self.clip.refresh_from_db()
        self.assertEqual(other_edit.verdict, "pending")
        self.assertIsNone(other_edit.reviewed_by_id)
        self.assertEqual(self.clip.gold_text, "Дагь-дагьккун гьей ботӀрол,")

    def test_closed_batch_still_allows_editor_to_revise_reference(self):
        edit = self.rejected_edit()
        self.batch.is_open = False
        self.batch.save()
        response = self.client.post(reverse("clip-resolve", args=[self.clip.pk]), {"text": edit.text})
        self.assertEqual(response.status_code, 302)
        self.clip.refresh_from_db()
        edit.refresh_from_db()
        self.assertEqual(self.clip.gold_text, edit.text)
        self.assertEqual(edit.errors, 0)
        self.assertEqual(edit.verdict, "pending")
        self.assertEqual(self.clip.status, "open")

    def test_reference_revision_preserves_human_verdict(self):
        edit = self.rejected_edit()
        set_verdict(edit, "accepted", self.reviewer)
        self.client.post(reverse("clip-resolve", args=[self.clip.pk]), {"text": "другой эталон"})
        edit.refresh_from_db()
        self.assertEqual(edit.verdict, "accepted")
        self.assertEqual(edit.reviewed_by_id, self.reviewer.pk)
        self.assertGreater(edit.errors, 0)

    def test_participant_cannot_review_or_change_reference(self):
        edit = self.rejected_edit()
        self.client.force_login(self.worker)
        self.assertEqual(self.client.post(reverse("clip-verdict", args=[edit.pk]), {"verdict": "accepted"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("clip-resolve", args=[self.clip.pk]), {"text": "new"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("clip-review") + "?status=gold").status_code, 403)
        edit.refresh_from_db()
        self.assertEqual(edit.verdict, "pending")

    def test_control_page_contains_working_actions_and_reference_editor(self):
        edit = self.rejected_edit()
        response = self.client.get(reverse("clip-review") + "?status=gold")
        self.assertContains(response, reverse("clip-verdict", args=[edit.pk]))
        self.assertContains(response, reverse("clip-resolve", args=[self.clip.pk]))
        self.assertContains(response, "Исправить эталон")

    def test_review_form_submits_with_csrf_protection_enabled(self):
        edit = self.rejected_edit()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reviewer)
        page = client.get(reverse("clip-review") + "?status=gold")
        self.assertEqual(page.status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post(reverse("clip-verdict", args=[edit.pk]),
            {"verdict": "accepted", "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)
        edit.refresh_from_db()
        self.assertEqual(edit.verdict, "accepted")

    def test_reassessment_preview_and_apply_preserve_manual_decisions(self):
        edit = ClipEdit.objects.create(clip=self.clip, user=self.worker,
            text="Дагь дагьккун гьей ботӀрол", errors=1, verdict="rejected")
        other = get_user_model().objects.create_user(username="other")
        manual = ClipEdit.objects.create(clip=self.clip, user=other, text=edit.text,
            errors=1, verdict="rejected", reviewed_by=self.reviewer)
        call_command("reassess_gold", stdout=io.StringIO())
        edit.refresh_from_db()
        self.assertEqual(edit.errors, 1)
        call_command("reassess_gold", apply=True, stdout=io.StringIO())
        edit.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual((edit.errors, edit.verdict), (0, "rejected"))
        self.assertEqual((manual.errors, manual.verdict), (0, "rejected"))
        call_command("reassess_gold", apply=True, stdout=io.StringIO())
        self.assertEqual(PointLedger.objects.filter(user=self.worker, clip=self.clip).count(), 0)
