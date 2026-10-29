from datetime import time

from django.conf import settings
from django.db import models
from django.db.models import Q


# Student pickups: designated pickup points -> school
TO_SCHOOL_DEPARTURE_TIMES = (
    (time(6, 0), "6:00 AM"),
    (time(7, 0), "7:00 AM"),
    (time(9, 30), "9:30 AM"),
    (time(11, 50), "11:50 AM"),
    (time(13, 50), "1:50 PM"),
)

# Student drop-offs: school -> designated destinations
FROM_SCHOOL_DEPARTURE_TIMES = (
    (time(11, 0), "11:00 AM"),
    (time(13, 0), "1:00 PM"),
    (time(15, 30), "3:30 PM"),
    (time(17, 30), "5:30 PM"),
    (time(19, 20), "7:20 PM"),
    (time(21, 20), "9:20 PM"),
)

# All allowed departure times, used by the database field.
ALL_DEPARTURE_TIME_CHOICES = (
    TO_SCHOOL_DEPARTURE_TIMES + FROM_SCHOOL_DEPARTURE_TIMES
)

TO_SCHOOL_TIMES = tuple(
    departure_time for departure_time, label
    in TO_SCHOOL_DEPARTURE_TIMES
)

FROM_SCHOOL_TIMES = tuple(
    departure_time for departure_time, label
    in FROM_SCHOOL_DEPARTURE_TIMES
)


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

    departure_time = models.TimeField(
    choices=ALL_DEPARTURE_TIME_CHOICES,
    null=True,
    blank=True,
    help_text=(
        "Exact scheduled departure time. "
        "Blank for older requests awaiting review."
        ),
    )

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
        blank=True,
        default="",
    )
       
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["travel_date", "departure_time"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "travel_date",
                    "direction",
                    "departure_time",
                ],
                name="unique_student_departure_time",
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
