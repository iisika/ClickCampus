from django.shortcuts import render
from .models import Route, PickupPoint, Bus

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.urls import reverse

from .models import Route, PickupPoint, Bus, TravelRequest



def dashboard(request):
    routes = Route.objects.filter(is_active=True)

    pickup_points = PickupPoint.objects.filter(
        route__is_active=True
    ).select_related("route")

    available_bus_count = Bus.objects.filter(
        status="available"
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
    time_slot = request.POST.get("time_slot", "").strip()

    # Validate the pickup point.
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

    # Validate direction and time slot against the model choices.
    valid_directions = {
        choice[0] for choice in TravelRequest._meta
        .get_field("direction").choices
    }
    valid_time_slots = {
        choice[0] for choice in TravelRequest._meta
        .get_field("time_slot").choices
    }

    if direction not in valid_directions:
        messages.error(request, "Please choose a valid journey direction.")
        return redirect("transport:dashboard")

    if time_slot not in valid_time_slots:
        messages.error(request, "Please choose a valid travel time.")
        return redirect("transport:dashboard")

    # Avoid duplicate requests for the same student, date,
    # direction, and time slot.
    duplicate_exists = TravelRequest.objects.filter(
        student=request.user,
        travel_date=travel_date,
        direction=direction,
        time_slot=time_slot,
    ).exists()

    if duplicate_exists:
        messages.error(
            request,
            "You already have a request for that date, direction, "
            "and time slot."
        )
        return redirect("transport:dashboard")

    try:
        with transaction.atomic():
            TravelRequest.objects.create(
                student=request.user,
                route=pickup_point.route,
                pickup_point=pickup_point,
                travel_date=travel_date,
                direction=direction,
                time_slot=time_slot,
            )
    except IntegrityError:
        messages.error(
            request,
            "This request could not be saved because a matching "
            "request already exists."
        )
        return redirect("transport:dashboard")

    messages.success(request, "Your transport request was submitted successfully.")
    return redirect(
        reverse("transport:dashboard") + "#my-trips"
    )


def login_page(request):
    return render(request, "transport/login.html")


def register_page(request):
    return render(request, "transport/register.html")
