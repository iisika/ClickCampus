
from django.urls import path
from . import views

app_name = "transport"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register_page, name="register"),
]
