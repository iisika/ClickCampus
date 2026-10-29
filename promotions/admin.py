
from django.contrib import admin
from .models import Promotion


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "business_name",
        "status",
        "start_date",
        "end_date",
        "created_at",
    )

    list_filter = ("status", "start_date", "end_date")
    search_fields = ("title", "business_name", "location")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Business and Offer", {
            "fields": (
                "business_name",
                "title",
                "description",
                "offer",
                "location",
                "image",
            )
        }),
        ("Promotion Period", {
            "fields": ("start_date", "end_date")
        }),
        ("Approval", {
            "fields": ("status",)
        }),
        ("Record Information", {
            "fields": ("created_at",)
        }),
    )
