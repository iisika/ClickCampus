from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Promotion


def make_test_png():
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="PNG")
    return SimpleUploadedFile(
        "promotion.png",
        buffer.getvalue(),
        content_type="image/png",
    )


class PromotionWorkflowTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        self.enterContext(
            override_settings(MEDIA_ROOT=self.media_directory.name)
        )

        self.student = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="TestPassword!234",
        )
        self.staff = User.objects.create_user(
            username="admin",
            password="TestPassword!234",
            is_staff=True,
        )

    def promotion_payload(self, image=None):
        today = timezone.localdate()
        return {
            "business_name": "Campus Cafe",
            "title": "Student lunch offer",
            "description": "A special lunch offer for students.",
            "offer": "10% off",
            "location": "Near campus",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=7)).isoformat(),
            "image": image or make_test_png(),
        }

    def test_logged_in_user_can_submit_valid_promotion_for_review(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("transport:create_promotion"),
            self.promotion_payload(),
        )

        self.assertRedirects(
            response,
            reverse("transport:promotions"),
            fetch_redirect_response=False,
        )
        promotion = Promotion.objects.get()
        self.assertEqual(promotion.status, Promotion.Status.PENDING)
        self.assertTrue(promotion.image.name.endswith(".png"))

    def test_invalid_image_content_is_rejected(self):
        self.client.force_login(self.student)
        fake_image = SimpleUploadedFile(
            "not-really-an-image.png",
            b"this is not an image",
            content_type="image/png",
        )

        self.client.post(
            reverse("transport:create_promotion"),
            self.promotion_payload(image=fake_image),
        )

        self.assertEqual(Promotion.objects.count(), 0)

    def test_promotion_cannot_start_in_the_past(self):
        self.client.force_login(self.student)
        yesterday = timezone.localdate() - timedelta(days=1)
        payload = self.promotion_payload()
        payload["start_date"] = yesterday.isoformat()

        self.client.post(
            reverse("transport:create_promotion"),
            payload,
        )

        self.assertEqual(Promotion.objects.count(), 0)

    def test_staff_can_approve_promotion(self):
        today = timezone.localdate()
        promotion = Promotion.objects.create(
            business_name="Campus Cafe",
            title="Student offer",
            description="Offer details",
            offer="10% off",
            location="Near campus",
            start_date=today,
            end_date=today + timedelta(days=7),
            image=make_test_png(),
            status=Promotion.Status.PENDING,
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("transport:approve_promotion", args=[promotion.pk])
        )

        promotion.refresh_from_db()
        self.assertEqual(promotion.status, Promotion.Status.APPROVED)
        self.assertEqual(response.status_code, 302)

    def test_non_staff_cannot_approve_promotion(self):
        today = timezone.localdate()
        promotion = Promotion.objects.create(
            business_name="Campus Cafe",
            title="Student offer",
            description="Offer details",
            offer="10% off",
            location="Near campus",
            start_date=today,
            end_date=today + timedelta(days=7),
            image=make_test_png(),
            status=Promotion.Status.PENDING,
        )
        self.client.force_login(self.student)

        self.client.post(
            reverse("transport:approve_promotion", args=[promotion.pk])
        )

        promotion.refresh_from_db()
        self.assertEqual(promotion.status, Promotion.Status.PENDING)
