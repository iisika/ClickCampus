
from django.conf import settings
from django.db import models
from django.db.models import Q


class Route(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_location = models.CharField(max_length=150)
    end_location = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PickupPoint(models.Model):
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="pickup_points",
    )
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["sequence", "name"]

    def __str__(self):
        return f"{self.name} - {self.route.name}"


class Bus(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        IN_SERVICE = "in_service", "In service"
        MAINTENANCE = "maintenance", "Under maintenance"

    registration_number = models.CharField(max_length=20, unique=True)
    capacity = models.PositiveIntegerField()
    route = models.ForeignKey(
        Route,
        on_delete=models.PROTECT,
        related_name="buses",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(capacity__gt=0),
                name="bus_capacity_must_be_positive",
            )
        ]

    def __str__(self):
        return self.registration_number


class TravelRequest(models.Model):
    class Direction(models.TextChoices):
        TO_SCHOOL = "to_school", "To school"
        FROM_SCHOOL = "from_school", "From school"

    class TimeSlot(models.TextChoices):
        MORNING = "morning", "Morning"
        AFTERNOON = "afternoon", "Afternoon"
        EVENING = "evening", "Evening"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="travel_requests",
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.PROTECT,
        related_name="travel_requests",
    )
    pickup_point = models.ForeignKey(
        PickupPoint,
        on_delete=models.PROTECT,
        related_name="travel_requests",
    )
    bus = models.ForeignKey(
        Bus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="travel_requests",
    )
    travel_date = models.DateField()
    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
    )
    time_slot = models.CharField(
        max_length=20,
        choices=TimeSlot.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["travel_date", "time_slot"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "travel_date",
                    "direction",
                    "time_slot",
                ],
                name="unique_student_travel_slot",
            )
        ]

    def __str__(self):
        return (
            f"{self.student} - {self.travel_date} "
            f"({self.get_direction_display()})"
        )


class BusLocation(models.Model):
    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name="location_updates",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_bus_locations",
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.bus.registration_number} at {self.recorded_at}"
