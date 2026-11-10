from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from gamification.models import PointLedger

from common.normalizer import char_errors, similarity, fix_palochka

from .models import Clip, ClipEdit, gold_is_correct, texts_match

POINTS_ACCEPTED = 1   # очко начисляется только за принятую правку (редактором или алгоритмом для контрольных)


def next_clip_for(user):
    """Следующий фрагмент: открытая пачка, пользователь его ещё не правил, правок меньше двух."""
    done_ids = ClipEdit.objects.filter(user=user).values_list("clip_id", flat=True)
    qs = (Clip.objects.filter(batch__is_open=True, status=Clip.Status.OPEN)
          .exclude(id__in=done_ids).annotate(n=Count("edits")))
    # Фрагмент выбирается случайно из всех доступных: второго правщика подбирает случай,
    # поэтому пары постоянно меняются и договориться «править вдвоём» нельзя.
    return qs.order_by("?").first()


@transaction.atomic
def set_verdict(edit, verdict, by=None):
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
    if not clip.batch.is_open or clip.status != Clip.Status.OPEN or (existing and existing.verdict != ClipEdit.Verdict.PENDING):
        return "closed", existing
    text = fix_palochka(text.strip())
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


@transaction.atomic
def accept_edit(edit, by):
    """Редактор выбрал вариант правщика: он — итог; совпадающие с ним правки приняты, остальные отклонены."""
    clip = Clip.objects.select_for_update().get(pk=edit.clip_id)
    clip.final_text, clip.status = fix_palochka(edit.text), Clip.Status.RESOLVED
    clip.save(update_fields=["final_text", "status", "updated_at"])
    for e in clip.edits.all():
        set_verdict(e, ClipEdit.Verdict.ACCEPTED if (e.pk == edit.pk or texts_match(e.text, edit.text))
                    else ClipEdit.Verdict.REJECTED, by)


def matching_edit(clip, text):
    return next((e for e in clip.edits.select_related("user") if texts_match(e.text, text)), None)


@transaction.atomic
def resolve(clip, text, by=None):
    """Редактор вписал свой текст: итог — его текст, все правки отклонены (совпадающие сюда не доходят)."""
    clip = Clip.objects.select_for_update().get(pk=clip.pk)
    clip.final_text, clip.status = fix_palochka(text.strip()), Clip.Status.RESOLVED
    clip.save(update_fields=["status", "final_text", "updated_at"])
    for e in clip.edits.all():
        set_verdict(e, ClipEdit.Verdict.ACCEPTED if texts_match(e.text, text) else ClipEdit.Verdict.REJECTED, by)


def user_stats(user):
    q = ClipEdit.objects.filter(user=user)
    return {"total": q.count(),
            "accepted": q.filter(verdict="accepted").count(),
            "rejected": q.filter(verdict="rejected").count(),
            "pending": q.filter(verdict="pending").count()}
