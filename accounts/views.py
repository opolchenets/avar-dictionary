from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.views.generic import CreateView, TemplateView

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion
from .forms import ProfileDisplayNameForm, SimpleSignUpForm

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

    def get_profile(self):
        profile, _ = UserProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"display_name": self.request.user.username},
        )
        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile = self.get_profile()
        accepted_count = TranslationSuggestion.objects.filter(
            author=user,
            status=TranslationSuggestion.Status.ACCEPTED,
        ).count()
        context["profile"] = profile
        context["profile_form"] = kwargs.get(
            "profile_form",
            ProfileDisplayNameForm(instance=profile, user=user),
        )
        context["total_points"] = accepted_count
        context["translations_count"] = Sentence.objects.filter(translated_by=user).count()
        context["suggestions_count"] = TranslationSuggestion.objects.filter(author=user).count()
        context["accepted_suggestions_count"] = accepted_count
        context["achievements"] = UserAchievement.objects.filter(user=user).select_related("achievement")
        return context

    def post(self, request, *args, **kwargs):
        profile = self.get_profile()
        form = ProfileDisplayNameForm(
            request.POST,
            instance=profile,
            user=request.user,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Никнейм обновлен.")
            return redirect("profile")

        return self.render_to_response(
            self.get_context_data(profile_form=form)
        )


def forbidden_editor(request):
    if request.user.is_authenticated:
        return render(request, "accounts/editor_forbidden.html", status=403)
    return redirect_to_login(request.get_full_path())
