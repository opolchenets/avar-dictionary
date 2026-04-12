from django.urls import path

from .views import (
    CorpusExportView,
    EditorDashboardView,
    EditorSentenceDetailView,
    EditorSentenceListView,
    SentenceImportView,
    SuggestionQueueView,
)


urlpatterns = [
    path("", EditorDashboardView.as_view(), name="editor-dashboard"),
    path("import/", SentenceImportView.as_view(), name="editor-import"),
    path("suggestions/", SuggestionQueueView.as_view(), name="editor-suggestions"),
    path("sentences/", EditorSentenceListView.as_view(), name="editor-sentences"),
    path("sentences/<int:pk>/", EditorSentenceDetailView.as_view(), name="editor-sentence-detail"),
    path("export.csv", CorpusExportView.as_view(), name="editor-export"),
]
