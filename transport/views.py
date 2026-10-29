
from django.shortcuts import render


def dashboard(request):
    return render(request, "transport/dashboard.html")


def login_page(request):
    return render(request, "transport/login.html")


def register_page(request):
    return render(request, "transport/register.html")


def promotions(request):
    return render(request, "transport/promotions.html")


def create_promotion(request):
    return render(request, "transport/create_promotion.html")
def create_promotion(request):
    return render(request, "transport/create_promotion.html")