from fractions import Fraction
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from gamification.models import PointLedger
from .models import Batch, Clip, ClipEdit, ClipReviewEvent
from .services import submit_edit, accept_edit, next_clip_for, resolve

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
    def test_third_answer_after_manual_acceptance_and_fourth_is_blocked(self):
        Clip.objects.create(batch=self.batch, audio="untouched.wav")
        fourth = get_user_model().objects.create_user(username="fourth")
        _, first = submit_edit(self.clip, self.users[0], "first")
        accept_edit(first, fourth)
        self.assertNotEqual(next_clip_for(self.users[0]), self.clip)
        for user in self.users[1:]:
            self.assertEqual(next_clip_for(user), self.clip)
            self.assertEqual(submit_edit(self.clip, user, "independent")[0], "saved")
        self.assertNotEqual(next_clip_for(fourth), self.clip)
        self.assertEqual(submit_edit(self.clip, fourth, "stale tab")[0], "closed")
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.final_text, "first")
        self.assertEqual(self.clip.edits.count(), 3)
        self.assertEqual(PointLedger.objects.count(), 1)

    def test_queue_prioritizes_cross_checks_without_making_participants_wait(self):
        second = Clip.objects.create(batch=self.batch, audio="second.wav")
        first_user, second_user, third_user = self.users
        self.assertEqual(next_clip_for(first_user, skip_clip_id=self.clip.pk), second)
        self.assertEqual(next_clip_for(first_user), self.clip)
        submit_edit(self.clip, first_user, "text")
        self.assertEqual(next_clip_for(first_user), second)
        submit_edit(second, first_user, "another text")
        self.assertEqual(next_clip_for(second_user), self.clip)
        submit_edit(self.clip, second_user, "text")
        self.assertEqual(next_clip_for(second_user), second)
        self.assertEqual(next_clip_for(third_user), self.clip)
        submit_edit(self.clip, third_user, "text")
        self.assertEqual(next_clip_for(third_user), second)
        self.assertEqual(self.clip.edits.count(), 3)

    def test_two_matches_use_existing_rating_formula(self):
        for dissent_rate, expected_acceptances in ((Fraction(1, 2), 2), (Fraction(3, 4), 0)):
            with self.subTest(dissent_rate=dissent_rate):
                clip = Clip.objects.create(batch=self.batch, audio="rated.wav")
                rates = dict(zip((user.pk for user in self.users),
                                 (Fraction(3, 4), Fraction(3, 4), dissent_rate)))
                with patch("clips.services.approval_rates", return_value=rates):
                    for user, answer in zip(self.users, ("same", "same", "different")):
                        submit_edit(clip, user, answer)
                self.assertEqual(clip.edits.filter(auto_accepted=True).count(), expected_acceptances)

    def test_history_keeps_snapshots_and_requires_editor_access(self):
        reviewer = get_user_model().objects.create_user(username="reviewer", is_staff=True)
        _, first = submit_edit(self.clip, self.users[0], "original")
        accept_edit(first, reviewer)
        accept_edit(first, reviewer)
        resolve(self.clip, "replacement", reviewer)
        self.assertEqual(list(ClipReviewEvent.objects.values_list("text", flat=True)),
                         ["replacement", "original"])
        self.client.force_login(self.users[0])
        self.assertEqual(self.client.get(reverse("clip-review-history")).status_code, 403)
        self.client.force_login(reviewer)
        page = self.client.get(reverse("clip-review-history"))
        self.assertContains(page, "reviewer")
        self.assertContains(page, "original")
        self.assertContains(page, "replacement")

    def test_private_media_requires_login(self):
        response = self.client.get("/media/clips/example.wav")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
