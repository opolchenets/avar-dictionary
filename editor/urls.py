from django.urls import path

from .views import (
    CorpusExportView,
    EditorDashboardView,
    EditorSentenceDetailView,
    EditorSentenceListView,
    SentenceImportView,
    SuggestionQueueView,
    TerminologyListView,
    TerminologyImportView,
)


urlpatterns = [
    path("", EditorDashboardView.as_view(), name="editor-dashboard"),
    path("import/", SentenceImportView.as_view(), name="editor-import"),
    path("suggestions/", SuggestionQueueView.as_view(), name="editor-suggestions"),
    path("sentences/", EditorSentenceListView.as_view(), name="editor-sentences"),
    path("sentences/<int:pk>/", EditorSentenceDetailView.as_view(), name="editor-sentence-detail"),
    path("terminology/", TerminologyListView.as_view(), name="editor-terminology"),
    path("terminology/import/", TerminologyImportView.as_view(), name="editor-import-terminology"),
    path("export.csv", CorpusExportView.as_view(), name="editor-export"),
]
