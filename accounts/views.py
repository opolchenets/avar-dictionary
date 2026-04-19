from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import CreateView, TemplateView
from django.urls import reverse_lazy
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
import datetime

from .forms import ProfileDisplayNameForm, SimpleSignUpForm
from .models import UserProfile, Notification
from gamification.models import UserAchievement

User = get_user_model()

@login_required
@require_POST
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok"})


class SignUpView(CreateView):
    form_class = SimpleSignUpForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            user = self.object
            district = form.cleaned_data.get("district")
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.district = district
            profile.save()
            return response


def get_user_profile_data(user):
    from suggestions.models import TranslationSuggestion
    from corpus.models import Sentence

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"display_name": user.username},
    )
    
    # Все принятые правки
    accepted_suggestions_qs = TranslationSuggestion.objects.filter(
        author=user,
        status=TranslationSuggestion.Status.ACCEPTED,
    ).select_related("sentence").order_by("-created_at")
    
    accepted_count = accepted_suggestions_qs.count()
    
    # Данные для графика активности (за последний год)
    one_year_ago = timezone.now() - datetime.timedelta(days=365)
    activity_data = (
        TranslationSuggestion.objects.filter(author=user, created_at__gte=one_year_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    
    activity_dict = {item["date"].isoformat() if item["date"] else "": item["count"] for item in activity_data}
    
    # Расчет стриков
    today = timezone.now().date()
    current_streak = 0
    max_streak = 0
    temp_streak = 0
    
    check_date = today
    if today.isoformat() not in activity_dict:
        yesterday = today - datetime.timedelta(days=1)
        if yesterday.isoformat() in activity_dict:
            check_date = yesterday
    
    for i in range(365):
        d = check_date - datetime.timedelta(days=i)
        if d.isoformat() in activity_dict:
            current_streak += 1
        else:
            break
    
    sorted_dates_asc = sorted([item["date"] for item in activity_data if item["date"]])
    if sorted_dates_asc:
        prev_date = None
        for d in sorted_dates_asc:
            if prev_date and (d - prev_date).days == 1:
                temp_streak += 1
            else:
                temp_streak = 1
            max_streak = max(max_streak, temp_streak)
            prev_date = d

    grid_dates = []
    start_grid = today - datetime.timedelta(days=364)
    for i in range(365):
        current_date = start_grid + datetime.timedelta(days=i)
        iso = current_date.isoformat()
        grid_dates.append({
            'date': iso,
            'count': activity_dict.get(iso, 0),
        })

    return {
        "profile": profile,
        "total_points": accepted_count,
        "translations_count": Sentence.objects.filter(translated_by=user).count(),
        "suggestions_count": TranslationSuggestion.objects.filter(author=user).count(),
        "accepted_suggestions_count": accepted_count,
        "achievements": UserAchievement.objects.filter(user=user).select_related("achievement"),
        "activity_grid": grid_dates,
        "current_streak": current_streak,
        "max_streak": max_streak,
        "accepted_suggestions": accepted_suggestions_qs,
    }

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        from suggestions.models import TranslationSuggestion
        context = super().get_context_data(**kwargs)
        user = self.request.user
        data = get_user_profile_data(user)
        context.update(data)
        
        context["target_user"] = user
        context["is_own_profile"] = True
        context["profile_form"] = kwargs.get(
            "profile_form",
            ProfileDisplayNameForm(instance=data["profile"], user=user),
        )
        
        # Только для своего профиля показываем те, что на проверке
        context["pending_suggestions"] = TranslationSuggestion.objects.filter(
            author=user,
            status=TranslationSuggestion.Status.PENDING
        ).select_related("sentence").order_by("-created_at")
        
        return context

    def post(self, request, *args, **kwargs):
        profile = get_object_or_404(UserProfile, user=request.user)
        form = ProfileDisplayNameForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Никнейм обновлен.")
            return redirect("profile")
        return self.render_to_response(self.get_context_data(profile_form=form))

class PublicProfileView(TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get("pk")
        user = get_object_or_404(User, pk=pk)
        
        # Если это я сам, перенаправляем на обычный профиль или просто ставим флаг
        if self.request.user.is_authenticated and self.request.user == user:
            context["is_own_profile"] = True
        else:
            context["is_own_profile"] = False

        data = get_user_profile_data(user)
        context.update(data)
        context["target_user"] = user
        return context


def forbidden_editor(request):
    if request.user.is_authenticated:
        return render(request, "accounts/editor_forbidden.html", status=403)
    return redirect_to_login(request.get_full_path())
