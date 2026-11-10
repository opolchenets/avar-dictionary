from corpus.views import get_safe_redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q, Sum, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from .models import Batch, Clip, ClipEdit
from .services import accept_edit, matching_edit, next_clip_for, resolve, reject_edit, request_correction, submit_edit, user_stats


def is_editor(u):
    return u.is_authenticated and (u.is_staff or getattr(getattr(u, "profile", None), "is_editor", False)
                                    or getattr(getattr(u, "profile", None), "is_co_editor", False))


class ClipHomeView(View):
    """Раздел «Фрагменты»: сводка и кнопка «Следующий фрагмент»."""

    def get(self, request):
        total = Clip.objects.filter(is_gold=False).count()
        done = Clip.objects.filter(is_gold=False, status=Clip.Status.RESOLVED).count()
        ctx = {
            "total": total, "done": done, "left": total - done,
            "pending": ClipEdit.objects.exclude(verdict="redo").filter(Q(verdict="pending") | Q(reviewed_by__isnull=True)).count(),
            "batches": Batch.objects.filter(is_open=True).annotate(
                n=Count("clips", distinct=True),
                d=Count("clips", distinct=True, filter=Q(clips__status="resolved")
                        | Q(clips__is_gold=True, clips__edits__reviewed_by__isnull=False,
                            clips__edits__verdict__in=["accepted", "rejected"]))).filter(n__gt=0),
        }
        if request.user.is_authenticated:
            ctx["redo_edits"] = ClipEdit.objects.filter(user=request.user, verdict="redo").select_related("clip", "clip__batch")
            ctx["my"] = user_stats(request.user)
            ctx["recent"] = (ClipEdit.objects.filter(user=request.user).select_related("clip")
                             .order_by("-created_at")[:10])
        return render(request, "clips/clip_home.html", ctx)


class NextClipView(LoginRequiredMixin, View):
    def get(self, request):
        skipped = request.session.pop("skip_clip_once", None)
        clip = next_clip_for(request.user, skip_clip_id=skipped)
        if not clip:
            messages.info(request, "Свободных фрагментов пока нет — спасибо! Новая пачка скоро появится.")
            return redirect("clip-home")
        return redirect("clip-edit", pk=clip.pk)


class ClipEditView(LoginRequiredMixin, View):
    def get(self, request, pk):
        clip = get_object_or_404(Clip, pk=pk, batch__is_open=True)
        mine = ClipEdit.objects.filter(clip=clip, user=request.user).first()
        # править можно только открытый фрагмент; после решения (совпало / редактор) правка закрыта
        retry = mine is not None and mine.verdict == ClipEdit.Verdict.REDO
        locked = not retry and (clip.status != Clip.Status.OPEN or (mine is not None and mine.verdict != ClipEdit.Verdict.PENDING))
        return render(request, "clips/clip_edit.html", {
            "clip": clip, "mine": mine, "locked": locked,
            "text": mine.text if mine else clip.draft_text,
        })

    def post(self, request, pk):
        clip = get_object_or_404(Clip, pk=pk, batch__is_open=True)
        text = request.POST.get("text", "").strip()
        if request.POST.get("action") == "skip":
            request.session["skip_clip_once"] = clip.pk
            return redirect("clip-next")
        if not text:
            messages.error(request, "Текст пустой. Если в записи нет речи, напишите «#».")
            return redirect("clip-edit", pk=pk)
        mine = ClipEdit.objects.filter(clip=clip, user=request.user).first()
        retry = mine is not None and mine.verdict == ClipEdit.Verdict.REDO
        if not retry and (clip.status != Clip.Status.OPEN or (mine and mine.verdict != ClipEdit.Verdict.PENDING)):
            messages.info(request, "Этот фрагмент уже закрыт.")
            return redirect("clip-next")
        result, _ = submit_edit(clip, request.user, text)
        if result == "closed":
            messages.info(request, "Этот фрагмент уже закрыт.")
            return redirect("clip-next")
        n = ClipEdit.objects.filter(user=request.user).count()
        messages.success(request, f"Сохранено. Вы проверили фрагментов: {n}.")
        return redirect("clip-next")


