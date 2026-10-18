from urllib.parse import urlencode

from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .inapp import is_in_app_browser


def _landing_path(**params):
    """Landing path with a query string built by urlencode (never raw concatenation)."""
    params = {key: value for key, value in params.items() if value}
    path = reverse("landing")
    return f"{path}?{urlencode(params)}" if params else path


@login_not_required
def landing(request):
    if request.user.is_authenticated:
        return redirect("home")
    # `next` is only echoed into a hidden form field or an encoded query string;
    # allauth validates it as a safe redirect target, so we never build a redirect
    # from it ourselves.
    next_url = request.GET.get("next", "")
    in_app = (
        is_in_app_browser(request.META.get("HTTP_USER_AGENT", ""))
        and request.GET.get("force") != "1"
    )
    context = {"next": next_url, "in_app": in_app}
    if in_app:
        context["copy_url"] = request.build_absolute_uri(_landing_path(next=next_url))
        context["force_url"] = _landing_path(force="1", next=next_url)
    return render(request, "gifter/landing.html", context)


def home(request):
    # Login required by LoginRequiredMiddleware (no decorator needed).
    return render(request, "gifter/home.html")
