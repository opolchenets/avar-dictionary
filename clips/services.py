from fractions import Fraction

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from gamification.models import ArchivedRejection, PointLedger

from common.normalizer import char_errors, similarity, fix_palochka

from .models import AudioIssue, Clip, ClipEdit, ClipReviewEvent, comparison_text, texts_match

POINTS_ACCEPTED = 1


def approval_rates(edits, clip_id):
    user_ids = {edit.user_id for edit in edits}
    history = ClipEdit.objects.filter(user_id__in=user_ids).exclude(clip_id=clip_id)
    history = history.filter(verdict__in=["accepted", "rejected"]).filter(
        Q(reviewed_by__isnull=False) | Q(auto_accepted=True))
    counts = {
        row["user_id"]: [row["accepted"], row["judged"]]
        for row in history.values("user_id").annotate(
            accepted=Count("pk", filter=Q(verdict="accepted")), judged=Count("pk"))
    }
    archived = ArchivedRejection.objects.filter(kind="clip", user_id__in=user_ids).exclude(target_id=clip_id)
    for row in archived.values("user_id").annotate(total=Count("pk")):
        counts.setdefault(row["user_id"], [0, 0])[1] += row["total"]
    return {user_id: Fraction(accepted, judged) for user_id, (accepted, judged) in counts.items()}


def consensus_winners(edits, clip_id):
    if len(edits) != Clip.REQUIRED_EDITS:
        return []
    groups = {}
    for edit in edits:
        groups.setdefault(comparison_text(edit.text), []).append(edit)
    winners = max(groups.values(), key=len)
    if len(winners) == 1 or not comparison_text(winners[0].text).strip():
        return []
    rates = approval_rates(edits, clip_id)
    if len(winners) == 2:
        dissent = next(edit for edit in edits if edit not in winners)
        if len(rates) != 3 or rates[winners[0].user_id] * rates[winners[1].user_id] <= rates[dissent.user_id]:
            return []
    return sorted(winners, key=lambda edit: rates.get(edit.user_id, -1), reverse=True)


def preferred_accepted_edit(clip, text):
    approved = list(clip.edits.filter(verdict="accepted").filter(
        Q(reviewed_by__isnull=False) | Q(auto_accepted=True)).order_by("reviewed_at", "pk"))
    if not approved:
        return None
    equivalent = [edit for edit in approved if texts_match(edit.text, text)]
    if not equivalent:
        return approved[-1]
    first = equivalent[0]
    rates = approval_rates(equivalent, clip.pk)
    if first.user_id not in rates:
        return first
    best = max(equivalent, key=lambda edit: rates.get(edit.user_id, -1))
    return best if rates[best.user_id] - rates[first.user_id] >= Fraction(1, 5) else first


def next_clip_for(user, skip_clip_id=None):
    """Prioritize unfinished clips the participant has not answered."""
    redo = ClipEdit.objects.filter(user=user, verdict="redo", clip__batch__is_open=True).exclude(clip_id=skip_clip_id).order_by("reviewed_at", "pk").first()
    if redo:
        return redo.clip
    answered = ClipEdit.objects.filter(user=user).values("clip_id")
    return (Clip.objects.filter(batch__is_open=True)
            .filter(Q(status=Clip.Status.OPEN) | Q(status=Clip.Status.RESOLVED, collect_after_accept=True))
            .exclude(audio="").exclude(pk=skip_clip_id).exclude(pk__in=answered)
            .exclude(pk__in=AudioIssue.objects.filter(reviewed_at__isnull=True).values("clip_id"))
            .annotate(answer_count=Count("edits"))
            .filter(answer_count__lt=Clip.REQUIRED_EDITS)
            .order_by("-answer_count", "pk").first())


def can_submit(clip, existing):
    if not clip.batch.is_open or not clip.audio:
        return False
    if existing and existing.verdict == ClipEdit.Verdict.REDO:
        return True
    if clip.status != Clip.Status.OPEN and not (
        clip.status == Clip.Status.RESOLVED and clip.collect_after_accept
    ):
        return False
    if existing:
        return existing.verdict == ClipEdit.Verdict.PENDING
    return (clip.edits.count() < Clip.REQUIRED_EDITS
            and not clip.audio_issues.filter(reviewed_at__isnull=True).exists())


@transaction.atomic
def set_verdict(edit, verdict, by=None):
    if by is None or verdict not in (ClipEdit.Verdict.ACCEPTED, ClipEdit.Verdict.REJECTED, ClipEdit.Verdict.REDO):
        raise ValueError("A final verdict requires a named reviewer.")
    Clip.objects.select_for_update().get(pk=edit.clip_id)
    if verdict == edit.verdict == ClipEdit.Verdict.ACCEPTED and edit.reviewed_by_id is not None:
        return
    edit.verdict = verdict
    edit.auto_accepted = False
    edit.reviewed_by, edit.reviewed_at = by, timezone.now()
    edit.save(update_fields=["verdict", "auto_accepted", "reviewed_by", "reviewed_at"])
    if verdict == ClipEdit.Verdict.ACCEPTED:
        ClipReviewEvent.objects.create(
            clip_number=edit.clip_id, edit_number=edit.pk, reviewer_name=by.get_username(),
            action=ClipReviewEvent.Action.ACCEPT, text=edit.text, decided_at=edit.reviewed_at,
        )
        PointLedger.objects.get_or_create(user=edit.user, reason=PointLedger.Reason.CLIP_ACCEPTED,
                                          clip=edit.clip, defaults={"points": POINTS_ACCEPTED})
    else:
        PointLedger.objects.filter(user=edit.user, reason=PointLedger.Reason.CLIP_ACCEPTED, clip=edit.clip).delete()


