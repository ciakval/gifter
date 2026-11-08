import datetime
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
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
    next_url = request.GET.get("next", "")
    if request.user.is_authenticated:
        # A copied in-app-browser link like /?next=/invite/T/ must still reach its target when
        # opened in an already signed-in browser; only same-site targets are followed.
        # The admin sends signed-in non-staff users to its login page, which redirects here with
        # next=<admin path>; following that would loop, so admin targets are never followed.
        if (
            next_url
            and not next_url.startswith(reverse("admin:index"))
            and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            )
        ):
            return redirect(next_url)
        return redirect("home")
    # For signed-out visitors `next` is only echoed into a hidden form field or an encoded
    # query string; allauth validates it as a safe redirect target on sign-in.
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
    # Session fallback for an invite whose `next` was lost during sign-in: forward once.
    token = request.session.pop("pending_invite", None)
    if token and not Membership.objects.filter(
        event__invite_token=token, user=request.user
    ).exists():
        if Event.objects.filter(invite_token=token).exists():
            return redirect("invite", token=token)
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
    invite_url = request.build_absolute_uri(reverse("invite", args=[event.invite_token]))
    return render(
        request,
        "gifter/event_detail.html",
        {"event": event, "memberships": memberships, "invite_url": invite_url},
    )


@login_not_required
def invite(request, token):
    # Must run for signed-out visitors so the token can be kept in the session. Anonymous
    # requests (people, chat-app preview bots) get the same redirect for every token, so
    # nothing about an event is revealed and token validity cannot be probed.
    if not request.user.is_authenticated:
        request.session["pending_invite"] = token
        return redirect_to_login(request.get_full_path())
    event = get_object_or_404(Event, invite_token=token)
    if request.session.get("pending_invite") == token:
        del request.session["pending_invite"]
    if request.method == "POST":
        _membership, created = Membership.objects.get_or_create(event=event, user=request.user)
        if created:
            messages.success(request, _("You joined %(event)s.") % {"event": event.name})
        return redirect(reverse("event_detail", args=[event.pk]) + "?joined=1")
    return render(
        request,
        "gifter/invite.html",
        {
            "event": event,
            "already_member": event.memberships.filter(user=request.user).exists(),
            "member_count": event.memberships.count(),
            "creator_name": event.created_by.display_name if event.created_by else None,
        },
    )
