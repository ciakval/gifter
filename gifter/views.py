import datetime
import re
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import redirect_to_login
from django.db import DatabaseError, connection, transaction
from django.db.models import F
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from .claims import claim_views_for
from .forms import EventForm, WishForm
from .inapp import is_in_app_browser
from .models import Event, Membership, Wish

# Bump whenever privacy.html changes. The policy must be updated BEFORE a feature that
# stores or shows new kinds of data ships (see DEPLOYMENT.md).
PRIVACY_POLICY_UPDATED = datetime.date(2026, 11, 10)

# File in DATA_DIR written once by scripts/gifter-backup.sh (plan 04-02) after the first
# successful NIGHTLY backup, never by manual copies. While it is missing or not a valid
# YYYY-MM-DD date the privacy page says nothing about nightly backups (fail closed).
NIGHTLY_BACKUPS_MARKER = "nightly-backups-since"


def _nightly_backups_since():
    """The date of the first nightly backup, or None when the marker is missing or unusable."""
    try:
        text = (Path(settings.DATA_DIR) / NIGHTLY_BACKUPS_MARKER).read_text(encoding="utf-8")
        text = text.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return None
        return datetime.date.fromisoformat(text)
    except (OSError, ValueError):
        return None


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
@require_safe
@never_cache
def healthz(request):
    # Public on purpose and shows no data, version or error text (D-16); no template, no session.
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("unavailable", status=503, content_type="text/plain; charset=utf-8")
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")


@login_not_required
def privacy(request):
    # Public page: reads two constants and the backup marker file, never any user or wish data.
    since = _nightly_backups_since()
    updated = max(PRIVACY_POLICY_UPDATED, since) if since else PRIVACY_POLICY_UPDATED
    return render(
        request,
        "gifter/privacy.html",
        {
            "contact_email": settings.GIFTER_CONTACT_EMAIL,
            "updated": updated,
            "nightly_backups_since": since,
        },
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
    # Participant view: other members' active wishes explicitly shared into this event.
    shared = list(
        Wish.objects.filter(
            events=event, status=Wish.Status.ACTIVE, owner__memberships__event=event
        )
        .exclude(owner=request.user)
        .order_by("priority", "-created_at", "-pk")
    )
    # The only claim read on this page: other members' wishes, viewer excluded.
    claim_map = claim_views_for(request.user, shared)
    by_owner = {}
    for wish in shared:
        by_owner.setdefault(wish.owner_id, []).append(
            {"wish": wish, "claim": claim_map.get(wish.pk)}
        )
    member_cards = [
        {"user": membership.user, "items": by_owner.get(membership.user_id, [])}
        for membership in memberships
        if membership.user_id != request.user.pk
    ]
    # Owner view: the viewer's own shared wishes, in plain owner markup (no claim information).
    own_wishes = request.user.wishes.filter(events=event, status=Wish.Status.ACTIVE).order_by(
        "priority", "-created_at", "-pk"
    )
    return render(
        request,
        "gifter/event_detail.html",
        {
            "event": event,
            "memberships": memberships,
            "invite_url": invite_url,
            "member_cards": member_cards,
            "own_wishes": own_wishes,
            "joined": request.GET.get("joined") == "1",
            "has_active_wishes": request.user.wishes.filter(status=Wish.Status.ACTIVE).exists(),
        },
    )


@require_POST
def event_share_all(request, pk):
    event = _member_event_or_404(request.user, pk)
    wishes = list(request.user.wishes.filter(status=Wish.Status.ACTIVE))
    if not wishes:
        messages.info(request, _("You have no wishes to share yet."))
    else:
        # Idempotent: the through table is unique per wish and event. Touches only this event.
        event.wishes.add(*wishes)
        count = len(wishes)
        messages.success(
            request,
            ngettext(
                "%(count)d wish is shared here now.",
                "%(count)d wishes are shared here now.",
                count,
            )
            % {"count": count},
        )
    return redirect("event_detail", pk=event.pk)


def wishlist(request):
    wishes = (
        request.user.wishes.filter(status=Wish.Status.ACTIVE)
        .prefetch_related("events")
        .order_by("priority", "-created_at", "-pk")
    )
    # LIFE-01 ordering: priority, then newest. Never by receipt time and never by claim data.
    received_wishes = (
        request.user.wishes.filter(status=Wish.Status.RECEIVED)
        .prefetch_related("events")
        .order_by("priority", "-created_at", "-pk")
    )
    return render(
        request,
        "gifter/wishlist.html",
        {"wishes": wishes, "received_wishes": received_wishes},
    )


@require_POST
def wish_received(request, pk):
    # Owner path: never imports claim code and never touches claims (D-12). Status only, so
    # updated_at stays put and claimers get no false "changed" marker. Repeating is a no-op.
    wish = get_object_or_404(
        Wish,
        pk=pk,
        owner=request.user,
        status__in=[Wish.Status.ACTIVE, Wish.Status.RECEIVED],
    )
    wish.status = Wish.Status.RECEIVED
    wish.save(update_fields=["status"])
    messages.success(request, _("Marked as received."))
    return redirect("wishlist")


@require_POST
def wish_reopen(request, pk):
    wish = get_object_or_404(
        Wish,
        pk=pk,
        owner=request.user,
        status__in=[Wish.Status.RECEIVED, Wish.Status.ACTIVE],
    )
    wish.status = Wish.Status.ACTIVE
    wish.save(update_fields=["status"])
    messages.success(request, _("Wish reopened."))
    return redirect("wishlist")


def wish_create(request):
    form = WishForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            wish = form.save(commit=False)
            wish.owner = request.user
            wish.save()
            form.save_m2m()
        messages.success(request, _("Wish added."))
        return redirect("wishlist")
    return render(request, "gifter/wish_form.html", {"form": form})


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


def wish_edit(request, pk):
    wish = get_object_or_404(Wish, pk=pk, owner=request.user, status=Wish.Status.ACTIVE)
    # Recorded before validation: ModelForm validation copies cleaned data onto the instance.
    content_before = (wish.name, wish.description, wish.priority, wish.links)
    form = WishForm(request.POST or None, instance=wish, owner=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            wish = form.save(commit=False)
            fields = ["name", "description", "priority", "links"]
            # A share-only edit leaves updated_at alone, so it raises no "changed" notice for
            # people who claimed the wish. Status is never written: a racing delete must stick.
            if content_before != (wish.name, wish.description, wish.priority, wish.links):
                fields.append("updated_at")
            wish.save(update_fields=fields)
            form.save_m2m()
        messages.success(request, _("Wish saved."))
        return redirect("wishlist")
    return render(request, "gifter/wish_form.html", {"form": form, "is_edit": True})


def wish_delete(request, pk):
    if request.method == "POST":
        # Any status, so a repeated delete is a harmless no-op with the same outcome.
        wish = get_object_or_404(Wish, pk=pk, owner=request.user)
        wish.status = Wish.Status.WITHDRAWN
        wish.save(update_fields=["status", "updated_at"])
        messages.success(request, _("Wish deleted."))
        return redirect("wishlist")
    wish = get_object_or_404(Wish, pk=pk, owner=request.user, status=Wish.Status.ACTIVE)
    return render(request, "gifter/wish_confirm_delete.html", {"wish": wish})
