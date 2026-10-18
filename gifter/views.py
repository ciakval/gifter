from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render


@login_not_required
def landing(request):
    if request.user.is_authenticated:
        return redirect("home")
    # `next` is only echoed into a hidden form field; allauth validates it as a safe
    # redirect target, so we never build a redirect from it ourselves.
    return render(request, "gifter/landing.html", {"next": request.GET.get("next", "")})


def home(request):
    # Login required by LoginRequiredMiddleware (no decorator needed).
    return render(request, "gifter/home.html")
