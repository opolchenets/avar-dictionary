from django.db import transaction
from corpus.views import get_safe_redirect
from .audio_validation import validate_audio
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.files.base import ContentFile
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from clips.views import is_editor

from .models import Consent, Prompt, Recording

MAX_SECONDS = 30


def next_prompt_for(user):
    """Фраза, у которой ещё нет принятой или ждущей проверки озвучки, и которую этот человек не читал."""
    mine = Recording.objects.filter(user=user).values_list("prompt_id", flat=True)
    busy = Recording.objects.filter(status__in=["accepted", "pending"]).values_list("prompt_id", flat=True)
    return (Prompt.objects.filter(is_active=True).exclude(id__in=mine).exclude(id__in=busy).order_by("id").first())


class ReadingHomeView(View):
    def get(self, request):
        ctx = {"total": Prompt.objects.filter(is_active=True).count(),
               "done": Prompt.objects.filter(recordings__status="accepted").distinct().count(),
               "minutes": round((Recording.objects.filter(status="accepted").aggregate(s=Sum("duration"))["s"] or 0) / 60, 1)}
        if request.user.is_authenticated:
            mine = Recording.objects.filter(user=request.user)
            ctx["my"] = {
                "total": mine.count(),
                "accepted": mine.filter(status="accepted").count(),
                "pending": mine.filter(status="pending").count(),
                "minutes": round((mine.filter(status="accepted").aggregate(s=Sum("duration"))["s"] or 0) / 60, 1),
            }
            ctx["redo"] = mine.filter(status="redo").select_related("prompt")
            ctx["recent"] = mine.select_related("prompt")[:10]
            ctx["pending_review"] = Recording.objects.filter(status="pending").count() if is_editor(request.user) else None
        return render(request, "reading/home.html", ctx)


class NextPromptView(LoginRequiredMixin, View):
    def get(self, request):
        p = next_prompt_for(request.user)
        if not p:
            messages.info(request, "Новых фраз для чтения пока нет — спасибо!")
            return redirect("reading-home")
        return redirect("reading-record", pk=p.pk)


class RecordView(LoginRequiredMixin, View):
    def get(self, request, pk):
        prompt = get_object_or_404(Prompt, pk=pk, is_active=True)
        mine = Recording.objects.filter(prompt=prompt, user=request.user).first()
        locked = mine is not None and mine.status != Recording.Status.REDO
        return render(request, "reading/record.html", {
            "prompt": prompt, "mine": mine, "locked": locked, "max_seconds": MAX_SECONDS,
            "need_consent": not Consent.objects.filter(user=request.user).exists()})

    def post(self, request, pk):
        prompt = get_object_or_404(Prompt, pk=pk, is_active=True)
        if not Consent.objects.filter(user=request.user).exists():
            if request.POST.get("consent") != "1":
                return JsonResponse({"error": "Нужно согласие"}, status=400)
            Consent.objects.create(user=request.user)
        try:
            content, dur, ext = validate_audio(request.FILES.get("audio"), request.POST.get("duration"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        new_name = None
        storage = Recording._meta.get_field("audio").storage
        try:
            with transaction.atomic():
                # Serialize submissions and editorial decisions for this phrase.
                Prompt.objects.select_for_update().get(pk=prompt.pk)
                rec = Recording.objects.filter(prompt=prompt, user=request.user).first()
                if rec and rec.status != Recording.Status.REDO:
                    return JsonResponse({"error": "Эта фраза уже озвучена"}, status=400)
                if not rec and Recording.objects.filter(prompt=prompt, status__in=["accepted", "pending"]).exists():
                    return JsonResponse({"error": "Эту фразу уже отправили на проверку. Выберите следующую."}, status=409)
                old_name = rec.audio.name if rec else None
                if rec:
                    rec.attempts += 1
                    rec.status, rec.note, rec.reviewed_by, rec.reviewed_at = Recording.Status.PENDING, "", None, None
                else:
                    rec = Recording(prompt=prompt, user=request.user)
                rec.duration = dur
                rec.audio.save(f"{prompt.pk}_{request.user.pk}.{ext}", ContentFile(content), save=False)
                new_name = rec.audio.name
                rec.save()
                if old_name and old_name != new_name:
                    transaction.on_commit(lambda name=old_name: storage.delete(name))
        except Exception:
            if new_name:
                storage.delete(new_name)
            raise
        n = Recording.objects.filter(user=request.user).count()
        messages.success(request, f"Запись отправлена на проверку. Вы озвучили фраз: {n}.")
        return JsonResponse({"next": reverse("reading-next")})


class ReviewView(UserPassesTestMixin, ListView):
    template_name = "reading/review.html"
    context_object_name = "recs"
    paginate_by = 30

    def test_func(self):
        return is_editor(self.request.user)

    def get_queryset(self):
        st = self.request.GET.get("status", "pending")
        return Recording.objects.filter(status=st).select_related("prompt", "user", "user__profile").order_by("updated_at")

    def get_context_data(self, **kw):
        c = super().get_context_data(**kw)
        c["status"] = self.request.GET.get("status", "pending")
        c["counts"] = {s: Recording.objects.filter(status=s).count() for s, _ in Recording.Status.choices}
        return c


class VerdictView(UserPassesTestMixin, View):
    def test_func(self):
        return is_editor(self.request.user)

    @transaction.atomic
    def post(self, request, pk):
        rec = get_object_or_404(Recording, pk=pk)
        Prompt.objects.select_for_update().get(pk=rec.prompt_id)
        rec.refresh_from_db()
        v = request.POST.get("verdict")
        if v in ("accepted", "redo", "rejected"):
            rec.status, rec.note = v, request.POST.get("note", "")[:255]
            rec.reviewed_by, rec.reviewed_at = request.user, timezone.now()
            rec.save(update_fields=["status", "note", "reviewed_by", "reviewed_at", "updated_at"])
        return redirect(get_safe_redirect(request, reverse("reading-review")))
