from rest_framework import filters, viewsets
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from django.db.models import Q

from api.mixins import QueryParamsFilterMixin
from .models import Language, Word, Translation, Example, Synonym
from .serializers import (
    LanguageSerializer,
    WordSerializer,
    WordShortSerializer,
    TranslationSerializer,
    ExampleSerializer,
    SynonymSerializer,
)
from .services import (
    build_word_search_queryset,
    fetch_translations_for_words,
    find_candidate_words,
)

class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for language lookup."""
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    pagination_class = None

class WordViewSet(QueryParamsFilterMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for words with filters and search."""
    queryset = (
        Word.objects.all()
        .select_related("language", "lemma")
        .prefetch_related("translations_from", "examples", "synonyms1", "synonyms2")
    )
    serializer_class = WordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["text", "transcription", "alternative_spelling", "description"]
    ordering_fields = ["text", "created_at"]

    query_params_map = {
        "language": "language__code",
        "part_of_speech": "part_of_speech",
    }

class TranslationViewSet(QueryParamsFilterMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for translations."""
    queryset = Translation.objects.select_related(
        "from_word",
        "to_word",
        "from_word__language",
        "to_word__language",
    ).all()
    serializer_class = TranslationSerializer

    query_params_map = {
        "from_word_id": "from_word_id",
        "to_word_id": "to_word_id",
    }

class ExampleViewSet(QueryParamsFilterMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for examples."""
    queryset = Example.objects.select_related("word").all()
    serializer_class = ExampleSerializer
    query_params_map = {"word_id": "word_id"}

class SynonymViewSet(QueryParamsFilterMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for synonyms."""
    queryset = Synonym.objects.select_related("word1", "word2").all()
    serializer_class = SynonymSerializer

    query_params_map = {
        "word_id": lambda qs, value: qs.filter(Q(word1_id=value) | Q(word2_id=value)),
    }

# Поиск по слову с фильтрами
@api_view(["GET"])
def search_words(request: Request) -> Response:
    """Return short word matches by query and language code."""
    query = request.GET.get("q", "").strip()
    language_code = request.GET.get("language")
    queryset = build_word_search_queryset(query, language_code)
    serializer = WordShortSerializer(queryset[:30], many=True)
    return Response(serializer.data)

# Быстрый перевод (от слова к переводам)
@api_view(["GET"])
def quick_translate(request: Request) -> Response:
    """Return translations for a word prefix in both directions."""
    word = request.GET.get("word", "").strip()
    source = request.GET.get("from")
    target = request.GET.get("to")
    if not (word and source and target):
        return Response({"error": "Required: word, from, to"}, status=400)
    word_qs = find_candidate_words(word, source)
    if not word_qs.exists():
        return Response([])

    word_ids = list(word_qs.values_list("id", flat=True)[:20])
    translations, reverse_translations = fetch_translations_for_words(word_ids, target)

    data = TranslationSerializer(translations, many=True).data
    reverse_data = TranslationSerializer(reverse_translations, many=True).data
    for item in reverse_data:
        item["from_word"], item["to_word"] = item["to_word"], item["from_word"]
    data.extend(reverse_data)

    return Response(data)
