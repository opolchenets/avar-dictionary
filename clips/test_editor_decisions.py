import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from gamification.models import PointLedger
from gamification.ranking import user_rows
from .models import Batch, Clip, ClipEdit
from .services import accept_edit, set_verdict, submit_edit, user_stats


class EditorDecisionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.first = User.objects.create_user(username="first")
        self.second = User.objects.create_user(username="second")
        self.reviewer = User.objects.create_user(username="reviewer")
        self.reviewer.profile.role = "co_editor"
        self.reviewer.profile.save()
        self.client.force_login(self.reviewer)
        batch = Batch.objects.create(name="batch")
        self.gold = Clip.objects.create(batch=batch, audio="gold.wav", is_gold=True, gold_text="тӀехь")
        self.normal = Clip.objects.create(batch=batch, audio="normal.wav")

    def page(self, status="pending", kind="all"):
        return self.client.get(reverse("clip-review"), {"status": status, "kind": kind})

    @staticmethod
    def displayed_ids(response):
        return {edit.pk for clip in response.context["clips"] for edit in clip.review_edits}

    def decide(self, edit, verdict):
        return self.client.post(reverse("clip-verdict", args=[edit.pk]),
            {"verdict": verdict, "next": "/clips/review/?status=pending&kind=all"}, follow=True)

    def test_all_submissions_enter_pending_before_second_response(self):
        _, gold = submit_edit(self.gold, self.first, "тӀехь")
        _, regular = submit_edit(self.normal, self.first, "text")
        response = self.page()
        self.assertEqual(response.context["counts"]["pending"], 2)
        self.assertEqual(self.displayed_ids(response), {gold.pk, regular.pk})
        self.assertFalse(PointLedger.objects.exists())
        self.assertEqual(user_stats(self.first)["accepted"], 0)
        self.assertEqual(user_rows(), [])

    def test_two_matching_answers_wait_for_third(self):
        for user in (self.first, self.second):
            submit_edit(self.normal, user, "same")
        self.normal.refresh_from_db()
        self.assertEqual(self.normal.status, "open")
        self.assertFalse(self.normal.is_done)
        self.assertEqual(self.normal.final_text, "")
        self.assertEqual(self.normal.edits.filter(verdict="pending").count(), 2)
        self.assertFalse(PointLedger.objects.exists())
        self.assertEqual(self.page().context["counts"]["pending"], 2)

    def test_failed_automatic_hint_does_not_reject_or_award(self):
        _, edit = submit_edit(self.gold, self.first, "совсем другой ответ")
        self.assertGreater(edit.errors, 0)
        self.assertEqual(edit.verdict, "pending")
        self.assertIsNone(edit.reviewed_by_id)
        self.assertFalse(PointLedger.objects.exists())
        self.assertEqual(self.displayed_ids(self.page()), {edit.pk})

    def test_accepted_control_leaves_pending_and_enters_accepted(self):
        _, edit = submit_edit(self.gold, self.first, "тӀехь")
        response = self.decide(edit, "accepted")
        self.assertEqual(response.context["counts"]["pending"], 0)
        self.assertEqual(response.context["counts"]["accepted"], 1)
        self.assertEqual(self.displayed_ids(response), set())
        self.assertEqual(self.displayed_ids(self.page("accepted")), {edit.pk})
        self.assertEqual(self.displayed_ids(self.page("accepted", "gold")), {edit.pk})
        self.assertEqual(self.displayed_ids(self.page("accepted", "new")), set())
        self.assertEqual(user_stats(self.first), {"total": 1, "accepted": 1, "rejected": 0, "redo": 0, "pending": 0})

    def test_rejected_control_moves_and_can_be_accepted_later(self):
        _, edit = submit_edit(self.gold, self.first, "incorrect")
        self.decide(edit, "rejected")
        self.assertEqual(self.displayed_ids(self.page()), set())
        self.assertEqual(self.displayed_ids(self.page("rejected")), {edit.pk})
        self.decide(edit, "accepted")
        self.assertEqual(self.displayed_ids(self.page("rejected")), set())
        self.assertEqual(self.displayed_ids(self.page("accepted")), {edit.pk})
        self.assertEqual(PointLedger.objects.count(), 1)

    def test_one_decision_does_not_approve_another_submission(self):
        _, first = submit_edit(self.normal, self.first, "same")
        _, second = submit_edit(self.normal, self.second, "same")
        self.decide(first, "accepted")
        second.refresh_from_db()
        self.assertEqual(second.verdict, "pending")
        self.assertEqual(self.displayed_ids(self.page()), {second.pk})
        self.assertEqual(self.displayed_ids(self.page("accepted")), {first.pk})
        self.assertEqual(PointLedger.objects.count(), 1)

    def test_final_verdict_cannot_be_made_without_reviewer(self):
        _, edit = submit_edit(self.gold, self.first, "тӀехь")
        with self.assertRaises(ValueError):
            set_verdict(edit, "accepted")
        edit.refresh_from_db()
        self.assertEqual(edit.verdict, "pending")
        self.assertFalse(PointLedger.objects.exists())

    def test_all_rejected_regular_answers_reopen_clip_for_other_participants(self):
        _, first = submit_edit(self.normal, self.first, "same")
        _, second = submit_edit(self.normal, self.second, "same")
        self.decide(first, "rejected")
        self.decide(second, "rejected")
        self.normal.refresh_from_db()
        self.assertEqual(self.normal.status, "open")
        self.assertEqual(self.normal.final_text, "")
        self.assertEqual(self.page().context["counts"]["pending"], 0)
        self.assertEqual(self.page("rejected").context["counts"]["rejected"], 2)

    def test_migration_returns_automatic_decisions_and_points_only(self):
        automatic = ClipEdit.objects.create(clip=self.gold, user=self.first,
            text="тӀехь", verdict="accepted", errors=0)
        manual = ClipEdit.objects.create(clip=self.gold, user=self.second,
            text="тӀехь", verdict="accepted", reviewed_by=self.reviewer)
        for edit in (automatic, manual):
            PointLedger.objects.create(user=edit.user, clip=self.gold, reason="clip_accepted", points=1)
        self.normal.status, self.normal.final_text = "agreed", "old automatic final"
        self.normal.save()
        legacy_normal = ClipEdit.objects.create(clip=self.normal, user=self.first, text="old automatic final", verdict="accepted")
        out = io.StringIO()
        call_command("enforce_manual_review", stdout=out)
        automatic.refresh_from_db()
        self.assertEqual(automatic.verdict, "accepted")
        self.assertIn("automatic_verdicts_to_pending=2", out.getvalue())
        call_command("enforce_manual_review", apply=True, stdout=io.StringIO())
        for edit in (automatic, legacy_normal):
            edit.refresh_from_db()
            self.assertEqual(edit.verdict, "pending")
            self.assertIsNone(edit.reviewed_at)
        manual.refresh_from_db()
        self.assertEqual(manual.verdict, "accepted")
        self.assertEqual(manual.reviewed_by_id, self.reviewer.pk)
        self.assertEqual(PointLedger.objects.count(), 1)
        self.normal.refresh_from_db()
        self.assertEqual(self.normal.final_text, "")
        call_command("enforce_manual_review", apply=True, stdout=io.StringIO())
        self.assertEqual(PointLedger.objects.count(), 1)

    def test_pending_queue_does_not_present_legacy_auto_accept_as_final(self):
        edit = ClipEdit.objects.create(clip=self.gold, user=self.first, text="тӀехь", verdict="accepted", errors=0)
        response = self.page()
        self.assertEqual(self.displayed_ids(response), {edit.pk})
        self.assertContains(response, "Ждёт оценки")
        self.assertNotContains(response, ">Принята<")
        self.assertEqual(self.page("accepted").context["counts"]["accepted"], 0)
