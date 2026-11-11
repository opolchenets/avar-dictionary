from django.contrib import admin

from .models import Consent, Prompt, Recording, PromptFeedback


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

@admin.register(PromptFeedback)
class PromptFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "prompt", "user", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("prompt", "user", "original_text", "suggested_text", "note", "status", "reviewed_by", "reviewed_at", "created_at")

    def has_add_permission(self, request):
        return False
