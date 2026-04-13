import csv

from django.contrib import messages
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView

from accounts.permissions import EditorRequiredMixin
from corpus.forms import SentenceFilterForm
from corpus.models import Sentence
from gamification.models import PointLedger
from gamification.services import award_points
from suggestions.models import TranslationSuggestion

from .forms import SentenceEditForm, SentenceImportForm


class EditorDashboardView(EditorRequiredMixin, TemplateView):
    template_name = "editor/dashboard.html"

    def handle_no_permission(self):
        return redirect("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sentence_count"] = Sentence.objects.count()
        context["translated_count"] = Sentence.objects.filter(
            status=Sentence.Status.TRANSLATED
        ).count()
        context["pending_count"] = TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.PENDING
        ).count()
        context["latest_sentences"] = Sentence.objects.order_by("-created_at")[:10]
        return context


class EditorSentenceListView(EditorRequiredMixin, ListView):
    model = Sentence
    template_name = "editor/sentence_list.html"
    context_object_name = "sentences"
    paginate_by = 30

    def handle_no_permission(self):
        return redirect("home")

    def get_queryset(self):
        queryset = Sentence.objects.all()
        self.filter_form = SentenceFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get("q")
            status = self.filter_form.cleaned_data.get("status")
            if q:
                queryset = queryset.filter(source_text_ru__icontains=q)
            if status and status != "all":
                queryset = queryset.filter(status=status)
        return queryset.order_by("id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        return context

    def post(self, request, *args, **kwargs):
        sentence_id = request.POST.get("sentence_id")
        action = request.POST.get("action", "save")
        
        sentence = get_object_or_404(Sentence, pk=sentence_id)
        
        if action == "delete":
            sentence.delete()
            messages.success(request, f"Предложение #{sentence_id} полностью удалено.")
            return redirect(request.get_full_path())

        if action == "delete_translation":
            sentence.text_av = ""
            sentence.translated_by = None
            if sentence.suggestions.filter(status=TranslationSuggestion.Status.PENDING).exists():
                sentence.status = Sentence.Status.PENDING
            else:
                sentence.status = Sentence.Status.UNTRANSLATED
            sentence.save()
            messages.success(request, f"Перевод для предложения #{sentence_id} удалён.")
            return redirect(request.get_full_path())

        text_ru = request.POST.get("source_text_ru", "").strip()
        text_av = request.POST.get("text_av", "").strip()
        
        if text_ru:
            sentence.source_text_ru = text_ru
        
        if text_av:
            sentence.text_av = text_av
            sentence.status = Sentence.Status.TRANSLATED
            if not sentence.translated_by:
                sentence.translated_by = request.user
        else:
            sentence.text_av = ""
            if sentence.suggestions.filter(status=TranslationSuggestion.Status.PENDING).exists():
                sentence.status = Sentence.Status.PENDING
            else:
                sentence.status = Sentence.Status.UNTRANSLATED
            sentence.translated_by = None
            
        sentence.save()
        messages.success(request, f"Предложение #{sentence_id} обновлено.")
        return redirect(request.get_full_path())


class SentenceImportView(EditorRequiredMixin, FormView):
    template_name = "editor/import.html"
    form_class = SentenceImportForm
    success_url = reverse_lazy("editor-import")

    def handle_no_permission(self):
        return redirect("home")

    def form_valid(self, form):
        csv_file = form.cleaned_data.get("csv_file")
        raw_lines = form.cleaned_data.get("sentences", "").splitlines()
        
        prepared = []
        if csv_file:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.reader(decoded_file)
            for row in reader:
                if not row:
                    continue
                ru_text = row[0].strip() # Column 0 is RU
                if not ru_text:
                    continue
                av_text = row[1].strip() if len(row) > 1 else "" # Column 1 is AV
                prepared.append((ru_text, av_text))
        else:
            for line in raw_lines:
                clean_line = line.strip()
                if clean_line:
                    prepared.append((clean_line, ""))

        seen = set()
        unique_prepared = []
        for ru_text, av_text in prepared:
            if ru_text not in seen:
                seen.add(ru_text)
                unique_prepared.append((ru_text, av_text))

        existing = set(
            Sentence.objects.filter(source_text_ru__in=[item[0] for item in unique_prepared]).values_list(
                "source_text_ru", flat=True
            )
        )
        
        new_sentences = []
        for ru_text, av_text in unique_prepared:
            if ru_text not in existing:
                status = Sentence.Status.TRANSLATED if av_text else Sentence.Status.UNTRANSLATED
                new_sentences.append(
                    Sentence(
                        source_text_ru=ru_text,
                        text_av=av_text,
                        status=status,
                        translated_by=self.request.user if av_text else None
                    )
                )
                
        Sentence.objects.bulk_create(new_sentences)
        messages.success(
            self.request,
            f"Импортировано предложений: {len(new_sentences)}.",
        )
        return super().form_valid(form)


class SuggestionQueueView(EditorRequiredMixin, ListView):
    model = TranslationSuggestion
    template_name = "editor/suggestion_queue.html"
    context_object_name = "suggestions"
    paginate_by = 20

    def handle_no_permission(self):
        return redirect("home")

    def get_queryset(self):
        return TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.PENDING
        ).select_related(
            "sentence",
            "author",
            "reviewed_by",
        ).prefetch_related(
            "sentence__suggestions"
        ).annotate(
            vote_count=Count("votes", distinct=True)
        ).order_by("-vote_count", "-created_at")

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        
        if action in ("bulk_accept", "bulk_reject"):
            ids_str = request.POST.get("bulk_ids", "")
            ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
            if not ids:
                messages.error(request, "Не выбраны правки для массового действия.")
                return redirect("editor-suggestions")
            
            count = 0
            with transaction.atomic():
                suggestions = TranslationSuggestion.objects.filter(
                    pk__in=ids, status=TranslationSuggestion.Status.PENDING
                ).select_for_update().select_related("sentence", "author")
                
                for suggestion in suggestions:
                    if action == "bulk_accept":
                        suggestion.sentence.text_av = suggestion.proposed_text_av
                        suggestion.sentence.translated_by = suggestion.author
                        suggestion.sentence.status = Sentence.Status.TRANSLATED
                        suggestion.sentence.save(update_fields=["text_av", "translated_by", "status", "updated_at"])
                        suggestion.status = TranslationSuggestion.Status.ACCEPTED
                        suggestion.reviewed_by = request.user
                        suggestion.reviewed_at = timezone.now()
                        suggestion.save(update_fields=["status", "reviewed_by", "reviewed_at"])
                        award_points(
                            user=suggestion.author,
                            reason=PointLedger.Reason.SUGGESTION_ACCEPTED,
                            points=1,
                            sentence=suggestion.sentence,
                            suggestion=suggestion,
                        )
                    else:
                        suggestion.status = TranslationSuggestion.Status.REJECTED
                        suggestion.reviewed_by = request.user
                        suggestion.reviewed_at = timezone.now()
                        suggestion.save(update_fields=["status", "reviewed_by", "reviewed_at"])
                        if suggestion.sentence.status == Sentence.Status.PENDING and not suggestion.sentence.suggestions.filter(status=TranslationSuggestion.Status.PENDING).exists():
                            suggestion.sentence.status = Sentence.Status.UNTRANSLATED
                            suggestion.sentence.save(update_fields=["status", "updated_at"])
                    count += 1
            messages.success(request, f"Обработано правок: {count}.")
            return redirect("editor-suggestions")

        suggestion = get_object_or_404(TranslationSuggestion, pk=request.POST.get("id"))
        note = request.POST.get("editor_note", "").strip()
        edited_text = request.POST.get("edited_text", "").strip()

        if suggestion.status != TranslationSuggestion.Status.PENDING:
            messages.error(request, "Эта правка уже обработана.")
            return redirect("editor-suggestions")

        with transaction.atomic():
            suggestion = TranslationSuggestion.objects.select_for_update().select_related(
                "sentence",
                "author",
            ).get(pk=suggestion.pk)
            
            if edited_text and edited_text != suggestion.proposed_text_av:
                suggestion.proposed_text_av = edited_text
                suggestion.save(update_fields=["proposed_text_av"])

            if action == "accept":
                suggestion.sentence.text_av = suggestion.proposed_text_av
                suggestion.sentence.translated_by = suggestion.author
                suggestion.sentence.status = Sentence.Status.TRANSLATED
                suggestion.sentence.save(update_fields=["text_av", "translated_by", "status", "updated_at"])
                suggestion.status = TranslationSuggestion.Status.ACCEPTED
                suggestion.reviewed_by = request.user
                suggestion.reviewed_at = timezone.now()
                suggestion.editor_note = note
                suggestion.save(
                    update_fields=[
                        "status",
                        "reviewed_by",
                        "reviewed_at",
                        "editor_note",
                    ]
                )
                award_points(
                    user=suggestion.author,
                    reason=PointLedger.Reason.SUGGESTION_ACCEPTED,
                    points=1,
                    sentence=suggestion.sentence,
                    suggestion=suggestion,
                )
                messages.success(request, "Правка принята.")
            elif action == "reject":
                suggestion.status = TranslationSuggestion.Status.REJECTED
                suggestion.reviewed_by = request.user
                suggestion.reviewed_at = timezone.now()
                suggestion.editor_note = note
                suggestion.save(
                    update_fields=[
                        "status",
                        "reviewed_by",
                        "reviewed_at",
                        "editor_note",
                    ]
                )
                if suggestion.sentence.status == Sentence.Status.PENDING and not suggestion.sentence.suggestions.filter(status=TranslationSuggestion.Status.PENDING).exists():
                    suggestion.sentence.status = Sentence.Status.UNTRANSLATED
                    suggestion.sentence.save(update_fields=["status", "updated_at"])
                messages.success(request, "Правка отклонена.")
            else:
                messages.error(request, "Неизвестное действие.")

        return redirect("editor-suggestions")


