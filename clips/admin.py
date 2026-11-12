from django.contrib import admin
from django.utils import timezone

from .models import Batch, Clip, ClipEdit


class ClipEditInline(admin.TabularInline):
    model = ClipEdit
    extra = 0
    readonly_fields = ("user", "text", "errors", "verdict", "reviewed_by", "created_at")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "source", "n_clips", "n_gold", "is_open", "created_at")

    @admin.display(description="Фрагментов")
    def n_clips(self, obj):
        return obj.clips.count()

    @admin.display(description="Проверочных")
    def n_gold(self, obj):
        return obj.clips.filter(is_gold=True).count()
    list_editable = ("is_open",)


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "status", "is_gold", "duration", "draft_text")
    list_filter = ("batch", "status", "is_gold")
    search_fields = ("draft_text", "final_text", "source_ref")
    inlines = [ClipEditInline]
    actions = ("mark_audio_defective",)

    @admin.action(description="Отметить дефект аудио и снять с выдачи")
    def mark_audio_defective(self, request, queryset):
        for clip in queryset:
            AudioIssue.objects.get_or_create(clip=clip, user=request.user,
                                             defaults={"reason": AudioIssue.Reason.OTHER, "note": "Отмечено администратором"})


@admin.register(ClipEdit)
class ClipEditAdmin(admin.ModelAdmin):
    list_display = ("id", "clip", "user", "verdict", "errors", "created_at")
    list_filter = ("verdict", "clip__is_gold", "clip__batch")


from .models import AudioIssue
@admin.register(AudioIssue)
class AudioIssueAdmin(admin.ModelAdmin):
    list_display = ("clip", "user", "created_at", "reviewed_at")
    list_filter = ("reviewed_at",)
    readonly_fields = ("clip", "user", "reason", "note", "created_at")
    search_fields = ("clip__source_ref", "clip__draft_text", "note")
    actions = ("return_to_processing", "keep_out_of_processing")

    @admin.action(description="Вернуть фрагменты в обработку")
    def return_to_processing(self, request, queryset):
        clip_ids = list(queryset.values_list("clip_id", flat=True))
        queryset.update(reviewed_by=request.user, reviewed_at=timezone.now())
        for clip in Clip.objects.filter(pk__in=clip_ids, status=Clip.Status.DISPUTED):
            if not clip.audio_issues.filter(reviewed_at__isnull=True).exists():
                clip.status = Clip.Status.OPEN
                clip.save(update_fields=("status", "updated_at"))

    @admin.action(description="Оставить фрагменты вне выдачи")
    def keep_out_of_processing(self, request, queryset):
        for issue in queryset.select_related("clip"):
            clip = issue.clip
            clip.status = Clip.Status.DISPUTED
            clip.save(update_fields=("status", "updated_at"))
