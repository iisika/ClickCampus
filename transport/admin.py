from django.contrib import admin

from .models import Bus, BusLocation, PickupPoint, Route, TravelRequest


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("name", "start_location", "end_location", "is_active")
    search_fields = ("name", "start_location", "end_location")
    list_filter = ("is_active",)


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ("name", "route", "sequence")
    list_filter = ("route",)
    search_fields = ("name",)


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "route", "capacity", "status")
    list_filter = ("status", "route")
    search_fields = ("registration_number",)


@admin.register(TravelRequest)
class TravelRequestAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "travel_date",
        "direction",
        "time_slot",
        "status",
        "bus",
    )
    list_filter = ("travel_date", "direction", "time_slot", "status")
    search_fields = ("student__username", "student__email")


@admin.register(BusLocation)
class BusLocationAdmin(admin.ModelAdmin):
    list_display = ("bus", "latitude", "longitude", "recorded_at")
    list_filter = ("bus",)
    ordering = ("-recorded_at",)