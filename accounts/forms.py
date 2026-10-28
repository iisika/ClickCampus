
from django import forms
from django.contrib.auth.models import User
from django.db import transaction
from .models import StudentProfile


class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    registration_number = forms.CharField(max_length=50)
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    def clean_registration_number(self):
        number = self.cleaned_data["registration_number"].strip()

        if StudentProfile.objects.filter(
            registration_number__iexact=number
        ).exists():
            raise forms.ValidationError(
                "This student registration number is already registered."
            )

        return number

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error(
                "confirm_password",
                "Passwords do not match."
            )

        return cleaned_data

    @transaction.atomic
    def save(self):
        full_name = self.cleaned_data["full_name"].strip()
        name_parts = full_name.split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        email = self.cleaned_data["email"]

        user = User(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_password(self.cleaned_data["password"])
        user.save()

        StudentProfile.objects.create(
            user=user,
            registration_number=self.cleaned_data[
                "registration_number"
            ].strip()
        )

        return user
