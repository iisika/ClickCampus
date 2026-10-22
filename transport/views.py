
from django.shortcuts import render

def dashboard(request):
    return render(request, "transport/dashboard.html")

def login_page(request):
    return render(request, "transport/login.html")

def register_page(request):
    return render(request, "transport/register.html")
