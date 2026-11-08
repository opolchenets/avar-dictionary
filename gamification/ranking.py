"""
Внутренний рейтинг (на сайте не показывается, только задаёт порядок):

    score = M·m + k·N·n
    M — принятые правки текста, m — доля принятых правок
    N — минуты принятой озвучки, n — доля принятых озвучек
    k = 10

Новичкам (меньше SMOOTH_N оценённых работ) доля сглаживается к средней по сайту:
    m = (j·m_личн + (SMOOTH_N − j)·m_сайт) / SMOOTH_N,  j — сколько работ оценено.
«Переозвучить» в долю не входит — это второй шанс, а не ошибка.
"""
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum

from clips.models import ClipEdit
from reading.models import Recording

K = 10
SMOOTH_N = 10


def _smooth(acc, judged, site):
    if judged >= SMOOTH_N:
        return acc / judged
    own = acc / judged if judged else 0
    return (judged * own + (SMOOTH_N - judged) * site) / SMOOTH_N


def user_rows():
    User = get_user_model()
    ed = {r["user"]: r for r in ClipEdit.objects.values("user").annotate(
        acc=Count("id", filter=Q(verdict="accepted")),
        judged=Count("id", filter=Q(verdict__in=["accepted", "rejected"])))}
    rc = {r["user"]: r for r in Recording.objects.values("user").annotate(
        acc=Count("id", filter=Q(status="accepted")),
        judged=Count("id", filter=Q(status__in=["accepted", "rejected"])),
        sec=Sum("duration", filter=Q(status="accepted")))}
    e_acc = sum(r["acc"] for r in ed.values()); e_j = sum(r["judged"] for r in ed.values())
    r_acc = sum(r["acc"] for r in rc.values()); r_j = sum(r["judged"] for r in rc.values())
    site_m = e_acc / e_j if e_j else 0.8
    site_n = r_acc / r_j if r_j else 0.8
    rows = []
    for u in User.objects.filter(id__in=set(ed) | set(rc)).select_related(
            "profile", "profile__district", "profile__district__alliance"):
        e = ed.get(u.id, {"acc": 0, "judged": 0}); r = rc.get(u.id, {"acc": 0, "judged": 0, "sec": 0})
        M, N = e["acc"], (r["sec"] or 0) / 60
        score = M * _smooth(e["acc"], e["judged"], site_m) + K * N * _smooth(r["acc"], r["judged"], site_n)
        rows.append({
            "user": u, "name": getattr(getattr(u, "profile", None), "display_name", "") or u.username,
            "district": getattr(getattr(u, "profile", None), "district", None),
            "edits": M, "edits_pct": round(100 * e["acc"] / e["judged"]) if e["judged"] else None,
            "minutes": round(N, 1), "rec_pct": round(100 * r["acc"] / r["judged"]) if r["judged"] else None,
            "score": score})
    rows = [x for x in rows if x["edits"] or x["minutes"] or x["edits_pct"] is not None or x["rec_pct"] is not None]
    rows.sort(key=lambda x: (-x["score"], x["name"]))
    return rows


def group_rows(rows, key):
    g = defaultdict(lambda: {"edits": 0, "minutes": 0.0, "score": 0.0, "members": 0})
    for x in rows:
        d = x["district"]
        if not d:
            continue
        obj = d if key == "district" else d.alliance
        if obj is None:
            continue
        a = g[obj]; a["edits"] += x["edits"]; a["minutes"] += x["minutes"]; a["score"] += x["score"]; a["members"] += 1
    out = [{"obj": o, **v, "minutes": round(v["minutes"], 1)} for o, v in g.items()]
    out.sort(key=lambda x: -x["score"])
    return out
