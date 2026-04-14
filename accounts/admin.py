from django.contrib import admin
from .models import Alliance, District, UserProfile


@admin.register(Alliance)
class AllianceAdmin(admin.ModelAdmin):
    list_display = ("name", "color")


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "alliance")
    list_filter = ("alliance",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "role", "district")
    list_filter = ("role", "district__alliance", "district")
    search_fields = ("user__username", "display_name")
