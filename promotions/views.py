
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Promotion


@login_required
def promotions_list(request):
    today = timezone.localdate()

    promotions = Promotion.objects.filter(
        status=Promotion.Status.APPROVED,
        start_date__lte=today,
        end_date__gte=today,
    )

    return render(
        request,
        "promotions/promotions.html",
        {"promotions": promotions},
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_promotion(request):
    if request.method == "GET":
        return render(request, "promotions/create_promotion.html")

    business_name = request.POST.get("business_name", "").strip()
    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()
    offer = request.POST.get("offer", "").strip()
    location = request.POST.get("location", "").strip()
    start_date = request.POST.get("start_date", "")
    end_date = request.POST.get("end_date", "")
    image = request.FILES.get("image")

    if not all([
        business_name, title, description, offer, location,
        start_date, end_date, image,
    ]):
        messages.error(
            request,
            "Please complete all fields and select an image.",
        )
        return redirect("transport:create_promotion")

    try:
        start = timezone.datetime.strptime(
            start_date, "%Y-%m-%d"
        ).date()
        end = timezone.datetime.strptime(
            end_date, "%Y-%m-%d"
        ).date()
    except ValueError:
        messages.error(request, "Please enter valid promotion dates.")
        return redirect("transport:create_promotion")

    if start < timezone.localdate() or end < start:
        messages.error(request, "Please check the promotion dates.")
        return redirect("transport:create_promotion")

    if image.size > 5 * 1024 * 1024:
        messages.error(request, "The image must be 5 MB or smaller.")
        return redirect("transport:create_promotion")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed_types:
        messages.error(
            request,
            "Please upload a JPG, PNG, or WebP image.",
        )
        return redirect("transport:create_promotion")

    Promotion.objects.create(
        business_name=business_name,
        title=title,
        description=description,
        offer=offer,
        location=location,
        start_date=start,
        end_date=end,
        image=image,
        status=Promotion.Status.PENDING,
    )

    messages.success(
        request,
        "Your promotion has been submitted for administrator review.",
    )
    return redirect("transport:promotions")


@staff_member_required
def admin_promotions(request):
    promotions = Promotion.objects.all()

    return render(
        request,
        "admin/promotions_list.html",
        {"promotions": promotions},
    )

@staff_member_required
@require_http_methods(["POST"])
def approve_promotion(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)

    promotion.status = Promotion.Status.APPROVED
    promotion.save(update_fields=["status"])

    messages.success(
        request,
        f'"{promotion.title}" has been approved.'
    )
    return redirect("transport:admin_promotions")


@staff_member_required
@require_http_methods(["POST"])
def reject_promotion(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)

    promotion.status = Promotion.Status.REJECTED
    promotion.save(update_fields=["status"])

    messages.success(
        request,
        f'"{promotion.title}" has been rejected.'
    )
    return redirect("transport:admin_promotions")