import re
import difflib
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from gamification.models import PointLedger
from gamification.services import award_points
from suggestions.models import TranslationSuggestion

from .models import Sentence


class TranslationWorkflowError(Exception):
    pass


def get_or_create_user_profile(user):
    from accounts.models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"display_name": user.get_username()},
    )
    if profile.average_quality_score is None:
        profile.average_quality_score = 0.0
    if profile.accepted_suggestions_count is None:
        profile.accepted_suggestions_count = 0
    return profile


def normalize_avar_text(text: str) -> str:
    if not text:
        return ""
    
    # 1. Базовая очистка от лишних пробелов и HTML (защита от XSS на бэкенде)
    text = strip_tags(text).strip()
    
    # 2. Замена технических символов на правильную аварскую орфографию
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

    if sentence.status == Sentence.Status.TRANSLATED:
        raise TranslationWorkflowError("Это предложение уже переведено и заблокировано для новых правок.")

    if sentence.text_av and sentence.text_av == cleaned_text:
        raise TranslationWorkflowError("Этот перевод уже является основным.")

    # Проверяем дубликаты от других
    duplicate = sentence.suggestions.filter(
        proposed_text_av__iexact=cleaned_text,
        status=TranslationSuggestion.Status.PENDING
    ).exclude(author=user).exists()
    if duplicate:
        raise TranslationWorkflowError(
            "Такой вариант уже предложен другим участником. Лучше проголосуйте за него."
        )

    # Ищем существующую PENDING правку этого автора
    existing_suggestion = sentence.suggestions.filter(
        author=user,
        status=TranslationSuggestion.Status.PENDING
    ).first()

    if existing_suggestion:
        if existing_suggestion.proposed_text_av == cleaned_text:
            raise TranslationWorkflowError("Вы уже предложили точно такой же вариант.")
        
        existing_suggestion.proposed_text_av = cleaned_text
        existing_suggestion.original_text_av = cleaned_text
        existing_suggestion.created_at = timezone.now()
        existing_suggestion.save()
        return "Ваш предложенный перевод успешно обновлен."

    TranslationSuggestion.objects.create(
        sentence=sentence,
        proposed_text_av=cleaned_text,
        original_text_av=cleaned_text,
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
    try:
        suggestion = (
            TranslationSuggestion.objects.select_for_update()
            .select_related("sentence", "author")
            .get(pk=suggestion_id)
        )
    except TranslationSuggestion.DoesNotExist:
        raise TranslationWorkflowError("Правка не найдена.")

    if suggestion.status != TranslationSuggestion.Status.PENDING:
        raise TranslationWorkflowError("Эта правка уже обработана.")

    from accounts.models import UserProfile
    reviewer_profile = getattr(reviewer, "profile", None)
    is_co_editor_reviewer = (
        reviewer_profile is not None
        and reviewer_profile.role == UserProfile.Role.CO_EDITOR
    )
    if is_co_editor_reviewer and suggestion.author == reviewer:
        raise TranslationWorkflowError(
            "Соредактор не может принять или отклонить собственную правку."
        )

    # Запоминаем оригинал
    user_original_version = (suggestion.original_text_av or suggestion.proposed_text_av or "").strip()

    # Если редактор передал пустой текст - значит он не правил, берем текущий из правки
    final_text_to_approve = normalize_avar_text(edited_text) or suggestion.proposed_text_av

    suggestion.proposed_text_av = final_text_to_approve
    suggestion.reviewed_by = reviewer
    suggestion.reviewed_at = timezone.now()
    suggestion.editor_note = note
    suggestion.reviewer_role = (
        TranslationSuggestion.ReviewerRole.CO_EDITOR
        if is_co_editor_reviewer
        else TranslationSuggestion.ReviewerRole.EDITOR
    )

    if action == "accept":
        if is_co_editor_reviewer:
            admin_accepted = suggestion.sentence.suggestions.filter(
                status=TranslationSuggestion.Status.ACCEPTED
            ).exclude(reviewer_role=TranslationSuggestion.ReviewerRole.CO_EDITOR).first()
            if admin_accepted is not None:
                raise TranslationWorkflowError(
                    "Нельзя изменить перевод, принятый администратором."
                )

        # РАСЧЕТ КАЧЕСТВА
        matcher = difflib.SequenceMatcher(None, user_original_version, final_text_to_approve)
        score = matcher.ratio()
        suggestion.similarity_score = score

        # Обновляем профиль автора.
        profile = get_or_create_user_profile(suggestion.author)
        cur_avg = profile.average_quality_score or 0.0
        cur_count = profile.accepted_suggestions_count or 0
        new_count = cur_count + 1
        profile.average_quality_score = ((cur_avg * cur_count) + score) / new_count
        profile.accepted_suggestions_count = new_count
        profile.save(update_fields=["average_quality_score", "accepted_suggestions_count"])

        # Обновляем предложение
        set_sentence_translation(
            suggestion.sentence,
            translated_text=final_text_to_approve,
            translated_by=suggestion.author,
        )
        suggestion.sentence.save()
        
        suggestion.status = TranslationSuggestion.Status.ACCEPTED
        suggestion.save()

        # Создаем уведомление для автора
        from accounts.models import Notification
        Notification.objects.create(user=suggestion.author, suggestion=suggestion)

        # Отклоняем остальные
        other_pending = suggestion.sentence.suggestions.filter(
            status=TranslationSuggestion.Status.PENDING
        ).exclude(pk=suggestion.pk)
        
        for other in other_pending:
            other.status = TranslationSuggestion.Status.REJECTED
            other.reviewed_by = reviewer
            other.reviewed_at = timezone.now()
            other.editor_note = f"Автоматически отклонено: принят другой вариант (#{suggestion.pk})"
            other.save()

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
        suggestion.save()

        # Создаем уведомление для автора
        from accounts.models import Notification
        Notification.objects.create(user=suggestion.author, suggestion=suggestion)
        
        set_sentence_translation(
            suggestion.sentence,
            translated_text=suggestion.sentence.text_av,
        )
        suggestion.sentence.save()
        return suggestion

    raise TranslationWorkflowError("Неизвестное действие.")