@transaction.atomic
def submit_edit(clip, user, text):
    clip = Clip.objects.select_for_update().get(pk=clip.pk)
    existing = ClipEdit.objects.filter(clip=clip, user=user).first()
    if not can_submit(clip, existing):
        return "closed", existing
    text = fix_palochka(text)
    edit, _ = ClipEdit.objects.update_or_create(
        clip=clip, user=user,
        defaults={"text": text, "verdict": ClipEdit.Verdict.PENDING, "reviewed_by": None, "reviewed_at": None})
    if clip.is_gold:   # Control comparison is advisory, never a final verdict.
        edit.gold_score = similarity(text, clip.gold_text)
        edit.errors = char_errors(text, clip.gold_text)
        edit.save(update_fields=["gold_score", "errors"])
    edits = list(clip.edits.all())
    if len(edits) >= Clip.REQUIRED_EDITS:
        clip.collect_after_accept = False
        if clip.status == Clip.Status.OPEN:
            if clip.is_gold:
                clip.status = Clip.Status.DISPUTED
                clip.save(update_fields=["status", "collect_after_accept", "updated_at"])
            else:
                pending = [candidate for candidate in edits if candidate.verdict == ClipEdit.Verdict.PENDING]
                winning = [] if clip.audio_issues.filter(reviewed_at__isnull=True).exists() else consensus_winners(pending, clip.pk)
                if winning:
                    clip.final_text, clip.status = winning[0].text, Clip.Status.RESOLVED
                    clip.save(update_fields=["final_text", "status", "collect_after_accept", "updated_at"])
                    for candidate in winning:
                        candidate.verdict = ClipEdit.Verdict.ACCEPTED
                        candidate.auto_accepted = True
                        candidate.reviewed_at = timezone.now()
                        candidate.save(update_fields=["verdict", "auto_accepted", "reviewed_at"])
                        PointLedger.objects.get_or_create(user=candidate.user, reason=PointLedger.Reason.CLIP_ACCEPTED,
                                                          clip=clip, defaults={"points": POINTS_ACCEPTED})
                else:
                    clip.status = Clip.Status.DISPUTED
                    clip.save(update_fields=["status", "collect_after_accept", "updated_at"])
        else:
            clip.save(update_fields=["collect_after_accept", "updated_at"])
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
    set_verdict(edit, ClipEdit.Verdict.ACCEPTED, by)
    if clip.status == Clip.Status.OPEN:
        clip.collect_after_accept = clip.edits.count() < Clip.REQUIRED_EDITS
    winner = preferred_accepted_edit(clip, edit.text)
    clip.final_text, clip.status = winner.text, Clip.Status.RESOLVED
    clip.save(update_fields=["final_text", "status", "collect_after_accept", "updated_at"])


@transaction.atomic
def _nonaccepted_edit(edit, by, verdict):
    clip = Clip.objects.select_for_update().get(pk=edit.clip_id)
    edit.refresh_from_db()
    was_final = not clip.is_gold and clip.final_text == fix_palochka(edit.text)
    set_verdict(edit, verdict, by)
    if was_final:
        approved = preferred_accepted_edit(clip, edit.text)
        clip.final_text = fix_palochka(approved.text) if approved else ""
        clip.status = Clip.Status.RESOLVED if approved else Clip.Status.OPEN
        clip.save(update_fields=["status", "final_text", "updated_at"])
    if not clip.is_gold and clip.status != Clip.Status.RESOLVED:
        answer_count = clip.edits.count()
        clip.status = Clip.Status.DISPUTED if answer_count >= Clip.REQUIRED_EDITS else Clip.Status.OPEN
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
    text = fix_palochka(text.strip())
    previous = clip.gold_text if clip.is_gold else clip.final_text
    if previous != text or (not clip.is_gold and clip.status != Clip.Status.RESOLVED):
        ClipReviewEvent.objects.create(
            clip_number=clip.pk, reviewer_name=by.get_username(),
            action=ClipReviewEvent.Action.GOLD if clip.is_gold else ClipReviewEvent.Action.FINAL,
            previous_text=previous, text=text, decided_at=timezone.now(),
        )
    if clip.is_gold:
        clip.gold_text = text
        clip.save(update_fields=["gold_text", "updated_at"])
        reassess_gold_clip(clip)
        return
    clip.final_text, clip.status = text, Clip.Status.RESOLVED
    clip.collect_after_accept = False
    clip.save(update_fields=["status", "final_text", "collect_after_accept", "updated_at"])
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
            "accepted": q.filter(verdict="accepted").count(),
            "rejected": q.filter(verdict="rejected", reviewed_by__isnull=False).count(),
            "redo": q.filter(verdict="redo").count(),
            "pending": q.exclude(verdict="redo").filter(
                Q(verdict="pending") | Q(reviewed_by__isnull=True, auto_accepted=False)).count()}
