from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from gamification.models import PointLedger

from .models import Clip, ClipEdit, char_errors, gold_is_correct, normalize, similarity, texts_match

POINTS_ACCEPTED = 1   # очко начисляется только за принятую правку (редактором или алгоритмом для контрольных)


def next_clip_for(user):
    """Следующий фрагмент: открытая пачка, пользователь его ещё не правил, правок меньше двух."""
    done_ids = ClipEdit.objects.filter(user=user).values_list("clip_id", flat=True)
    qs = (Clip.objects.filter(batch__is_open=True, status=Clip.Status.OPEN)
          .exclude(id__in=done_ids))
    return qs.annotate(n=Count("edits")).order_by("-n", "id").first()


def set_verdict(edit, verdict, by=None):
    edit.verdict = verdict
    edit.reviewed_by, edit.reviewed_at = by, timezone.now()
    edit.save(update_fields=["verdict", "reviewed_by", "reviewed_at"])
    if verdict == ClipEdit.Verdict.ACCEPTED:
        PointLedger.objects.get_or_create(user=edit.user, reason=PointLedger.Reason.CLIP_ACCEPTED,
                                          clip=edit.clip, defaults={"points": POINTS_ACCEPTED})
        clip = edit.clip
        if not clip.is_gold and not clip.is_done and clip.status != Clip.Status.AGREED:
            clip.final_text, clip.status = edit.text, Clip.Status.RESOLVED
            clip.save(update_fields=["final_text", "status", "updated_at"])
    else:
        PointLedger.objects.filter(user=edit.user, reason=PointLedger.Reason.CLIP_ACCEPTED, clip=edit.clip).delete()
        clip = edit.clip
        if not clip.is_gold and clip.final_text == edit.text:
            other = clip.edits.filter(verdict=ClipEdit.Verdict.ACCEPTED).exclude(pk=edit.pk).first()
            if other:
                clip.final_text, clip.status = other.text, Clip.Status.RESOLVED
            else:   # итог больше не подтверждён — возвращаем фрагмент в работу
                n = clip.edits.count()
                clip.final_text = ""
                clip.status = Clip.Status.OPEN if n < Clip.REQUIRED_EDITS else Clip.Status.DISPUTED
            clip.save(update_fields=["final_text", "status", "updated_at"])


@transaction.atomic
def submit_edit(clip, user, text):
    clip = Clip.objects.select_for_update().get(pk=clip.pk)
    edit, _ = ClipEdit.objects.update_or_create(
        clip=clip, user=user,
        defaults={"text": text.strip(), "verdict": ClipEdit.Verdict.PENDING, "reviewed_by": None, "reviewed_at": None})
    if clip.is_gold:   # контрольный: оценивает алгоритм
        edit.gold_score = similarity(text, clip.gold_text)
        edit.errors = char_errors(text, clip.gold_text)
        edit.save(update_fields=["gold_score", "errors"])
        set_verdict(edit, ClipEdit.Verdict.ACCEPTED if gold_is_correct(text, clip.gold_text)
                    else ClipEdit.Verdict.REJECTED)
        return "saved", edit
    # Перекрёстная проверка: два правщика совпали (в пределах порога) — обе правки приняты автоматически,
    # иначе фрагмент уходит редакторам на перепроверку.
    edits = list(clip.edits.all())
    if len(edits) >= Clip.REQUIRED_EDITS and clip.status == Clip.Status.OPEN:
        a, b = edits[0], edits[1]
        if texts_match(a.text, b.text):
            clip.status, clip.final_text = Clip.Status.AGREED, a.text
            clip.save(update_fields=["status", "final_text", "updated_at"])
            for e in (a, b):
                set_verdict(e, ClipEdit.Verdict.ACCEPTED)
        else:
            clip.status = Clip.Status.DISPUTED
            clip.save(update_fields=["status", "updated_at"])
    return "saved", edit


def resolve(clip, text):
    """Редактор вписал итоговый текст сам: правки, совпавшие с ним, принимаются, остальные — отклоняются."""
    clip.final_text, clip.status = text.strip(), Clip.Status.RESOLVED
    clip.save(update_fields=["status", "final_text", "updated_at"])


def user_stats(user):
    q = ClipEdit.objects.filter(user=user)
    return {"total": q.count(),
            "accepted": q.filter(verdict="accepted").count(),
            "rejected": q.filter(verdict="rejected").count(),
            "pending": q.filter(verdict="pending").count()}