class ReviewQueueView(UserPassesTestMixin, ListView):
    """Each submission remains pending until an explicit editorial verdict."""
    template_name = "clips/review_queue.html"
    context_object_name = "clips"
    paginate_by = 30

    def test_func(self):
        return is_editor(self.request.user)

    def selected_filters(self):
        status = self.request.GET.get("status", "pending")
        kind = self.request.GET.get("kind", "all")
        if status == "gold":  # Existing bookmarked URL, not a workflow stage.
            status, kind = "pending", "gold"
        if status == "resolved":
            status = "accepted"
        if status in ("agreed", "disputed", "open"):
            status = "pending"
        if status not in ("pending", "redo", "accepted", "rejected", "all"):
            status = "pending"
        if kind not in ("all", "gold", "new"):
            kind = "all"
        return status, kind

    def submissions(self):
        _, kind = self.selected_filters()
        edits = ClipEdit.objects.select_related("user", "user__profile", "reviewed_by")
        if kind != "all":
            edits = edits.filter(clip__is_gold=(kind == "gold"))
        return edits

    @staticmethod
    def by_status(edits, status):
        if status == "pending":
            return edits.exclude(verdict="redo").filter(Q(verdict="pending") | Q(reviewed_by__isnull=True))
        if status == "redo":
            return edits.filter(verdict="redo")
        if status in ("accepted", "rejected"):
            return edits.filter(verdict=status, reviewed_by__isnull=False)
        return edits

    def get_queryset(self):
        status, _ = self.selected_filters()
        edits = self.by_status(self.submissions(), status)
        return (Clip.objects.filter(edits__in=edits).distinct().select_related("batch")
                .prefetch_related(Prefetch("edits", queryset=edits, to_attr="review_edits")))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status, kind = self.selected_filters()
        edits = self.submissions()
        context.update(status=status, kind=kind,
            suggest=self.request.session.get("clip_suggest"),
            counts={state: self.by_status(edits, state).count()
                    for state in ("pending", "redo", "accepted", "rejected", "all")})
        return context


class ResolveView(UserPassesTestMixin, View):
    """Редактор вписал свой итоговый текст. Если он совпал с вариантом правщика — сайт предложит принять тот вариант."""

    def test_func(self):
        return is_editor(self.request.user)

    def post(self, request, pk):
        clip = get_object_or_404(Clip, pk=pk)
        text = request.POST.get("text", "").strip()
        back = get_safe_redirect(request, reverse("clip-review"))
        if not text:
            return redirect(back)
        if clip.is_gold:
            resolve(clip, text, request.user)
            messages.success(request, f"Фрагмент #{clip.pk}: эталон сохранён, предварительные подсказки обновлены. Решения редакторов сохранены.")
            return redirect(f"{back}#clip-{clip.pk}")
        m = matching_edit(clip, text)
        if m and not request.POST.get("force"):
            request.session["clip_suggest"] = {"clip": clip.pk, "edit": m.pk, "text": text}
            return redirect(f"{back}#clip-{clip.pk}")
        resolve(clip, text, request.user)
        request.session.pop("clip_suggest", None)
        messages.success(request, f"Фрагмент #{clip.pk}: записан ваш текст, правки участников отклонены.")
        return redirect(back)


class VerdictView(UserPassesTestMixin, View):
    """Принять вариант правщика (он становится итогом, остальные — отклонены) или отклонить правку."""

    def test_func(self):
        return is_editor(self.request.user)

    def post(self, request, pk):
        edit = get_object_or_404(ClipEdit, pk=pk)
        v = request.POST.get("verdict")
        if v == ClipEdit.Verdict.ACCEPTED:
            accept_edit(edit, request.user)
            messages.success(request, f"Фрагмент #{edit.clip_id}: принят вариант {edit.user.username}.")
        elif v == ClipEdit.Verdict.REJECTED:
            reject_edit(edit, request.user)
            messages.success(request, f"Фрагмент #{edit.clip_id}: правка {edit.user.username} отклонена редактором.")
        elif v == ClipEdit.Verdict.REDO:
            try:
                request_correction(edit, request.user, request.POST.get("note", ""))
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Фрагмент #{edit.clip_id}: правка возвращена участнику на исправление.")
        request.session.pop("clip_suggest", None)
        return redirect(get_safe_redirect(request, reverse("clip-review")))
