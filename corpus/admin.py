from django.contrib import admin

from .models import Sentence


@admin.register(Sentence)
class SentenceAdmin(admin.ModelAdmin):
    list_display = ("id", "short_text", "status", "translated_by", "created_at")
    list_filter = ("status",)
    search_fields = ("source_text_ru", "text_av")

    @admin.display(description="Текст")
    def short_text(self, obj):
        return obj.source_text_ru[:80]
