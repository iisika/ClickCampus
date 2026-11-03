from django import forms
from .models import Bus, Route, PickupPoint

class BusManagementForm(forms.ModelForm):
    class Meta:
        model = Bus
        fields = ("registration_number", "capacity", "route", "status")
        widgets = {"registration_number": forms.TextInput(attrs={"placeholder": "e.g. KDA 123A"})}

class RouteManagementForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ("name", "start_location", "end_location", "description", "is_active")

class PickupPointManagementForm(forms.ModelForm):
    class Meta:
        model = PickupPoint
        fields = ("route", "name", "description", "sequence", "latitude", "longitude")
