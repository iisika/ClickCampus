
from datetime import date, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.urls import reverse

from .models import (
    Route,
    PickupPoint,
    Bus,
    TravelRequest,
    TO_SCHOOL_TIMES,
    FROM_SCHOOL_TIMES,
)


def dashboard(request):
    routes = Route.objects.filter(is_active=True)

    pickup_points = PickupPoint.objects.filter(
        route__is_active=True
    ).select_related("route")

    available_bus_count = Bus.objects.filter(
        status=Bus.Status.AVAILABLE
    ).count()

    context = {
        "routes": routes,
        "pickup_points": pickup_points,
        "available_bus_count": available_bus_count,
        "active_route_count": routes.count(),
        "my_trips": (
            TravelRequest.objects
            .filter(student=request.user)
            .select_related("route", "pickup_point", "bus")
            .order_by("-requested_at")
            if request.user.is_authenticated
            else []
        ),
    }

    return render(request, "transport/dashboard.html", context)


@login_required
def create_travel_request(request):
    if request.method != "POST":
        return redirect("transport:dashboard")

    pickup_point_id = request.POST.get("pickup_point", "").strip()
    travel_date_text = request.POST.get("travel_date", "").strip()
    direction = request.POST.get("direction", "").strip()
    departure_time_text = request.POST.get("departure_time", "").strip()

    # Validate the pickup point and its route.
    try:
        pickup_point = PickupPoint.objects.select_related("route").get(
            pk=pickup_point_id,
            route__is_active=True,
        )
    except (PickupPoint.DoesNotExist, ValueError, TypeError):
        messages.error(request, "Please select a valid pickup point.")
        return redirect("transport:dashboard")

    # Validate the travel date.
    try:
        travel_date = date.fromisoformat(travel_date_text)
    except (ValueError, TypeError):
        messages.error(request, "Please select a valid travel date.")
        return redirect("transport:dashboard")

    if travel_date < date.today():
        messages.error(request, "Travel date cannot be in the past.")
        return redirect("transport:dashboard")

    # Validate the journey direction.
    valid_directions = {
        choice[0]
        for choice in TravelRequest._meta.get_field("direction").choices
    }

    if direction not in valid_directions:
        messages.error(request, "Please choose a valid journey direction.")
        return redirect("transport:dashboard")

    # Select the allowed timetable for the chosen direction.
    if direction == TravelRequest.Direction.TO_SCHOOL:
        allowed_times = TO_SCHOOL_TIMES
    else:
        allowed_times = FROM_SCHOOL_TIMES

    # Parse and validate the exact departure time.
    try:
        departure_time = time.fromisoformat(departure_time_text)
    except (ValueError, TypeError):
        messages.error(request, "Please choose a valid departure time.")
        return redirect("transport:dashboard")

    if departure_time not in allowed_times:
        messages.error(
            request,
            "That departure time is not available for the selected "
            "journey direction.",
        )
        return redirect("transport:dashboard")

    # Prevent duplicate requests for the same student, date,
    # direction, and exact departure time.
    duplicate_exists = TravelRequest.objects.filter(
        student=request.user,
        travel_date=travel_date,
        direction=direction,
        departure_time=departure_time,
    ).exists()

    if duplicate_exists:
        messages.error(
            request,
            "You already have a request for that date, direction, "
            "and departure time.",
        )
        return redirect("transport:dashboard")

    # Save the request while retaining the legacy time_slot field
    # for compatibility with existing database records.
    try:
        with transaction.atomic():
            TravelRequest.objects.create(
                student=request.user,
                route=pickup_point.route,
                pickup_point=pickup_point,
                travel_date=travel_date,
                direction=direction,
                departure_time=departure_time,
                time_slot="",
            )
    except IntegrityError:
        messages.error(
            request,
            "This request could not be saved because a matching "
            "request already exists.",
        )
        return redirect("transport:dashboard")

    messages.success(
        request,
        "Your transport request was submitted successfully.",
    )

    return redirect(
        reverse("transport:dashboard") + "#my-trips"
    )


def login_page(request):
    return render(request, "transport/login.html")


def register_page(request):
    return render(request, "transport/register.html")
