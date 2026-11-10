from django.contrib import admin

from .models import AsrTrial


@admin.register(AsrTrial)
class AsrTrialAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "duration", "model_version", "created_at")
    list_filter = ("status", "model_version")
    search_fields = ("user__username", "result_text")
    readonly_fields = ("public_id", "created_at")
