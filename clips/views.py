from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from .models import Batch, Clip, ClipEdit
from .services import next_clip_for, resolve, submit_edit, user_gold_accuracy


def is_editor(u):
    return u.is_authenticated and (u.is_staff or getattr(getattr(u, "profile", None), "is_editor", False))


class ClipHomeView(View):
    """Раздел «Фрагменты»: сводка и кнопка «Следующий фрагмент»."""

    def get(self, request):
        total = Clip.objects.filter(is_gold=False).count()
        done = Clip.objects.filter(is_gold=False, status__in=[Clip.Status.AGREED, Clip.Status.RESOLVED]).count()
        ctx = {
            "total": total, "done": done, "left": total - done,
            "disputed": Clip.objects.filter(status=Clip.Status.DISPUTED).count(),
            "batches": Batch.objects.filter(is_open=True).annotate(
                n=Count("clips", filter=Q(clips__is_gold=False)),
                d=Count("clips", filter=Q(clips__is_gold=False, clips__status__in=["agreed", "resolved"]))),
        }
        if request.user.is_authenticated:
            ctx["my_edits"] = ClipEdit.objects.filter(user=request.user).count()
            ctx["my_accuracy"], ctx["my_gold_n"] = user_gold_accuracy(request.user)
            ctx["recent"] = (ClipEdit.objects.filter(user=request.user).select_related("clip")
                             .order_by("-created_at")[:10])
        return render(request, "clips/clip_home.html", ctx)


class NextClipView(LoginRequiredMixin, View):
    def get(self, request):
        clip = next_clip_for(request.user)
        if not clip:
            messages.info(request, "Свободных фрагментов пока нет — спасибо! Новая пачка скоро появится.")
            return redirect("clip-home")
        return redirect("clip-edit", pk=clip.pk)


class ClipEditView(LoginRequiredMixin, View):
    def get(self, request, pk):
        clip = get_object_or_404(Clip, pk=pk)
        mine = ClipEdit.objects.filter(clip=clip, user=request.user).first()
        locked = clip.status != Clip.Status.OPEN and not mine
        return render(request, "clips/clip_edit.html", {
            "clip": clip, "mine": mine, "locked": locked,
            "text": mine.text if mine else clip.draft_text,
        })

    def post(self, request, pk):
        clip = get_object_or_404(Clip, pk=pk)
        text = request.POST.get("text", "").strip()
        if request.POST.get("action") == "skip":
            return redirect("clip-next")
        if not text:
            messages.error(request, "Текст пустой. Если в записи нет речи, напишите «#».")
            return redirect("clip-edit", pk=pk)
        if clip.status != Clip.Status.OPEN and not ClipEdit.objects.filter(clip=clip, user=request.user).exists():
            messages.info(request, "Этот фрагмент уже закрыт.")
            return redirect("clip-next")
        status, edit = submit_edit(clip, request.user, text)
        if status == Clip.Status.AGREED:
            messages.success(request, "Ваш текст совпал со вторым правщиком — фрагмент готов! +3 очка.")
        else:
            messages.success(request, "Сохранено. +1 очко.")
        return redirect("clip-next")


class ReviewQueueView(UserPassesTestMixin, ListView):
    """Редактор: фрагменты, где два правщика разошлись."""
    template_name = "clips/review_queue.html"
    context_object_name = "clips"
    paginate_by = 30

    def test_func(self):
        return is_editor(self.request.user)

    def get_queryset(self):
        st = self.request.GET.get("status", "disputed")
        qs = Clip.objects.prefetch_related("edits__user").select_related("batch")
        if st == "gold":
            return qs.filter(is_gold=True)
        return qs.filter(status=st)

    def get_context_data(self, **kw):
        c = super().get_context_data(**kw)
        c["status"] = self.request.GET.get("status", "disputed")
        c["counts"] = {s: Clip.objects.filter(status=s).count() for s in ["disputed", "open", "agreed", "resolved"]}
        c["counts"]["gold"] = Clip.objects.filter(is_gold=True).count()
        return c


class ResolveView(UserPassesTestMixin, View):
    def test_func(self):
        return is_editor(self.request.user)

    def post(self, request, pk):
        clip = get_object_or_404(Clip, pk=pk)
        text = request.POST.get("text", "").strip()
        if text:
            resolve(clip, text)
            messages.success(request, f"Фрагмент #{clip.pk} закрыт.")
        return redirect(request.POST.get("next") or "clip-review")
