
from django.db import models
from django.contrib.auth.models import User


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile"
    )
    registration_number = models.CharField(
        max_length=50,
        unique=True
    )

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.registration_number})"
