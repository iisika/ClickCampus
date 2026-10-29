
from datetime import date, time
from datetime import datetime, timedelta
from django.utils import timezone

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from collections import defaultdict
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

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

    # Use the configured local timezone (Africa/Nairobi).
    local_now = timezone.localtime()
    today = local_now.date()

    # Reject travel dates that have already passed.
    if travel_date < today:
        messages.error(request, "Travel date cannot be in the past.")
        return redirect("transport:dashboard")

    # Bookings close at 10:00 PM on the calendar day before travel.
    deadline_date = travel_date - timedelta(days=1)

    booking_deadline = timezone.make_aware(
        datetime.combine(deadline_date, time(22, 0))
    )

    if local_now >= booking_deadline:
        messages.error(
            request,
            "Bookings for this travel date closed at 10:00 PM "
            "the previous night. Please select another travel date."
        )
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


@login_required
@require_POST
def cancel_travel_request(request, request_id):
    # Students can only access their own booking.
    booking = get_object_or_404(
        TravelRequest,
        pk=request_id,
        student=request.user,
    )

    if booking.status == TravelRequest.Status.CANCELLED:
        messages.info(request, "This booking is already cancelled.")
        return redirect(
            reverse("transport:dashboard") + "#my-trips"
        )

    booking.status = TravelRequest.Status.CANCELLED
    booking.save(update_fields=["status"])

    messages.success(
        request,
        "Your transport booking has been cancelled successfully.",
    )

    return redirect(
        reverse("transport:dashboard") + "#my-trips"
    )



def login_page(request):
    return render(request, "transport/login.html")


def register_page(request):
    return render(request, "transport/register.html")



@staff_member_required
def admin_dashboard(request):
    context = {
        "pending_requests": TravelRequest.objects.filter(
            status=TravelRequest.Status.PENDING
        ).count(),
        "confirmed_requests": TravelRequest.objects.filter(
            status=TravelRequest.Status.CONFIRMED
        ).count(),
        "cancelled_requests": TravelRequest.objects.filter(
            status=TravelRequest.Status.CANCELLED
        ).count(),
        "total_routes": Route.objects.count(),
        "total_pickup_points": PickupPoint.objects.count(),
        "total_buses": Bus.objects.count(),
        "available_buses": Bus.objects.filter(
            status=Bus.Status.AVAILABLE
        ).count(),
    }

    return render(
        request,
        "transport/admin_dashboard.html",
        context,
    )




@staff_member_required
def demand_report(request):
    selected_date_text = request.GET.get("travel_date", "").strip()
    selected_date = (
        parse_date(selected_date_text)
        if selected_date_text
        else None
    )

    if selected_date is None:
        selected_date = timezone.localdate()

    travel_requests = (
        TravelRequest.objects
        .filter(travel_date=selected_date)
        .exclude(status=TravelRequest.Status.CANCELLED)
        .select_related("route", "pickup_point", "bus")
        .order_by("direction", "departure_time", "route__name")
    )

    # Group all routes sharing the same direction and departure.
    groups = defaultdict(list)

    for booking in travel_requests:
        key = (booking.direction, booking.departure_time)
        groups[key].append(booking)

    # Route restrictions are deliberately not applied here.
    available_buses = list(
        Bus.objects
        .filter(
            status=Bus.Status.AVAILABLE,
            capacity__gt=0,
        )
        .order_by("-capacity", "registration_number")
    )

    # Record the earliest time each vehicle can be reused.
    next_available_at = {
        bus.pk: datetime.min for bus in available_buses
    }

    report_rows = []

    sorted_groups = sorted(
        groups.items(),
        key=lambda item: (
        item[0][1] or time.max,
        item[0][0]
    )
    )

    for (direction, departure_time), bookings in sorted_groups:
        total_students = len(bookings)
        planning_demand = total_students + 5

        route_counts = defaultdict(int)
        for booking in bookings:
            route_counts[booking.route.name] += 1

        buses_needed = 0
        remaining_students = planning_demand
        recommended_vehicles = []
        capacity_shortfall = False

        if departure_time is None:
            capacity_note = (
                "Departure time missing. Review these requests "
                "before planning vehicle assignments."
            )
        else:
            departure_at = datetime.combine(
                selected_date,
                departure_time,
            )

            if direction == TravelRequest.Direction.TO_SCHOOL:
                journey_duration = timedelta(minutes=90)
            else:
                journey_duration = timedelta(minutes=150)

            # Only vehicles available at this departure can be used.
            eligible_buses = sorted(
                (
                    bus for bus in available_buses
                    if next_available_at[bus.pk] <= departure_at
                ),
                key=lambda bus: (
                    -(bus.capacity - 5),
                    bus.registration_number,
                ),
            )

            for bus in eligible_buses:
                if remaining_students <= 0:
                    break

                usable_seats = bus.capacity
                remaining_students -= usable_seats
                buses_needed += 1
                recommended_vehicles.append(
                    bus.registration_number
                )

                # Reserve this vehicle until its estimated return.
                next_available_at[bus.pk] = (
                    departure_at + journey_duration
                )

            if remaining_students > 0:
                capacity_shortfall = True
                capacity_note = (
                    f"Insufficient vehicles available at this time. "
                    f"{remaining_students} student(s) remain uncovered. "
                    "Review the schedule or provide additional vehicles."
                )
            elif buses_needed == 0:
                capacity_note = "No vehicles required."
            else:
                capacity_note = (
                    "Capacity estimate includes a five-seat reserve "
                    "per vehicle. Review recommendations before assigning."
                )

        report_rows.append({
            "planning_demand": planning_demand,
            "direction": direction,
            "direction_label": dict(
                TravelRequest.Direction.choices
            ).get(direction, direction),
            "departure_time": departure_time,
            "total_students": total_students,
            "route_counts": dict(route_counts),
            "buses_needed": buses_needed,
            "recommended_vehicles": recommended_vehicles,
            "capacity_shortfall": capacity_shortfall,
            "capacity_note": capacity_note,
        })

    context = {
        "selected_date": selected_date,
        "report_rows": report_rows,
        "available_bus_count": len(available_buses),
        "total_requests": sum(
            row["total_students"] for row in report_rows
        ),
    }

    return render(
        request,
        "transport/demand_report.html",
        context,
    )
