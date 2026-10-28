
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .forms import RegistrationForm


def register_page(request):
    if request.user.is_authenticated:
        return redirect("transport:dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Account created successfully. You can now log in."
            )
            return redirect("transport:login")
    else:
        form = RegistrationForm()

    return render(
        request,
        "transport/register.html",
        {"form": form}
    )


def login_page(request):
    if request.user.is_authenticated:
        return redirect("transport:dashboard")

    if request.method == "POST":
        username_or_email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username_or_email,
            password=password
        )

        if user is None:
            matching_users = User.objects.filter(
                email__iexact=username_or_email
            )

            if matching_users.count() == 1:
                user = authenticate(
                    request,
                    username=matching_users.first().username,
                    password=password
                )

        if user is not None:
            login(request, user)
            return redirect("transport:dashboard")

        messages.error(request, "Invalid email/username or password.")

    return render(request, "transport/login.html")


def logout_page(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")

    return redirect("transport:login")
