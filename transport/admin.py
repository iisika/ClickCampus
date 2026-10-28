
from django import forms
from django.contrib import admin
from .models import Bus, BusLocation, PickupPoint, Route, TravelRequest


class TravelRequestAdminForm(forms.ModelForm):
    class Meta:
        model = TravelRequest
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        bus = cleaned_data.get("bus")
        route = cleaned_data.get("route")
        travel_date = cleaned_data.get("travel_date")
        direction = cleaned_data.get("direction")
        time_slot = cleaned_data.get("time_slot")
        status = cleaned_data.get("status")

        if not bus:
            return cleaned_data

        # A bus must serve the booking's route.
        if route and bus.route_id != route.id:
            self.add_error(
                "bus",
                "This bus does not serve the selected route.",
            )

        # A bus under maintenance cannot be assigned.
        if bus.status == Bus.Status.MAINTENANCE:
            self.add_error(
                "bus",
                "This bus is under maintenance and cannot be assigned.",
            )

        # Confirmed bookings must not exceed bus capacity.
        if (
            status == TravelRequest.Status.CONFIRMED
            and travel_date
            and direction
            and time_slot
        ):
            bookings = TravelRequest.objects.filter(
                bus=bus,
                travel_date=travel_date,
                direction=direction,
                time_slot=time_slot,
                status=TravelRequest.Status.CONFIRMED,
            )

            if self.instance.pk:
                bookings = bookings.exclude(pk=self.instance.pk)

            if bookings.count() >= bus.capacity:
                self.add_error(
                    "bus",
                    "This bus has reached capacity for this "
                    "date, direction and time slot.",
                )

        return cleaned_data


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = (
        "name", "start_location", "end_location", "is_active"
    )
    search_fields = ("name", "start_location", "end_location")
    list_filter = ("is_active",)


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ("name", "route", "sequence")
    list_filter = ("route",)
    search_fields = ("name", "route__name")


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = (
        "registration_number", "route", "capacity", "status"
    )
    list_filter = ("status", "route")
    search_fields = ("registration_number",)


@admin.register(TravelRequest)
class TravelRequestAdmin(admin.ModelAdmin):
    form = TravelRequestAdminForm

    list_display = (
        "student",
        "route",
        "pickup_point",
        "travel_date",
        "direction",
        "time_slot",
        "bus",
        "status",
    )
    list_filter = (
        "travel_date", "route", "direction", "time_slot", "status"
    )
    search_fields = (
        "student__username",
        "student__email",
        "student__first_name",
        "student__last_name",
        "bus__registration_number",
    )
    list_select_related = ("student", "route", "pickup_point", "bus")
    autocomplete_fields = ("student", "bus")
    list_per_page = 25


@admin.register(BusLocation)
class BusLocationAdmin(admin.ModelAdmin):
    list_display = ("bus", "latitude", "longitude", "recorded_at")
    list_filter = ("bus",)
    ordering = ("-recorded_at",)
