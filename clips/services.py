from django.db import transaction

from gamification.models import PointLedger

from .models import Clip, ClipEdit, normalize, similarity

GOLD_OK = 0.97          # контрольный засчитан, если совпадение с эталоном ≥ 97 %
POINTS_EDIT, POINTS_AGREED, POINTS_GOLD = 1, 2, 2


def next_clip_for(user):
    """Следующий фрагмент: открытая пачка, пользователь его ещё не правил, правок меньше двух."""
    done_ids = ClipEdit.objects.filter(user=user).values_list("clip_id", flat=True)
    qs = (Clip.objects.filter(batch__is_open=True, status=Clip.Status.OPEN)
          .exclude(id__in=done_ids))
    # сначала фрагменты, где уже есть одна правка — чтобы быстрее закрывать
    from django.db.models import Count
    return qs.annotate(n=Count("edits")).order_by("-n", "id").first()


@transaction.atomic
def submit_edit(clip, user, text):
    clip = Clip.objects.select_for_update().get(pk=clip.pk)
    edit, _ = ClipEdit.objects.update_or_create(clip=clip, user=user, defaults={"text": text.strip()})
    PointLedger.objects.get_or_create(user=user, reason=PointLedger.Reason.CLIP_EDIT, clip=clip,
                                      defaults={"points": POINTS_EDIT})
    if clip.is_gold:
        edit.gold_score = similarity(text, clip.gold_text)
        edit.save(update_fields=["gold_score"])
        if edit.gold_score >= GOLD_OK:
            PointLedger.objects.get_or_create(user=user, reason=PointLedger.Reason.CLIP_GOLD, clip=clip,
                                              defaults={"points": POINTS_GOLD})
        return "gold", edit
    edits = list(clip.edits.all())
    if len(edits) >= Clip.REQUIRED_EDITS and clip.status == Clip.Status.OPEN:
        a, b = edits[0], edits[1]
        if normalize(a.text) == normalize(b.text):
            clip.status, clip.final_text = Clip.Status.AGREED, a.text
            for e in (a, b):
                PointLedger.objects.get_or_create(user=e.user, reason=PointLedger.Reason.CLIP_AGREED,
                                                  clip=clip, defaults={"points": POINTS_AGREED})
        else:
            clip.status = Clip.Status.DISPUTED
        clip.save(update_fields=["status", "final_text", "updated_at"])
    return clip.status, edit


def resolve(clip, text):
    clip.final_text, clip.status = text.strip(), Clip.Status.RESOLVED
    clip.save(update_fields=["status", "final_text", "updated_at"])
    for e in clip.edits.all():   # очки тем, кто угадал итог
        if normalize(e.text) == normalize(clip.final_text):
            PointLedger.objects.get_or_create(user=e.user, reason=PointLedger.Reason.CLIP_AGREED, clip=clip,
                                              defaults={"points": POINTS_AGREED})


def user_gold_accuracy(user):
    s = ClipEdit.objects.filter(user=user, clip__is_gold=True).values_list("gold_score", flat=True)
    s = [x for x in s if x is not None]
    return (sum(x >= GOLD_OK for x in s) / len(s), len(s)) if s else (None, 0)
