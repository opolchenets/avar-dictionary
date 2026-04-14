import re
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from gamification.models import PointLedger
from gamification.services import award_points
from suggestions.models import TranslationSuggestion

from .models import Sentence


class TranslationWorkflowError(Exception):
    pass


def normalize_avar_text(text: str) -> str:
    if not text:
        return ""
    
    # 1. Базовая очистка от лишних пробелов и HTML (защита от XSS на бэкенде)
    text = strip_tags(text).strip()
    
    # 2. Замена технических символов на правильную аварскую орфографию
    # Заменяем цифру 1 или латинскую I/l на кириллическую палочку Ӏ
    # (часто используется в аварском для обозначения гортанных смычных)
    text = re.sub(r'[1Il]', 'Ӏ', text)
    
    # 3. Принудительная точка в конце предложения
    if text and not text.endswith(('.', '!', '?', '»', '"')):
        text += '.'
        
    return text


def set_sentence_translation(
    sentence: Sentence,
    *,
    translated_text: str,
    translated_by=None,
    fallback_translator=None,
) -> Sentence:
    cleaned_text = normalize_avar_text(translated_text)
    sentence.text_av = cleaned_text

    if cleaned_text:
        sentence.status = Sentence.Status.TRANSLATED
        if translated_by is not None:
            sentence.translated_by = translated_by
        elif sentence.translated_by is None and fallback_translator is not None:
            sentence.translated_by = fallback_translator
        return sentence

    sentence.translated_by = None
    has_pending_suggestions = sentence.suggestions.filter(
        status=TranslationSuggestion.Status.PENDING
    ).exists()
    sentence.status = (
        Sentence.Status.PENDING
        if has_pending_suggestions
        else Sentence.Status.UNTRANSLATED
    )
    return sentence


@transaction.atomic
def submit_translation(*, user, sentence_id: int, translated_text: str) -> str:
    cleaned_text = normalize_avar_text(translated_text)
    if not cleaned_text:
        raise TranslationWorkflowError("Текст перевода не может быть пустым.")

    sentence = Sentence.objects.select_for_update().get(pk=sentence_id)

    if sentence.text_av and sentence.text_av == cleaned_text:
        raise TranslationWorkflowError("Этот перевод уже является основным.")

    duplicate = sentence.suggestions.filter(
        proposed_text_av__iexact=cleaned_text
    ).exists()
    if duplicate:
        raise TranslationWorkflowError(
            "Такой вариант уже предложен. Лучше проголосуйте за него."
        )

    TranslationSuggestion.objects.create(
        sentence=sentence,
        proposed_text_av=cleaned_text,
        author=user,
    )

    if not sentence.text_av:
        set_sentence_translation(sentence, translated_text="")
        sentence.save()

    return "Перевод на аварский отправлен редактору на проверку."


@transaction.atomic
def review_translation_suggestion(
    *,
    suggestion_id: int,
    reviewer,
    action: str,
    note: str = "",
    edited_text: str = "",
) -> TranslationSuggestion:
    suggestion = (
        TranslationSuggestion.objects.select_for_update()
        .select_related("sentence", "author")
        .get(pk=suggestion_id)
    )

    if suggestion.status != TranslationSuggestion.Status.PENDING:
        raise TranslationWorkflowError("Эта правка уже обработана.")

    # Если редактор правил текст вручную при проверке - нормализуем и его
    cleaned_text = normalize_avar_text(edited_text)
    if cleaned_text and cleaned_text != suggestion.proposed_text_av:
        suggestion.proposed_text_av = cleaned_text
        suggestion.save(update_fields=["proposed_text_av"])

    suggestion.reviewed_by = reviewer
    suggestion.reviewed_at = timezone.now()
    suggestion.editor_note = note

    if action == "accept":
        set_sentence_translation(
            suggestion.sentence,
            translated_text=suggestion.proposed_text_av,
            translated_by=suggestion.author,
        )
        suggestion.sentence.save()
        suggestion.status = TranslationSuggestion.Status.ACCEPTED
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
        return suggestion

    if action == "reject":
        suggestion.status = TranslationSuggestion.Status.REJECTED
        suggestion.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "editor_note",
            ]
        )
        # Просто пересчитываем статус предложения (вдруг там есть другие правки)
        set_sentence_translation(
            suggestion.sentence,
            translated_text=suggestion.sentence.text_av,
        )
        suggestion.sentence.save()
        return suggestion

    raise TranslationWorkflowError("Неизвестное действие.")
