from django.contrib import admin

from .models import PointLedger


@admin.register(PointLedger)
class PointLedgerAdmin(admin.ModelAdmin):
    list_display = ("user", "reason", "points", "sentence", "created_at")
    list_filter = ("reason",)
    search_fields = ("user__username",)
