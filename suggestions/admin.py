from django.contrib import admin

from .models import SuggestionVote, TranslationSuggestion


@admin.register(TranslationSuggestion)
class TranslationSuggestionAdmin(admin.ModelAdmin):
    list_display = ("id", "sentence", "author", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("proposed_text_ru", "sentence__source_text_av", "author__username")


@admin.register(SuggestionVote)
class SuggestionVoteAdmin(admin.ModelAdmin):
    list_display = ("suggestion", "user", "created_at")
    search_fields = ("suggestion__proposed_text_ru", "user__username")
