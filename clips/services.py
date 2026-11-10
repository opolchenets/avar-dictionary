from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from gamification.models import PointLedger

from common.normalizer import char_errors, similarity, fix_palochka

from .models import Clip, ClipEdit, gold_is_correct, texts_match

POINTS_ACCEPTED = 1   # Only an explicit editorial decision can award points.


def next_clip_for(user, skip_clip_id=None):
    """Следующий фрагмент: открытая пачка, пользователь его ещё не правил, правок меньше двух."""
    redo = ClipEdit.objects.filter(user=user, verdict="redo", clip__batch__is_open=True).exclude(clip_id=skip_clip_id).order_by("reviewed_at", "pk").first()
    if redo:
        return redo.clip
    done_ids = ClipEdit.objects.filter(user=user).values_list("clip_id", flat=True)
    qs = (Clip.objects.filter(batch__is_open=True, status=Clip.Status.OPEN)
          .exclude(id__in=done_ids).exclude(pk=skip_clip_id).annotate(n=Count("edits")))
    # Фрагмент выбирается случайно из всех доступных: второго правщика подбирает случай,
    # поэтому пары постоянно меняются и договориться «править вдвоём» нельзя.
    return qs.order_by("?").first()


@transaction.atomic
def set_verdict(edit, verdict, by=None):
    if by is None or verdict not in (ClipEdit.Verdict.ACCEPTED, ClipEdit.Verdict.REJECTED, ClipEdit.Verdict.REDO):
        raise ValueError("A final verdict requires a named reviewer.")
    Clip.objects.select_for_update().get(pk=edit.clip_id)
    edit.verdict = verdict
    edit.reviewed_by, edit.reviewed_at = by, timezone.now()
    edit.save(update_fields=["verdict", "reviewed_by", "reviewed_at"])
    if verdict == ClipEdit.Verdict.ACCEPTED:
        PointLedger.objects.get_or_create(user=edit.user, reason=PointLedger.Reason.CLIP_ACCEPTED,
                                          clip=edit.clip, defaults={"points": POINTS_ACCEPTED})
    else:
        PointLedger.objects.filter(user=edit.user, reason=PointLedger.Reason.CLIP_ACCEPTED, clip=edit.clip).delete()


@transaction.atomic
def submit_edit(clip, user, text):
    clip = Clip.objects.select_for_update().get(pk=clip.pk)
    existing = ClipEdit.objects.filter(clip=clip, user=user).first()
    retry = existing is not None and existing.verdict == ClipEdit.Verdict.REDO
    if not clip.batch.is_open or (not retry and (clip.status != Clip.Status.OPEN or (existing and existing.verdict != ClipEdit.Verdict.PENDING))):
        return "closed", existing
    text = fix_palochka(text.strip())
    edit, _ = ClipEdit.objects.update_or_create(
        clip=clip, user=user,
        defaults={"text": text.strip(), "verdict": ClipEdit.Verdict.PENDING, "reviewed_by": None, "reviewed_at": None})
    if clip.is_gold:   # Control comparison is advisory, never a final verdict.
        edit.gold_score = similarity(text, clip.gold_text)
        edit.errors = char_errors(text, clip.gold_text)
        edit.save(update_fields=["gold_score", "errors"])
        return "saved", edit
    # Agreement/disagreement is only a hint for the reviewer.
    edits = list(clip.edits.filter(verdict=ClipEdit.Verdict.PENDING))
    if len(edits) >= Clip.REQUIRED_EDITS and clip.status == Clip.Status.OPEN:
        a, b = edits[0], edits[1]
        if texts_match(a.text, b.text):
            clip.status, clip.final_text = Clip.Status.AGREED, ""
            clip.save(update_fields=["status", "final_text", "updated_at"])
        else:
            clip.status = Clip.Status.DISPUTED
            clip.save(update_fields=["status", "updated_at"])
    return "saved", edit


