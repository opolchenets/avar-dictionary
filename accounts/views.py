from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.views.generic import CreateView, TemplateView

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion
from .forms import SimpleSignUpForm

from django.urls import reverse_lazy
from django.db import transaction
from gamification.models import UserAchievement
from .models import UserProfile

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


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        accepted_count = TranslationSuggestion.objects.filter(
            author=user,
            status=TranslationSuggestion.Status.ACCEPTED,
        ).count()
        context["total_points"] = accepted_count
        context["translations_count"] = Sentence.objects.filter(translated_by=user).count()
        context["suggestions_count"] = TranslationSuggestion.objects.filter(author=user).count()
        context["accepted_suggestions_count"] = accepted_count
        context["achievements"] = UserAchievement.objects.filter(user=user).select_related("achievement")
        return context


def forbidden_editor(request):
    if request.user.is_authenticated:
        return render(request, "accounts/editor_forbidden.html", status=403)
    return redirect_to_login(request.get_full_path())
