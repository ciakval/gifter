import datetime
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from .forms import EventForm
from .inapp import is_in_app_browser
from .models import Event, Membership

# Bump whenever privacy.html changes. The policy must be updated BEFORE a feature that
# stores or shows new kinds of data ships (see DEPLOYMENT.md).
PRIVACY_POLICY_UPDATED = datetime.date(2026, 11, 8)


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


@login_not_required
def privacy(request):
    # Public, static page: reads only two constants, never any user or wish data.
    return render(
        request,
        "gifter/privacy.html",
        {"contact_email": settings.GIFTER_CONTACT_EMAIL, "updated": PRIVACY_POLICY_UPDATED},
    )


def _member_event_or_404(user, pk):
    """The event if `user` belongs to it, else a bare 404.

    Non-members and missing ids share this one path, so their responses are identical and an
    event's existence is never revealed to an outsider.
    """
    event = Event.objects.filter(pk=pk, memberships__user=user).first()
    if event is None:
        raise Http404()
    return event


def home(request):
    # Login required by LoginRequiredMiddleware (no decorator needed).
    events = request.user.events.order_by(F("date").asc(nulls_last=True), "name", "pk")
    return render(request, "gifter/home.html", {"events": events})


def event_create(request):
    form = EventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            Membership.objects.create(event=event, user=request.user)
        messages.success(request, _("Event created."))
        return redirect("event_detail", pk=event.pk)
    return render(request, "gifter/event_form.html", {"form": form})


def event_detail(request, pk):
    event = _member_event_or_404(request.user, pk)
    memberships = event.memberships.select_related("user").order_by("joined_at", "pk")
    return render(
        request,
        "gifter/event_detail.html",
        {"event": event, "memberships": memberships},
    )