@transaction.atomic
def accept_edit(edit, by):
    """Explicitly accept this contribution; other contributions stay unreviewed."""
    clip = Clip.objects.select_for_update().get(pk=edit.clip_id)
    edit.refresh_from_db()
    if clip.is_gold:
        # A manual exception applies to this contribution, never to other users
        # or to the reference used for future control submissions.
        set_verdict(edit, ClipEdit.Verdict.ACCEPTED, by)
        return
    clip.final_text, clip.status = fix_palochka(edit.text), Clip.Status.RESOLVED
    clip.save(update_fields=["final_text", "status", "updated_at"])
    set_verdict(edit, ClipEdit.Verdict.ACCEPTED, by)


@transaction.atomic
def _nonaccepted_edit(edit, by, verdict):
    clip = Clip.objects.select_for_update().get(pk=edit.clip_id)
    edit.refresh_from_db()
    was_final = not clip.is_gold and clip.final_text == fix_palochka(edit.text)
    set_verdict(edit, verdict, by)
    if was_final:
        approved = clip.edits.filter(verdict="accepted", reviewed_by__isnull=False).order_by("-reviewed_at", "-pk").first()
        clip.final_text = fix_palochka(approved.text) if approved else ""
        clip.status = Clip.Status.RESOLVED if approved else Clip.Status.OPEN
        clip.save(update_fields=["status", "final_text", "updated_at"])
    if not clip.is_gold and clip.status != Clip.Status.RESOLVED:
        pending = list(clip.edits.filter(verdict="pending"))
        clip.status = Clip.Status.OPEN
        if len(pending) >= Clip.REQUIRED_EDITS:
            clip.status = Clip.Status.AGREED if texts_match(pending[0].text, pending[1].text) else Clip.Status.DISPUTED
        clip.final_text = ""
        clip.save(update_fields=["status", "final_text", "updated_at"])


def reject_edit(edit, by):
    _nonaccepted_edit(edit, by, ClipEdit.Verdict.REJECTED)


@transaction.atomic
def request_correction(edit, by, note):
    note = note.strip()
    if not note or len(note) > 1000:
        raise ValueError("Напишите, что исправить: от 1 до 1000 символов.")
    _nonaccepted_edit(edit, by, ClipEdit.Verdict.REDO)
    edit.reviewer_note = note
    edit.save(update_fields=["reviewer_note"])


def matching_edit(clip, text):
    return next((e for e in clip.edits.select_related("user") if texts_match(e.text, text)), None)


@transaction.atomic
def resolve(clip, text, by=None):
    """Reviewer explicitly saves a final text and judges the submitted variants."""
    if by is None:
        raise ValueError("Saving a final text requires a named reviewer.")
    clip = Clip.objects.select_for_update().get(pk=clip.pk)
    if clip.is_gold:
        clip.gold_text = fix_palochka(text.strip())
        clip.save(update_fields=["gold_text", "updated_at"])
        reassess_gold_clip(clip)
        return
    clip.final_text, clip.status = fix_palochka(text.strip()), Clip.Status.RESOLVED
    clip.save(update_fields=["status", "final_text", "updated_at"])
    for e in clip.edits.all():
        set_verdict(e, ClipEdit.Verdict.ACCEPTED if texts_match(e.text, text) else ClipEdit.Verdict.REJECTED, by)


@transaction.atomic
def reassess_gold_clip(clip):
    """Refresh advisory scores only; final decisions are never made here."""
    clip = Clip.objects.select_for_update().get(pk=clip.pk)
    if not clip.is_gold:
        raise ValueError("Only control clips can be reassessed.")
    for edit in clip.edits.all():
        edit.errors = char_errors(edit.text, clip.gold_text)
        edit.gold_score = similarity(edit.text, clip.gold_text)
        edit.save(update_fields=["errors", "gold_score"])


def user_stats(user):
    q = ClipEdit.objects.filter(user=user)
    return {"total": q.count(),
            "accepted": q.filter(verdict="accepted", reviewed_by__isnull=False).count(),
            "rejected": q.filter(verdict="rejected", reviewed_by__isnull=False).count(),
            "redo": q.filter(verdict="redo").count(),
            "pending": q.exclude(verdict="redo").filter(Q(verdict="pending") | Q(reviewed_by__isnull=True)).count()}