class EditorSentenceDetailView(EditorRequiredMixin, TemplateView):
    template_name = "editor/sentence_detail.html"

    def handle_no_permission(self):
        return redirect("home")

    def dispatch(self, request, *args, **kwargs):
        self.sentence = get_object_or_404(
            Sentence,
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sentence"] = self.sentence
        context["sentence_form"] = kwargs.get("sentence_form") or SentenceEditForm(
            instance=self.sentence
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action == "save_sentence":
            sentence_form = SentenceEditForm(request.POST, instance=self.sentence)
            if sentence_form.is_valid():
                sentence = sentence_form.save(commit=False)
                if not sentence.text_av:
                    if self.sentence.suggestions.filter(status=TranslationSuggestion.Status.PENDING).exists():
                        sentence.status = Sentence.Status.PENDING
                    else:
                        sentence.status = Sentence.Status.UNTRANSLATED
                    sentence.translated_by = None
                else:
                    sentence.status = Sentence.Status.TRANSLATED
                    if not sentence.translated_by:
                        sentence.translated_by = request.user
                sentence.save()
                messages.success(request, "Предложение обновлено.")
                return redirect("editor-sentence-detail", pk=self.sentence.pk)
            return self.render_to_response(
                self.get_context_data(sentence_form=sentence_form)
            )

        if action == "delete_translation":
            self.sentence.text_av = ""
            self.sentence.translated_by = None
            if self.sentence.suggestions.filter(status=TranslationSuggestion.Status.PENDING).exists():
                self.sentence.status = Sentence.Status.PENDING
            else:
                self.sentence.status = Sentence.Status.UNTRANSLATED
            self.sentence.save()
            messages.success(request, "Перевод удалён.")
            return redirect("editor-sentence-detail", pk=self.sentence.pk)

        if action == "delete_sentence":
            self.sentence.delete()
            messages.success(request, "Предложение удалено.")
            return redirect("editor-sentences")

        messages.error(request, "Неизвестное действие.")
        return redirect("editor-sentence-detail", pk=self.sentence.pk)


class CorpusExportView(EditorRequiredMixin, TemplateView):
    def handle_no_permission(self):
        return redirect("home")

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="approved_corpus.csv"'

        writer = csv.writer(response)
        
        rows = Sentence.objects.filter(status=Sentence.Status.TRANSLATED).order_by("id")
        for sentence in rows:
            writer.writerow([sentence.source_text_ru, sentence.text_av])
            
        return response
