
from django.urls import path
from . import views
from accounts import views as account_views

app_name = "transport"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "demand-report/",
        views.demand_report,
        name="demand_report",
    ),
    path("login/", account_views.login_page, name="login"),
    path("register/", account_views.register_page, name="register"),
    path("logout/", account_views.logout_page, name="logout"),
    path(
        "book-transport/",
        views.create_travel_request,
        name="create_travel_request",
    ),
    path(
        "my-trips/<int:request_id>/cancel/",
        views.cancel_travel_request,
        name="cancel_travel_request",
    ),
    path(
    "admin-dashboard/",
    views.admin_dashboard,
    name="admin_dashboard",
    ),
]
