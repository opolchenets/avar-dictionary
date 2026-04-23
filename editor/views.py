import csv

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DeleteView, FormView, ListView, TemplateView

from accounts.permissions import (
    CoEditorRequiredMixin,
    EditorRequiredMixin,
    user_is_co_editor,
    user_is_editor,
)
from accounts.models import UserProfile
from corpus.forms import SentenceFilterForm
from corpus.models import Category, Sentence, Terminology
from corpus.services import (
    TranslationWorkflowError,
    normalize_avar_text,
    review_translation_suggestion,
    set_sentence_translation,
)
from suggestions.models import TranslationSuggestion

from .forms import (
    SentenceEditForm,
    SentenceImportForm,
    TerminologyForm,
    TerminologyImportForm,
)


def enrich_suggestion_author_stats(suggestions):
    for suggestion in suggestions:
        profile = getattr(suggestion.author, "profile", None)
        quality_score = 0.0
        accepted_count = 0
        display_name = suggestion.author.username

        if profile is not None:
            quality_score = profile.average_quality_score or 0.0
            accepted_count = profile.accepted_suggestions_count or 0
            display_name = profile.display_name or suggestion.author.username

        suggestion.author_display_name = display_name
        suggestion.author_quality_score = quality_score
        suggestion.author_accepted_suggestions_count = accepted_count
        suggestion.author_quality_percentage = int(quality_score * 100)


class TerminologyListView(EditorRequiredMixin, ListView):
    model = Terminology
    template_name = "editor/terminology_list.html"
    context_object_name = "terms"
    paginate_by = 50

    def get_queryset(self):
        queryset = Terminology.objects.all().select_related("category")
        category_slug = self.request.GET.get("category")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        context["form"] = TerminologyForm()
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "bulk_delete":
            ids_str = request.POST.get("bulk_ids", "")
            ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
            if ids:
                count, _ = Terminology.objects.filter(pk__in=ids).delete()
                messages.success(request, f"Удалено терминов: {count}.")
            else:
                messages.error(request, "Не выбраны термины для удаления.")
            return redirect("editor-terminology")

        form = TerminologyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Термин добавлен.")
        else:
            messages.error(request, "Ошибка при добавлении термина.")
        return redirect("editor-terminology")


class TerminologyImportView(EditorRequiredMixin, FormView):
    template_name = "editor/import_terminology.html"
    form_class = TerminologyImportForm
    success_url = reverse_lazy("editor-terminology")

    def form_valid(self, form):
        category = form.cleaned_data.get("category")
        csv_file = form.cleaned_data.get("csv_file")
        
        decoded_file = csv_file.read().decode("utf-8-sig").splitlines()
        reader = csv.reader(decoded_file)
        
        new_terms = []
        existing_ru = set(
            Terminology.objects.filter(category=category).values_list("word_ru", flat=True)
        )
        
        seen_in_file = set()
        for row in reader:
            if len(row) < 2:
                continue
            ru = row[0].strip()
            av = row[1].strip()
            if not ru or not av:
                continue
            
            if ru not in existing_ru and ru not in seen_in_file:
                new_terms.append(Terminology(category=category, word_ru=ru, word_av=av))
                seen_in_file.add(ru)
        
        Terminology.objects.bulk_create(new_terms)
        messages.success(self.request, f"Импортировано терминов: {len(new_terms)}.")
        return super().form_valid(form)


class EditorDashboardView(EditorRequiredMixin, TemplateView):
    template_name = "editor/dashboard.html"

    def handle_no_permission(self):
        if user_is_co_editor(self.request.user):
            return redirect("co-editor-dashboard")
        return redirect("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sentence_count"] = Sentence.objects.count()
        context["translated_count"] = Sentence.objects.filter(
            status=Sentence.Status.TRANSLATED
        ).count()
        context["pending_count"] = Sentence.objects.filter(
            suggestions__status=TranslationSuggestion.Status.PENDING
        ).distinct().count()
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
        queryset = Sentence.objects.all().select_related("category")
        self.filter_form = SentenceFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get("q")
            status = self.filter_form.cleaned_data.get("status")
            category = self.filter_form.cleaned_data.get("category")
            if q:
                queryset = queryset.filter(source_text_ru__icontains=q)
            if status and status != "all":
                queryset = queryset.filter(status=status)
            if category:
                queryset = queryset.filter(category=category)
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
            set_sentence_translation(sentence, translated_text="")
            sentence.save()
            messages.success(request, f"Перевод для предложения #{sentence_id} удалён.")
            return redirect(request.get_full_path())

        text_ru = request.POST.get("source_text_ru", "").strip()
        text_av = request.POST.get("text_av", "").strip()
        
        if text_ru:
            sentence.source_text_ru = text_ru

        set_sentence_translation(
            sentence,
            translated_text=text_av,
            fallback_translator=request.user,
        )
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
        category = form.cleaned_data.get("category")
        csv_format = form.cleaned_data.get("csv_format")
        
        prepared = []
        if csv_file:
            decoded_file = csv_file.read().decode("utf-8-sig").splitlines()
            if csv_format == "1col":
                for line in decoded_file:
                    clean_line = line.strip()
                    if clean_line:
                        prepared.append((clean_line, ""))
            else:
                reader = csv.reader(decoded_file)
                for row in reader:
                    if not row:
                        continue
                    ru_text = row[0].strip()
                    if not ru_text:
                        continue
                    av_text = row[1].strip() if len(row) > 1 else ""
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
                # Нормализуем русский текст (только точка и пробелы)
                from corpus.services import normalize_avar_text
                # Для русского просто убираем теги и ставим точку, палочки не трогаем
                clean_ru = ru_text.strip()
                if clean_ru and not clean_ru.endswith(('.', '!', '?', '»', '"')):
                    clean_ru += '.'
                
                # Для аварского используем полную нормализацию (с палочками и точками)
                clean_av = normalize_avar_text(av_text)
                
                status = Sentence.Status.TRANSLATED if clean_av else Sentence.Status.UNTRANSLATED
                new_sentences.append(
                    Sentence(
                        source_text_ru=clean_ru,
                        text_av=clean_av,
                        status=status,
                        category=category,
                        translated_by=self.request.user if clean_av else None,
                    )
                )
                
        Sentence.objects.bulk_create(new_sentences)
        messages.success(
            self.request,
            f"Импортировано предложений: {len(new_sentences)}.",
        )
        return super().form_valid(form)


