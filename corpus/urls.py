from django.urls import path

from .views import SentenceDetailView, SentenceListView, SuggestionVoteToggleView


urlpatterns = [
    path("", SentenceListView.as_view(), name="sentence-list"),
    path("<int:pk>/", SentenceDetailView.as_view(), name="sentence-detail"),
    path(
        "<int:pk>/suggestions/<int:suggestion_pk>/vote/",
        SuggestionVoteToggleView.as_view(),
        name="suggestion-vote-toggle",
    ),
]
