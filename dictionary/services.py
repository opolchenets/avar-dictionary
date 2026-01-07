from typing import Iterable, Tuple

from django.db.models import Q, QuerySet

from .models import Translation, Word


def build_word_search_queryset(query: str, language_code: str | None) -> QuerySet[Word]:
    """Build a queryset for search_words with optional query and language filter."""
    queryset = Word.objects.select_related("language").all()
    if query:
        queryset = queryset.filter(
            Q(text__icontains=query)
            | Q(transcription__icontains=query)
            | Q(alternative_spelling__icontains=query)
            | Q(description__icontains=query)
        )
    if language_code:
        queryset = queryset.filter(language__code=language_code)
    return queryset


def find_candidate_words(prefix: str, source_language: str) -> QuerySet[Word]:
    """Return candidate words for quick translation by prefix."""
    queryset = Word.objects.filter(language__code=source_language)
    if prefix:
        queryset = queryset.filter(text__istartswith=prefix)
    return queryset.order_by("text")


def fetch_translations_for_words(
    word_ids: Iterable[int],
    target_language: str,
) -> Tuple[QuerySet[Translation], QuerySet[Translation]]:
    """Fetch translations in both directions for given word ids."""
    translations = Translation.objects.filter(
        from_word_id__in=word_ids,
        to_word__language__code=target_language,
    ).select_related("to_word", "to_word__language", "from_word", "from_word__language")

    reverse_translations = Translation.objects.filter(
        to_word_id__in=word_ids,
        from_word__language__code=target_language,
    ).select_related("to_word", "to_word__language", "from_word", "from_word__language")

    return translations, reverse_translations
