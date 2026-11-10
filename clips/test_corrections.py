from django.contrib.auth import get_user_model
from django.core.management import call_command
import io
from django.test import TestCase
from django.urls import reverse

from clips.models import Batch, Clip, ClipEdit
from clips.services import accept_edit, next_clip_for, request_correction, submit_edit, user_stats
from gamification.models import PointLedger
from gamification.ranking import user_rows


class CorrectionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("speaker")
        self.other = User.objects.create_user("other")
        self.editor = User.objects.create_user("reviewer")
        self.editor.profile.role = "co_editor"
        self.editor.profile.save()
        self.batch = Batch.objects.create(name="batch")
        self.clip = Clip.objects.create(batch=self.batch, audio="clips/original.wav", draft_text="draft")
        _, self.edit = submit_edit(self.clip, self.user, "first")

    def test_return_and_resubmit_reuses_submission_and_does_not_judge(self):
        request_correction(self.edit, self.editor, "Уточните слово")
        self.assertEqual(user_stats(self.user)["redo"], 1)
        self.assertEqual(user_stats(self.user)["pending"], 0)
        self.assertFalse(self.edit.is_reviewed)
        self.assertEqual(user_rows(), [])
        result, edit = submit_edit(self.clip, self.user, "corrected")
        self.assertEqual(result, "saved")
        self.assertEqual(edit.pk, self.edit.pk)
        self.assertEqual((edit.verdict, edit.reviewed_by_id, edit.reviewed_at), ("pending", None, None))
        self.assertEqual(edit.reviewer_note, "Уточните слово")
        self.assertEqual(ClipEdit.objects.count(), 1)
        self.assertFalse(PointLedger.objects.exists())

    def test_revoke_accepted_submission_removes_only_its_points(self):
        accept_edit(self.edit, self.editor)
        request_correction(self.edit, self.editor, "Исправьте")
        self.clip.refresh_from_db()
        self.assertEqual((self.clip.status, self.clip.final_text), ("open", ""))
        self.assertFalse(PointLedger.objects.exists())
        self.assertEqual(user_stats(self.user)["rejected"], 0)

    def test_owner_can_retry_resolved_clip_without_changing_another_users_final(self):
        _, second = submit_edit(self.clip, self.other, "accepted version")
        accept_edit(second, self.editor)
        request_correction(self.edit, self.editor, "Попробуйте ещё")
        self.assertEqual(next_clip_for(self.user), self.clip)
        self.assertIsNone(next_clip_for(self.user, skip_clip_id=self.clip.pk))
        self.client.force_login(self.user)
        response = self.client.get(reverse("clip-edit", args=[self.clip.pk]))
        self.assertContains(response, "Попробуйте ещё")
        self.assertContains(response, 'id="clipText"')
        self.client.post(reverse("clip-edit", args=[self.clip.pk]), {"text": "retry", "action": "save"})
        self.clip.refresh_from_db()
        second.refresh_from_db()
        self.edit.refresh_from_db()
        self.assertEqual((self.clip.status, self.clip.final_text), ("resolved", "accepted version"))
        self.assertEqual(second.verdict, "accepted")
        self.assertEqual(self.edit.verdict, "pending")
        self.assertEqual(PointLedger.objects.count(), 1)
        self.assertEqual(submit_edit(self.clip, self.editor, "forbidden")[0], "closed")

    def test_gold_retry_reassesses_hint_only_and_preserves_reference(self):
        self.clip.is_gold, self.clip.gold_text = True, "reference"
        self.clip.save()
        request_correction(self.edit, self.editor, "Слушайте снова")
        _, edit = submit_edit(self.clip, self.user, "reference")
        self.assertEqual((edit.verdict, edit.errors), ("pending", 0))
        self.clip.refresh_from_db()
        self.assertEqual(self.clip.gold_text, "reference")
        self.assertFalse(PointLedger.objects.exists())

    def test_comment_required_permissions_and_queue_transition(self):
        url = reverse("clip-verdict", args=[self.edit.pk])
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url, {"verdict": "redo", "note": "x"}).status_code, 403)
        self.client.force_login(self.editor)
        self.client.post(url, {"verdict": "redo", "note": "  "})
        self.edit.refresh_from_db()
        self.assertEqual(self.edit.verdict, "pending")
        self.client.post(url, {"verdict": "redo", "note": "Исправьте слово"})
        pending = self.client.get(reverse("clip-review"))
        self.assertEqual(pending.context["counts"]["pending"], 0)
        response = self.client.get(reverse("clip-review") + "?status=redo")
        self.assertContains(response, "Исправьте слово")
        self.assertEqual(response.context["counts"]["redo"], 1)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("clip-home")), "Исправить →")
        submit_edit(self.clip, self.user, "changed")
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse("clip-review")).context["counts"]["pending"], 1)

    def test_closed_batch_stays_closed_for_retry(self):
        request_correction(self.edit, self.editor, "Исправьте")
        self.batch.is_open = False
        self.batch.save()
        self.assertEqual(submit_edit(self.clip, self.user, "retry")[0], "closed")
        self.assertIsNone(next_clip_for(self.user))

    def test_legacy_repair_does_not_erase_redo_after_reviewer_is_removed(self):
        request_correction(self.edit, self.editor, "Исправьте")
        self.editor.delete()
        call_command("enforce_manual_review", apply=True, stdout=io.StringIO())
        self.edit.refresh_from_db()
        self.assertEqual(self.edit.verdict, "redo")
        self.assertEqual(user_stats(self.user)["pending"], 0)
