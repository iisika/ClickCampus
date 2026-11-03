
import json
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
from promotions.models import Promotion

from .models import (
    Route,
    PickupPoint,
    Bus,
    TravelRequest,
    
    TO_SCHOOL_TIMES,
    FROM_SCHOOL_TIMES,
)


def landing_page(request):
    """Public homepage for visitors who have not entered a portal."""
    return render(request, "transport/landing.html")


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
        "student_promotions": Promotion.objects.filter(
            status=Promotion.Status.APPROVED,
            start_date__lte=timezone.localdate(),
            end_date__gte=timezone.localdate(),
        ).order_by("-created_at"),
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
    pending_requests = TravelRequest.objects.filter(
        status=TravelRequest.Status.PENDING
    ).count()
    confirmed_requests = TravelRequest.objects.filter(
        status=TravelRequest.Status.CONFIRMED
    ).count()
    cancelled_requests = TravelRequest.objects.filter(
        status=TravelRequest.Status.CANCELLED
    ).count()
    available_buses = Bus.objects.filter(
        status=Bus.Status.AVAILABLE
    ).count()
    in_service_buses = Bus.objects.filter(
        status=Bus.Status.IN_SERVICE
    ).count()
    maintenance_buses = Bus.objects.filter(
        status=Bus.Status.MAINTENANCE
    ).count()

    def donut_background(values, colors):
        total = sum(values)
        if total == 0:
            return "#e8edf3"
        stops = []
        current = 0.0
        for value, color in zip(values, colors):
            next_stop = current + (value / total * 100)
            stops.append(f"{color} {current:.2f}% {next_stop:.2f}%")
            current = next_stop
        return f"conic-gradient({', '.join(stops)})"

    booking_values = [
        pending_requests,
        confirmed_requests,
        cancelled_requests,
    ]
    fleet_values = [
        available_buses,
        in_service_buses,
        maintenance_buses,
    ]

    context = {
        "pending_requests": pending_requests,
        "confirmed_requests": confirmed_requests,
        "cancelled_requests": cancelled_requests,
        "total_requests": TravelRequest.objects.count(),
        "total_routes": Route.objects.count(),
        "active_routes": Route.objects.filter(is_active=True).count(),
        "total_pickup_points": PickupPoint.objects.count(),
        "total_buses": Bus.objects.count(),
        "available_buses": available_buses,
        "in_service_buses": in_service_buses,
        "maintenance_buses": maintenance_buses,
        "pending_promotions": Promotion.objects.filter(
            status=Promotion.Status.PENDING
        ).count(),
        "approved_promotions": Promotion.objects.filter(
            status=Promotion.Status.APPROVED
        ).count(),
        "total_promotions": Promotion.objects.count(),
        "recent_requests": (
            TravelRequest.objects
            .select_related("student", "route", "bus")
            .order_by("-requested_at")[:6]
        ),
        "booking_chart_background": donut_background(booking_values, ["#f2bd28", "#31b981", "#e36d70"]),
        "fleet_chart_background": donut_background(fleet_values, ["#31b981", "#4778c7", "#e36d70"]),
        "booking_chart_data": json.dumps({
            "labels": ["Pending", "Confirmed", "Cancelled"],
            "values": [
                pending_requests,
                confirmed_requests,
                cancelled_requests,
            ],
        }),
        "fleet_chart_data": json.dumps({
            "labels": ["Available", "In service", "Maintenance"],
            "values": [
                available_buses,
                in_service_buses,
                maintenance_buses,
            ],
        }),
    }

    return render(request, "transport/admin_dashboard.html", context)




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

    # Keep demand separate for each route, direction, and departure.
    # The vehicle pool remains shared: administrators may assign any
    # available bus to any route, subject to capacity and schedule.
    groups = defaultdict(list)

    for booking in travel_requests:
        key = (
            booking.route_id,
            booking.route.name,
            booking.direction,
            booking.departure_time,
        )
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

    # Start with the full fleet so already-confirmed assignments are
    # respected even when a bus is currently marked "in service".
    fleet = list(Bus.objects.filter(capacity__gt=0))
    next_available_at = {
        bus.pk: datetime.min for bus in fleet
    }

    # Keep track of vehicles already assigned to each route departure.
    # A vehicle's capacity is counted once per departure, not once per student.
    assigned_by_group = defaultdict(dict)
    confirmed_assignments = (
        TravelRequest.objects
        .filter(
            travel_date=selected_date,
            status=TravelRequest.Status.CONFIRMED,
            bus__isnull=False,
            departure_time__isnull=False,
        )
        .select_related("bus")
    )

    confirmed_by_bus = defaultdict(list)
    for assigned_booking in confirmed_assignments:
        assigned_bus = assigned_booking.bus
        assigned_duration = (
            timedelta(minutes=90)
            if assigned_booking.direction == TravelRequest.Direction.TO_SCHOOL
            else timedelta(minutes=150)
        )
        assigned_departure = datetime.combine(
            selected_date,
            assigned_booking.departure_time,
        )
        assigned_return = assigned_departure + assigned_duration

        assignment_key = (
            assigned_booking.route_id,
            assigned_booking.direction,
            assigned_booking.departure_time,
        )
        # Multiple students may legitimately share one bus on the same
        # route departure. Record that vehicle assignment only once.
        if assigned_bus.pk not in assigned_by_group[assignment_key]:
            assigned_by_group[assignment_key][assigned_bus.pk] = assigned_bus
            confirmed_by_bus[assigned_bus.pk].append({
                "start": assigned_departure,
                "end": assigned_return,
                "group_key": assignment_key,
                "route_name": assigned_booking.route.name,
                "departure_time": assigned_booking.departure_time,
            })

    # Flag both sides of any overlapping confirmed assignments.
    conflicting_groups = defaultdict(set)
    for bus_id, assignments in confirmed_by_bus.items():
        assignments.sort(key=lambda item: item["start"])
        for index, first in enumerate(assignments):
            for second in assignments[index + 1:]:
                if second["start"] >= first["end"]:
                    break
                if first["start"] < second["end"] and second["start"] < first["end"]:
                    conflicting_groups[first["group_key"]].add(bus_id)
                    conflicting_groups[second["group_key"]].add(bus_id)

    # Use the latest known return only as a conservative availability
    # boundary for additional recommendations.
    for bus_id, assignments in confirmed_by_bus.items():
        next_available_at[bus_id] = max(
            item["end"] for item in assignments
        )

    report_rows = []

    sorted_groups = sorted(
        groups.items(),
        key=lambda item: (
            item[0][3] or time.max,
            item[0][2],
            item[0][1],
        ),
    )

    for (route_id, route_name, direction, departure_time), bookings in sorted_groups:
        total_students = len(bookings)
        planning_demand = total_students + 5

        group_key = (route_id, direction, departure_time)
        conflicting_bus_ids = conflicting_groups.get(group_key, set())
        all_preassigned_buses = list(
            assigned_by_group.get(group_key, {}).values()
        )
        preassigned_buses = [
            bus for bus in all_preassigned_buses
            if bus.pk not in conflicting_bus_ids
        ]
        has_assignment_conflict = bool(conflicting_bus_ids)
        preassigned_capacity = sum(
            bus.capacity for bus in preassigned_buses
        )

        buses_needed = len(preassigned_buses)
        remaining_students = max(
            planning_demand - preassigned_capacity,
            0,
        )
        recommended_vehicles = [
            bus.registration_number for bus in preassigned_buses
        ]
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
            already_assigned_ids = {
                bus.pk for bus in preassigned_buses
            }
            eligible_buses = sorted(
                (
                    bus for bus in available_buses
                    if bus.pk not in already_assigned_ids
                    and next_available_at[bus.pk] <= departure_at
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

            if has_assignment_conflict:
                capacity_shortfall = True
                conflict_names = ", ".join(
                    bus.registration_number
                    for bus in all_preassigned_buses
                    if bus.pk in conflicting_bus_ids
                )
                capacity_note = (
                    f"Scheduling conflict: {conflict_names} is assigned "
                    "to overlapping confirmed journeys. Conflicting "
                    "assignments are excluded from usable capacity. "
                    "An administrator must resolve them."
                )
            elif remaining_students > 0:
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
                    "Planning demand includes a five-student buffer "
                    "for this departure group. Review recommendations "
                    "before assigning."
                )

        report_rows.append({
            "planning_demand": planning_demand,
            "route_name": route_name,
            "direction": direction,
            "direction_label": dict(
                TravelRequest.Direction.choices
            ).get(direction, direction),
            "departure_time": departure_time,
            "total_students": total_students,
            "buses_needed": buses_needed,
            "recommended_vehicles": recommended_vehicles,
            "capacity_shortfall": capacity_shortfall,
            "has_assignment_conflict": has_assignment_conflict,
            "capacity_note": capacity_note,
        })

    total_planning_demand = sum(
        row["planning_demand"] for row in report_rows
    )
    shortfall_groups = sum(
        1 for row in report_rows if row["capacity_shortfall"]
    )
    conflict_groups = sum(
        1 for row in report_rows if row["has_assignment_conflict"]
    )
    context = {
        "selected_date": selected_date,
        "report_rows": report_rows,
        "total_planning_demand": total_planning_demand,
        "shortfall_groups": shortfall_groups,
        "conflict_groups": conflict_groups,
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


# ---------------------------------------------------------------------------
# ClickCampus dashboard management workspaces
# These staff-only views provide the everyday interface; Django admin remains
# available as a secondary/backup management tool.
# ---------------------------------------------------------------------------

@staff_member_required
def manage_bookings(request):
    bookings = TravelRequest.objects.select_related(
        "student", "route", "pickup_point", "bus"
    ).order_by("-travel_date", "-departure_time", "-requested_at")

    status_filter = request.GET.get("status", "").strip()
    search_query = request.GET.get("q", "").strip()
    if status_filter in dict(TravelRequest.Status.choices):
        bookings = bookings.filter(status=status_filter)
    if search_query:
        from django.db.models import Q
        bookings = bookings.filter(
            Q(student__username__icontains=search_query)
            | Q(student__email__icontains=search_query)
            | Q(route__name__icontains=search_query)
            | Q(bus__registration_number__icontains=search_query)
        )

    if request.method == "POST":
        booking = get_object_or_404(TravelRequest, pk=request.POST.get("booking_id"))
        action = request.POST.get("action")
        if action == "cancel":
            booking.status = TravelRequest.Status.CANCELLED
            booking.save(update_fields=["status"])
            messages.success(request, "Booking cancelled.")
        elif action == "save":
            # Reuse the established admin form so direction, capacity,
            # maintenance and overlapping-assignment checks stay consistent.
            from .admin import TravelRequestAdminForm
            form = TravelRequestAdminForm(request.POST, instance=booking)
            if form.is_valid():
                form.save()
                messages.success(request, "Booking details updated.")
            else:
                messages.error(request, "Booking could not be updated: " + "; ".join(
                    str(error) for error in form.errors.values()
                ))
        return redirect("transport:manage_bookings")

    from .admin import TravelRequestAdminForm
    editing_booking = get_object_or_404(
        TravelRequest, pk=request.GET.get("edit")
    ) if request.GET.get("edit") else None
    booking_form = TravelRequestAdminForm(instance=editing_booking) if editing_booking else None

    context = {
        "page_title": "Manage Bookings",
        "item_type": "bookings",
        "booking_form": booking_form,
        "editing_booking": editing_booking,
        "page_eyebrow": "STUDENT TRANSPORT",
        "page_description": "Review student requests, update booking status and assign vehicles.",
        "bookings": bookings[:250],
        "status_choices": TravelRequest.Status.choices,
        "selected_status": status_filter,
        "search_query": search_query,
        "total_count": bookings.count(),
        "pending_count": TravelRequest.objects.filter(status=TravelRequest.Status.PENDING).count(),
        "confirmed_count": TravelRequest.objects.filter(status=TravelRequest.Status.CONFIRMED).count(),
    }
    return render(request, "transport/management.html", context)


@staff_member_required
def manage_vehicles(request):
    from .management_forms import BusManagementForm
    instance = get_object_or_404(Bus, pk=request.GET.get("edit")) if request.GET.get("edit") else None
    form = BusManagementForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vehicle saved successfully.")
        return redirect("transport:manage_vehicles")
    return render(request, "transport/management.html", {
        "page_title": "Manage Vehicles",
        "page_eyebrow": "FLEET MANAGEMENT",
        "page_description": "Register vehicles and maintain their capacity, route and operational status.",
        "form": form,
        "items": Bus.objects.select_related("route").order_by("registration_number"),
        "item_type": "vehicles",
        "editing": instance,
    })


@staff_member_required
def manage_routes(request):
    from .management_forms import RouteManagementForm
    instance = get_object_or_404(Route, pk=request.GET.get("edit")) if request.GET.get("edit") else None
    form = RouteManagementForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Route saved successfully.")
        return redirect("transport:manage_routes")
    return render(request, "transport/management.html", {
        "page_title": "Manage Routes",
        "page_eyebrow": "ROUTE NETWORK",
        "page_description": "Create and maintain the routes available to students.",
        "form": form,
        "items": Route.objects.order_by("name"),
        "item_type": "routes",
        "editing": instance,
    })


@staff_member_required
def manage_pickup_points(request):
    from .management_forms import PickupPointManagementForm
    instance = get_object_or_404(PickupPoint, pk=request.GET.get("edit")) if request.GET.get("edit") else None
    form = PickupPointManagementForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pickup point saved successfully.")
        return redirect("transport:manage_pickup_points")
    return render(request, "transport/management.html", {
        "page_title": "Pickup Points",
        "page_eyebrow": "PICKUP NETWORK",
        "page_description": "Organise pickup locations and their order along each route.",
        "form": form,
        "items": PickupPoint.objects.select_related("route").order_by("route__name", "sequence", "name"),
        "item_type": "pickup_points",
        "editing": instance,
    })
