
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone


class Promotion(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    business_name = models.CharField(max_length=150)
    title = models.CharField(max_length=150)
    description = models.TextField()
    offer = models.CharField(max_length=150)
    location = models.CharField(max_length=200)

    start_date = models.DateField()
    end_date = models.DateField()

    image = models.ImageField(
        upload_to="promotions/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"]
            )
        ],
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} — {self.business_name}"

    @property
    def is_active(self):
        today = timezone.localdate()
        return (
            self.status == self.Status.APPROVED
            and self.start_date <= today <= self.end_date
        )
