from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from .audio import decode_trial
from .client import AsrUnavailable, recognize
from .models import AsrTrial


@method_decorator(never_cache, name="dispatch")
class AsrDemoView(LoginRequiredMixin, View):
    template_name = "asr_demo/demo.html"

    def context(self, request, **extra):
        since = timezone.now() - timedelta(hours=24)
        used = AsrTrial.objects.filter(user=request.user, created_at__gte=since).count()
        latest = AsrTrial.objects.filter(user=request.user, status=AsrTrial.Status.READY).first()
        return {
            "limit": settings.ASR_TRIAL_DAILY_LIMIT,
            "used": used,
            "remaining": max(0, settings.ASR_TRIAL_DAILY_LIMIT - used),
            "latest": latest,
            "service_configured": bool(settings.ASR_SERVICE_URL and len(settings.ASR_INTERNAL_TOKEN) >= 32),
            **extra,
        }

    def get(self, request):
        return render(request, self.template_name, self.context(request))

    def post(self, request):
        try:
            pcm, duration = decode_trial(request.FILES.get("audio"), recording=request.POST.get("input_kind") == "recording")
        except ValueError as exc:
            return render(request, self.template_name, self.context(request, error=str(exc)), status=400)

        since = timezone.now() - timedelta(hours=24)
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            used = AsrTrial.objects.filter(user=request.user, created_at__gte=since).count()
            if used >= settings.ASR_TRIAL_DAILY_LIMIT:
                return render(request, self.template_name,
                              self.context(request, error="Лимит исчерпан. Новая попытка появится через 24 часа."),
                              status=429)
            trial = AsrTrial(user=request.user, duration=duration)
            trial.save()

        try:
            text, version = recognize(pcm)
        except AsrUnavailable as exc:
            trial.status = AsrTrial.Status.FAILED
            trial.save(update_fields=("status",))
            return render(request, self.template_name, self.context(request, error=str(exc)), status=503)

        trial.result_text = text
        trial.model_version = version
        trial.status = AsrTrial.Status.READY
        trial.save(update_fields=("result_text", "model_version", "status"))
        return render(request, self.template_name, self.context(request, result=trial))
