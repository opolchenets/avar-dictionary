from django.db.models import Q

from .models import ArchivedRejection


def preserve_rejections(edits, recordings):
    rejected_edits = edits.filter(verdict="rejected").filter(
        Q(reviewed_by__isnull=False) | Q(auto_accepted=True))
    rejected_recordings = recordings.filter(status="rejected")
    for kind, queryset, target in (
        ("clip", rejected_edits, "clip_id"),
        ("recording", rejected_recordings, "prompt_id"),
    ):
        ArchivedRejection.objects.bulk_create(
            [
                ArchivedRejection(kind=kind, submission_id=pk, user_id=user_id, target_id=target_id)
                for pk, user_id, target_id in queryset.select_for_update().values_list("pk", "user_id", target)
            ],
            ignore_conflicts=True,
        )