class SuggestionQueueView(CoEditorRequiredMixin, ListView):
    model = Sentence
    template_name = "editor/suggestion_queue.html"
    context_object_name = "sentences"
    paginate_by = 10

    def handle_no_permission(self):
        return redirect("home")

    def get_queryset(self):
        from django.db.models import Prefetch
        
        # Подготавливаем отсортированный кверисет для правок
        sorted_suggestions = TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.PENDING
        ).select_related("author", "author__profile").annotate(
            v_count=Count("votes")
        ).order_by("-author__profile__average_quality_score", "-v_count", "-created_at")

        # Получаем предложения, у которых есть ожидающие правки, 
        # НО исключаем те, что уже официально переведены.
        return Sentence.objects.filter(
            suggestions__status=TranslationSuggestion.Status.PENDING
        ).exclude(status=Sentence.Status.TRANSLATED).distinct().prefetch_related(
            Prefetch("suggestions", queryset=sorted_suggestions, to_attr="pending_suggestions_list"),
            "suggestions__votes",
        ).annotate(
            pending_suggestion_count=Count(
                "suggestions",
                filter=Q(suggestions__status=TranslationSuggestion.Status.PENDING)
            )
        ).order_by("-pending_suggestion_count", "id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for sentence in context["sentences"]:
            enrich_suggestion_author_stats(sentence.pending_suggestions_list)
        context["user_is_full_editor"] = user_is_editor(self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action in ("bulk_accept", "bulk_reject"):
            # Для массовых действий теперь принимаем список ID правок
            ids_str = request.POST.get("bulk_ids", "")
            ids = [int(i) for i in ids_str.split(",") if i.isdigit()]
            if not ids:
                messages.error(request, "Не выбраны правки для массового действия.")
                return redirect("editor-suggestions")

            count = 0
            for suggestion_id in ids:
                try:
                    review_translation_suggestion(
                        suggestion_id=suggestion_id,
                        reviewer=request.user,
                        action="accept" if action == "bulk_accept" else "reject",
                    )
                except TranslationWorkflowError:
                    continue
                count += 1
            messages.success(request, f"Обработано правок: {count}.")
            return redirect("editor-suggestions")

        # Одиночное действие над правкой
        suggestion_id = request.POST.get("id")
        if not suggestion_id:
             messages.error(request, "Не указан ID правки.")
             return redirect("editor-suggestions")
             
        suggestion = get_object_or_404(TranslationSuggestion, pk=suggestion_id)
        note = request.POST.get("editor_note", "").strip()
        edited_text = request.POST.get("edited_text", "").strip()

        try:
            review_translation_suggestion(
                suggestion_id=suggestion.pk,
                reviewer=request.user,
                action=action,
                note=note,
                edited_text=edited_text,
            )
        except TranslationWorkflowError as error:
            messages.error(request, str(error))
        else:
            if action == "accept":
                messages.success(request, "Правка принята. Остальные правки этого предложения отклонены.")
            elif action == "reject":
                messages.success(request, "Правка отклонена.")
            else:
                messages.error(request, "Неизвестное действие.")

        return redirect("editor-suggestions")


class EditorSentenceDetailView(CoEditorRequiredMixin, TemplateView):
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
        context["user_is_full_editor"] = user_is_editor(self.request.user)
        context["sentence_form"] = kwargs.get("sentence_form") or SentenceEditForm(
            instance=self.sentence
        )
        pending_suggestions = self.sentence.suggestions.filter(
            status=TranslationSuggestion.Status.PENDING
        ).select_related("author", "author__profile").annotate(
            vote_count=Count("votes")
        ).order_by("-author__profile__average_quality_score", "-vote_count", "-created_at")
        enrich_suggestion_author_stats(pending_suggestions)
        context["pending_suggestions"] = pending_suggestions
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action in ("save_sentence", "delete_translation", "delete_sentence"):
            if not user_is_editor(request.user):
                messages.error(request, "Недостаточно прав.")
                return redirect("editor-sentence-detail", pk=self.sentence.pk)

        # Поддержка действий над правками в детальном виде
        if action in ("accept", "reject"):
            suggestion_id = request.POST.get("suggestion_id")
            suggestion = get_object_or_404(TranslationSuggestion, pk=suggestion_id, sentence=self.sentence)
            note = request.POST.get("editor_note", "").strip()
            edited_text = request.POST.get("edited_text", "").strip()
            
            try:
                review_translation_suggestion(
                    suggestion_id=suggestion.pk,
                    reviewer=request.user,
                    action=action,
                    note=note,
                    edited_text=edited_text,
                )
            except TranslationWorkflowError as error:
                messages.error(request, str(error))
            else:
                if action == "accept":
                    messages.success(request, "Правка принята.")
                else:
                    messages.success(request, "Правка отклонена.")
            return redirect("editor-sentence-detail", pk=self.sentence.pk)

        if action == "save_sentence":
            sentence_form = SentenceEditForm(request.POST, instance=self.sentence)
            if sentence_form.is_valid():
                sentence = sentence_form.save(commit=False)
                set_sentence_translation(
                    sentence,
                    translated_text=sentence.text_av,
                    fallback_translator=request.user,
                )
                sentence.save()
                messages.success(request, "Предложение обновлено.")
                return redirect("editor-sentence-detail", pk=self.sentence.pk)
            return self.render_to_response(
                self.get_context_data(sentence_form=sentence_form)
            )

        if action == "delete_translation":
            set_sentence_translation(self.sentence, translated_text="")
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

        queryset = Sentence.objects.filter(status=Sentence.Status.TRANSLATED)
        category_slug = request.GET.get("category")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        rows = queryset.order_by("id")
        for sentence in rows:
            writer.writerow([sentence.source_text_ru, sentence.text_av])

        return response


class CoEditorDashboardView(CoEditorRequiredMixin, TemplateView):
    template_name = "editor/co_editor_dashboard.html"

    def handle_no_permission(self):
        return redirect("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_count"] = TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.PENDING
        ).count()
        return context


class CoEditorAcceptedView(EditorRequiredMixin, ListView):
    model = TranslationSuggestion
    template_name = "editor/co_editor_accepted.html"
    context_object_name = "suggestions"
    paginate_by = 20

    def handle_no_permission(self):
        return redirect("home")

    def get_queryset(self):
        return TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.ACCEPTED,
            reviewer_role=TranslationSuggestion.ReviewerRole.CO_EDITOR,
        ).select_related(
            "sentence", "author", "author__profile",
            "reviewed_by", "reviewed_by__profile",
        ).order_by("-reviewed_at")

    def post(self, request, *args, **kwargs):
        suggestion = get_object_or_404(
            TranslationSuggestion,
            pk=request.POST.get("suggestion_id"),
            reviewer_role=TranslationSuggestion.ReviewerRole.CO_EDITOR,
            status=TranslationSuggestion.Status.ACCEPTED,
        )
        new_text = normalize_avar_text(request.POST.get("corrected_text", "").strip())
        if new_text:
            suggestion.proposed_text_av = new_text
            suggestion.save(update_fields=["proposed_text_av"])
            suggestion.sentence.text_av = new_text
            suggestion.sentence.save(update_fields=["text_av"])
            messages.success(request, "Перевод исправлен.")
        return redirect("editor-co-editor-accepted")


class CoEditorManageView(EditorRequiredMixin, TemplateView):
    template_name = "editor/co_editor_manage.html"

    def handle_no_permission(self):
        return redirect("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["co_editors"] = UserProfile.objects.filter(
            role=UserProfile.Role.CO_EDITOR
        ).select_related("user")
        context["contributors"] = UserProfile.objects.filter(
            role=UserProfile.Role.CONTRIBUTOR
        ).select_related("user").order_by("user__username")
        return context

    def post(self, request, *args, **kwargs):
        target = get_object_or_404(UserProfile, user_id=request.POST.get("user_id"))
        if target.is_editor:
            messages.error(request, "Нельзя изменить роль редактора или администратора.")
            return redirect("editor-co-editor-manage")
        action = request.POST.get("action")
        if action == "grant":
            target.role = UserProfile.Role.CO_EDITOR
        elif action == "revoke":
            target.role = UserProfile.Role.CONTRIBUTOR
        target.save(update_fields=["role"])
        messages.success(request, f"Роль обновлена: {target}")
        return redirect("editor-co-editor-manage")
