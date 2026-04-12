from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.views.generic import CreateView, TemplateView

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion
from .forms import SimpleSignUpForm

class SignUpView(CreateView):
    form_class = SimpleSignUpForm
    template_name = "accounts/signup.html"
    success_url = "/login/"


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
        return context


def forbidden_editor(request):
    if request.user.is_authenticated:
        return render(request, "accounts/editor_forbidden.html", status=403)
    return redirect_to_login(request.get_full_path())
