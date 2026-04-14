import datetime
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Exists, OuterRef, Prefetch
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.db.models.functions import TruncDate
from django.views.generic import DetailView, ListView, TemplateView

from suggestions.models import SuggestionVote, TranslationSuggestion

from .forms import SentenceFilterForm, TranslationSubmissionForm
from .models import Category, Sentence, Terminology
from .services import TranslationWorkflowError, submit_translation


def get_safe_redirect(request, fallback):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
    ):
        return target
    return fallback


def build_suggestions_queryset(user):
    queryset = TranslationSuggestion.objects.select_related("author", "reviewed_by").annotate(
        vote_count=Count("votes", distinct=True),
    )
    if user.is_authenticated:
        vote_subquery = SuggestionVote.objects.filter(
            suggestion=OuterRef("pk"),
            user_id=user.pk,
        )
        return queryset.annotate(user_voted=Exists(vote_subquery))
    return queryset.annotate(user_voted=Value(False, output_field=BooleanField()))
class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_model = get_user_model()
        
        context["sentence_count"] = Sentence.objects.count()
        context["translated_count"] = Sentence.objects.filter(
            status=Sentence.Status.TRANSLATED
        ).count()
        context["pending_count"] = TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.PENDING
        ).count()
        context["user_count"] = user_model.objects.count()
        
        context["latest_translations"] = Sentence.objects.filter(
            status=Sentence.Status.TRANSLATED
        ).order_by("-updated_at")[:5]
        
        context["next_sentence"] = Sentence.objects.filter(
            status=Sentence.Status.UNTRANSLATED
        ).first() or Sentence.objects.order_by("id").first()
        
        context["leaders"] = (
            TranslationSuggestion.objects.filter(status=TranslationSuggestion.Status.ACCEPTED)
            .values("author__username", "author__profile__display_name")
            .annotate(
                total_points=Count("id"),
                accepted_count=Count("id"),
            )
            .order_by("-total_points", "author__username")[:5]
        )
        
        # Growth history for the chart
        history_raw = (
            Sentence.objects.filter(status=Sentence.Status.TRANSLATED)
            .annotate(date=TruncDate("updated_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        
        history_labels = []
        history_values = []
        cumulative = 0
        
        # If no history yet, or only one point, add a zero-start point
        if not history_raw:
            from django.utils import timezone
            import datetime
            history_labels = [(timezone.now() - datetime.timedelta(days=1)).strftime("%d.%m"), timezone.now().strftime("%d.%m")]
            history_values = [0, 0]
        else:
            # If only one day of history, add a leading zero point
            if len(history_raw) == 1:
                first_date = history_raw[0]["date"]
                if first_date:
                    history_labels.append((first_date - datetime.timedelta(days=1)).strftime("%d.%m"))
                    history_values.append(0)

            for entry in history_raw:
                if entry["date"]:
                    cumulative += entry["count"]
                    history_labels.append(entry["date"].strftime("%d.%m"))
                    history_values.append(cumulative)
        
        context["history_labels"] = history_labels
        context["history_values"] = history_values
        
        return context


class SentenceListView(ListView):
    model = Sentence
    template_name = "corpus/sentence_list.html"
    context_object_name = "sentences"
    paginate_by = 20

    def get_queryset(self):
        pending_suggestions = build_suggestions_queryset(self.request.user).filter(
            status=TranslationSuggestion.Status.PENDING
        ).order_by("-vote_count", "-created_at")
        queryset = Sentence.objects.select_related("translated_by", "category").prefetch_related(
            Prefetch(
                "suggestions",
                queryset=pending_suggestions,
                to_attr="pending_suggestions",
            )
        )
        self.filter_form = SentenceFilterForm(self.request.GET or None)

        if self.filter_form.is_valid():
            query = self.filter_form.cleaned_data.get("q")
            status = self.filter_form.cleaned_data.get("status") or "all"
            category = self.filter_form.cleaned_data.get("category")

            if query:
                queryset = queryset.filter(
                    Q(source_text_ru__icontains=query)
                    | Q(text_av__icontains=query)
                )
            if status != "all":
                queryset = queryset.filter(status=status)
            if category:
                queryset = queryset.filter(category=category)

        return queryset.annotate(
            untranslated_first=Case(
                When(status=Sentence.Status.UNTRANSLATED, then=Value(0)),
                When(status=Sentence.Status.PENDING, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by("untranslated_first", "id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        context["categories"] = Category.objects.all()
        
        current_category_slug = self.request.GET.get("category")
        if current_category_slug:
            context["current_category"] = Category.objects.filter(slug=current_category_slug).first()
            context["terms"] = Terminology.objects.filter(category__slug=current_category_slug)
        else:
            context["terms"] = Terminology.objects.none()

        context["total_count"] = Sentence.objects.count()
        context["translated_count"] = Sentence.objects.filter(
            status=Sentence.Status.TRANSLATED
        ).count()
        context["untranslated_count"] = Sentence.objects.filter(
            status=Sentence.Status.UNTRANSLATED
        ).count()
        context["pending_count"] = TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.PENDING
        ).count()
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.get_full_path()}")

        sentence_id = request.POST.get("sentence_id")
        form = TranslationSubmissionForm(request.POST)
        redirect_to = get_safe_redirect(request, reverse("sentence-list"))

        if not sentence_id:
            messages.error(request, "Не найдено предложение для перевода.")
            return redirect(redirect_to)

        if not form.is_valid():
            messages.error(request, "Введите перевод на аварский.")
            return redirect(redirect_to)

        translated_text = form.cleaned_data["text_av"].strip()
        try:
            message = submit_translation(
                user=request.user,
                sentence_id=sentence_id,
                translated_text=translated_text,
            )
        except TranslationWorkflowError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, message)

        return redirect(redirect_to)


class SentenceDetailView(DetailView):
    model = Sentence
    template_name = "corpus/sentence_detail.html"
    context_object_name = "sentence"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", TranslationSubmissionForm())
        suggestions = build_suggestions_queryset(self.request.user)
        context["pending_suggestions"] = suggestions.filter(
            status=TranslationSuggestion.Status.PENDING
        ).order_by("-vote_count", "-created_at")
        context["reviewed_suggestions"] = suggestions.exclude(
            status=TranslationSuggestion.Status.PENDING
        ).order_by("-created_at")
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")

        self.object = self.get_object()
        form = TranslationSubmissionForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        translated_text = form.cleaned_data["text_av"].strip()
        try:
            message = submit_translation(
                user=request.user,
                sentence_id=self.object.pk,
                translated_text=translated_text,
            )
        except TranslationWorkflowError as error:
            form.add_error("text_av", str(error))
            return self.render_to_response(self.get_context_data(form=form))
        else:
            messages.success(request, message)

        return redirect("sentence-detail", pk=self.object.pk)


class SuggestionVoteToggleView(View):
    def post(self, request, pk, suggestion_pk):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")

        suggestion = get_object_or_404(
            TranslationSuggestion,
            pk=suggestion_pk,
            sentence_id=pk,
        )
        if suggestion.status != TranslationSuggestion.Status.PENDING:
            messages.error(request, "Голосовать можно только за активные предложения.")
            return redirect(get_safe_redirect(request, reverse("sentence-detail", args=[pk])))

        vote, created = SuggestionVote.objects.get_or_create(
            suggestion=suggestion,
            user=request.user,
        )
        if created:
            messages.success(request, "Ваш голос учтён.")
        else:
            vote.delete()
            messages.success(request, "Голос снят.")

        return redirect(get_safe_redirect(request, reverse("sentence-detail", args=[pk])))
