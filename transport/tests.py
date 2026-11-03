import json
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import TravelRequestAdminForm
from .models import Bus, PickupPoint, Route, TravelRequest


class TransportWorkflowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="TestPassword!234",
        )
        self.other_student = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="TestPassword!234",
        )
        self.staff = User.objects.create_user(
            username="admin",
            password="TestPassword!234",
            is_staff=True,
        )
        self.route = Route.objects.create(
            name="Route A",
            start_location="Town",
            end_location="Campus",
        )
        self.other_route = Route.objects.create(
            name="Route B",
            start_location="Westlands",
            end_location="Campus",
        )
        self.pickup = PickupPoint.objects.create(
            route=self.route,
            name="Main Stage",
        )
        self.other_pickup = PickupPoint.objects.create(
            route=self.other_route,
            name="Westlands",
        )
        self.bus = Bus.objects.create(
            registration_number="KCA 123A",
            capacity=30,
            route=self.route,
            status=Bus.Status.AVAILABLE,
        )
        self.travel_date = timezone.localdate() + timedelta(days=3)

    def booking_payload(self, **overrides):
        payload = {
            "pickup_point": str(self.pickup.pk),
            "travel_date": self.travel_date.isoformat(),
            "direction": TravelRequest.Direction.TO_SCHOOL,
            "departure_time": "06:00:00",
        }
        payload.update(overrides)
        return payload

    def test_student_can_submit_a_valid_travel_request(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("transport:create_travel_request"),
            self.booking_payload(),
        )

        self.assertRedirects(
            response,
            reverse("transport:dashboard") + "#my-trips",
            fetch_redirect_response=False,
        )
        self.assertEqual(TravelRequest.objects.count(), 1)
        booking = TravelRequest.objects.get()
        self.assertEqual(booking.student, self.student)
        self.assertEqual(booking.route, self.route)
        self.assertEqual(booking.status, TravelRequest.Status.PENDING)

    def test_duplicate_request_for_same_departure_is_rejected(self):
        self.client.force_login(self.student)
        payload = self.booking_payload()

        self.client.post(reverse("transport:create_travel_request"), payload)
        self.client.post(reverse("transport:create_travel_request"), payload)

        self.assertEqual(TravelRequest.objects.count(), 1)

    def test_invalid_pickup_point_is_rejected(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("transport:create_travel_request"),
            self.booking_payload(pickup_point="999999"),
        )

        self.assertRedirects(
            response,
            reverse("transport:dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(TravelRequest.objects.count(), 0)

    def test_invalid_direction_and_departure_combination_is_rejected(self):
        self.client.force_login(self.student)

        self.client.post(
            reverse("transport:create_travel_request"),
            self.booking_payload(
                direction=TravelRequest.Direction.FROM_SCHOOL,
                departure_time="06:00",
            ),
        )

        self.assertEqual(TravelRequest.objects.count(), 0)

    def test_student_can_cancel_their_own_booking(self):
        booking = TravelRequest.objects.create(
            student=self.student,
            route=self.route,
            pickup_point=self.pickup,
            travel_date=self.travel_date,
            direction=TravelRequest.Direction.TO_SCHOOL,
            departure_time=time(6, 0),
        )
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("transport:cancel_travel_request", args=[booking.pk])
        )

        booking.refresh_from_db()
        self.assertEqual(booking.status, TravelRequest.Status.CANCELLED)
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_cancel_another_students_booking(self):
        booking = TravelRequest.objects.create(
            student=self.other_student,
            route=self.route,
            pickup_point=self.pickup,
            travel_date=self.travel_date,
            direction=TravelRequest.Direction.TO_SCHOOL,
            departure_time=time(6, 0),
        )
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("transport:cancel_travel_request", args=[booking.pk])
        )

        booking.refresh_from_db()
        self.assertEqual(booking.status, TravelRequest.Status.PENDING)
        self.assertEqual(response.status_code, 404)

    def admin_form_payload(self, **overrides):
        payload = {
            "student": str(self.other_student.pk),
            "route": str(self.route.pk),
            "pickup_point": str(self.pickup.pk),
            "bus": str(self.bus.pk),
            "travel_date": self.travel_date.isoformat(),
            "direction": TravelRequest.Direction.TO_SCHOOL,
            "departure_time": "06:00:00",
            "status": TravelRequest.Status.CONFIRMED,
        }
        payload.update(overrides)
        return payload

    def test_same_bus_can_be_shared_by_students_on_same_departure(self):
        TravelRequest.objects.create(
            student=self.student,
            route=self.route,
            pickup_point=self.pickup,
            bus=self.bus,
            travel_date=self.travel_date,
            direction=TravelRequest.Direction.TO_SCHOOL,
            departure_time=time(6, 0),
            status=TravelRequest.Status.CONFIRMED,
        )

        form = TravelRequestAdminForm(data=self.admin_form_payload())

        self.assertTrue(form.is_valid(), form.errors)

    def test_bus_can_be_assigned_to_a_different_route(self):
        form = TravelRequestAdminForm(
            data=self.admin_form_payload(
                route=str(self.other_route.pk),
                pickup_point=str(self.other_pickup.pk),
                departure_time="09:30:00",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_bus_cannot_be_assigned_to_overlapping_different_route_journey(self):
        TravelRequest.objects.create(
            student=self.student,
            route=self.route,
            pickup_point=self.pickup,
            bus=self.bus,
            travel_date=self.travel_date,
            direction=TravelRequest.Direction.TO_SCHOOL,
            departure_time=time(6, 0),
            status=TravelRequest.Status.CONFIRMED,
        )

        form = TravelRequestAdminForm(
            data=self.admin_form_payload(
                route=str(self.other_route.pk),
                pickup_point=str(self.other_pickup.pk),
                departure_time="07:00:00",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("bus", form.errors)

    def test_staff_can_access_demand_report(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("transport:demand_report"))

        self.assertEqual(response.status_code, 200)


    def test_admin_dashboard_displays_live_kpis_and_chart_data(self):
        TravelRequest.objects.create(
            student=self.student,
            route=self.route,
            pickup_point=self.pickup,
            travel_date=self.travel_date,
            direction=TravelRequest.Direction.TO_SCHOOL,
            departure_time=time(6, 0),
            status=TravelRequest.Status.PENDING,
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("transport:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pending_requests"], 1)
        self.assertEqual(response.context["total_requests"], 1)
        booking_chart = json.loads(response.context["booking_chart_data"])
        self.assertEqual(booking_chart["labels"], ["Pending", "Confirmed", "Cancelled"])
        self.assertEqual(booking_chart["values"], [1, 0, 0])
        self.assertContains(response, "Recent transport requests")
        self.assertContains(response, "Vehicle availability")

    def test_demand_report_returns_staff_to_admin_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("transport:demand_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("transport:admin_dashboard")}"',
        )

    def test_admin_dashboard_charts_do_not_depend_on_external_cdn(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("transport:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "donut-chart")
        self.assertNotContains(response, "cdn.jsdelivr.net/npm/chart.js")

    def test_admin_dashboard_has_no_stray_script_text(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("transport:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/script>")

    def test_demand_report_renders_planning_overview(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("transport:demand_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demand &amp; Fleet Planning")
        self.assertIn("total_planning_demand", response.context)
        self.assertIn("shortfall_groups", response.context)
        self.assertIn("conflict_groups", response.context)

    def test_student_cannot_access_demand_report(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("transport:demand_report"))

        self.assertEqual(response.status_code, 302)

class PublicLandingPageTests(TestCase):
    def test_root_url_displays_public_landing_page(self):
        response = self.client.get(reverse("transport:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your campus journey.")
        self.assertContains(response, "For students")
        self.assertContains(response, "For administrators")

    def test_student_dashboard_has_its_own_url(self):
        response = self.client.get(reverse("transport:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "transport/dashboard.html")
