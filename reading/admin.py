from django.contrib import admin

from .models import Consent, Prompt, Recording


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ("id", "text", "source", "is_active")
    list_filter = ("source", "is_active")
    search_fields = ("text",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("id", "prompt", "user", "status", "duration", "attempts", "updated_at")
    list_filter = ("status",)


admin.site.register(Consent)
