
from django import forms
from django.contrib import admin

from .models import (
    Bus,
    BusLocation,
    PickupPoint,
    Route,
    TravelRequest,
    TO_SCHOOL_TIMES,
    FROM_SCHOOL_TIMES,
)


class TravelRequestAdminForm(forms.ModelForm):
    class Meta:
        model = TravelRequest
        exclude = ("time_slot",)

    def clean(self):
        cleaned_data = super().clean()

        bus = cleaned_data.get("bus")
        route = cleaned_data.get("route")
        travel_date = cleaned_data.get("travel_date")
        direction = cleaned_data.get("direction")
        departure_time = cleaned_data.get("departure_time")
        status = cleaned_data.get("status")

        # Validate that the departure time matches the journey direction.
        if direction and departure_time:
            if direction == TravelRequest.Direction.TO_SCHOOL:
                allowed_times = TO_SCHOOL_TIMES
            elif direction == TravelRequest.Direction.FROM_SCHOOL:
                allowed_times = FROM_SCHOOL_TIMES
            else:
                allowed_times = ()

            if departure_time not in allowed_times:
                self.add_error(
                    "departure_time",
                    "This departure time is not valid for the selected "
                    "journey direction.",
                )

        if not bus:
            return cleaned_data

        if bus.status == Bus.Status.MAINTENANCE:
            self.add_error(
                "bus",
                "This bus is under maintenance and cannot be assigned.",
            )

        # Count confirmed bookings for this exact departure.
        if (
            status == TravelRequest.Status.CONFIRMED
            and travel_date
            and direction
            and departure_time
        ):
            bookings = TravelRequest.objects.filter(
                bus=bus,
                travel_date=travel_date,
                direction=direction,
                departure_time=departure_time,
                status=TravelRequest.Status.CONFIRMED,
            )

            if self.instance.pk:
                bookings = bookings.exclude(pk=self.instance.pk)

            usable_capacity = bus.capacity

            if bookings.count() >= usable_capacity:
                self.add_error(
                    "bus",
                    "This bus has reached its usable capacity for this departure ",
                )

        return cleaned_data


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("name", "start_location", "end_location", "is_active")
    search_fields = ("name", "start_location", "end_location")
    list_filter = ("is_active",)


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ("name", "route", "sequence")
    list_filter = ("route",)
    search_fields = ("name", "route__name")


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "route", "capacity", "status")
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
        "departure_time",
        "bus",
        "status",
    )

    list_filter = (
        "travel_date",
        "route",
        "direction",
        "departure_time",
        "status",
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
