from django.contrib import admin
from .models import Category, Sentence, Terminology


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Sentence)
class SentenceAdmin(admin.ModelAdmin):
    list_display = ("id", "short_text", "status", "category", "translated_by", "created_at")
    list_filter = ("status", "category")
    search_fields = ("source_text_ru", "text_av")

    @admin.display(description="Текст")
    def short_text(self, obj):
        return obj.source_text_ru[:80]


@admin.register(Terminology)
class TerminologyAdmin(admin.ModelAdmin):
    list_display = ("word_ru", "word_av", "category")
    list_filter = ("category",)
    search_fields = ("word_ru", "word_av")
