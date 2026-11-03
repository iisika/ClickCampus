from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import StudentProfile


class RegistrationAndLoginTests(TestCase):
    def test_student_can_register(self):
        response = self.client.post(
            reverse("transport:register"),
            {
                "full_name": "Taylor Student",
                "email": "taylor@example.com",
                "registration_number": "STU-001",
                "password": "SafeTestPassword!234",
                "confirm_password": "SafeTestPassword!234",
            },
        )

        self.assertRedirects(
            response,
            reverse("transport:login"),
            fetch_redirect_response=False,
        )
        user = User.objects.get(username="taylor@example.com")
        self.assertTrue(user.check_password("SafeTestPassword!234"))
        self.assertTrue(
            StudentProfile.objects.filter(
                user=user,
                registration_number="STU-001",
            ).exists()
        )

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("transport:register"),
            {
                "full_name": "Taylor Student",
                "email": "taylor@example.com",
                "registration_number": "STU-001",
                "password": "SafeTestPassword!234",
                "confirm_password": "DifferentPassword!234",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="taylor@example.com").exists())

    def test_student_can_log_in_with_email_and_password(self):
        User.objects.create_user(
            username="taylor@example.com",
            email="taylor@example.com",
            password="SafeTestPassword!234",
        )

        response = self.client.post(
            reverse("transport:login"),
            {
                "email": "taylor@example.com",
                "password": "SafeTestPassword!234",
            },
        )

        self.assertRedirects(
            response,
            reverse("transport:dashboard"),
            fetch_redirect_response=False,
        )

    def test_staff_login_redirects_to_admin_dashboard(self):
        User.objects.create_user(
            username="admin",
            password="SafeTestPassword!234",
            is_staff=True,
        )

        response = self.client.post(
            reverse("transport:login"),
            {
                "email": "admin",
                "password": "SafeTestPassword!234",
            },
        )

        self.assertRedirects(
            response,
            reverse("transport:admin_dashboard"),
            fetch_redirect_response=False,
        )

    def test_already_authenticated_staff_visiting_login_goes_to_admin(self):
        staff = User.objects.create_user(
            username="admin",
            password="SafeTestPassword!234",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("transport:login"))

        self.assertRedirects(
            response,
            reverse("transport:admin_dashboard"),
            fetch_redirect_response=False,
        )
