from django.contrib import admin

from .models import Batch, Clip, ClipEdit


class ClipEditInline(admin.TabularInline):
    model = ClipEdit
    extra = 0
    readonly_fields = ("user", "text", "errors", "verdict", "reviewed_by", "created_at")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("name", "source", "is_open", "created_at")
    list_editable = ("is_open",)


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "status", "is_gold", "duration", "draft_text")
    list_filter = ("batch", "status", "is_gold")
    search_fields = ("draft_text", "final_text", "source_ref")
    inlines = [ClipEditInline]


@admin.register(ClipEdit)
class ClipEditAdmin(admin.ModelAdmin):
    list_display = ("id", "clip", "user", "verdict", "errors", "created_at")
    list_filter = ("verdict", "clip__is_gold", "clip__batch")
