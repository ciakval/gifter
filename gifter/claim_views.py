"""Participant claim views (Phase 3). Owner pages never import this module."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import claims
from .forms import ChipInForm
from .models import Wish
from .views import _member_event_or_404


def _participant_wish_or_404(user, event_pk, wish_pk):
    """The wish if `user` may act on it as a participant, else one bare 404 (D-15).

    Membership, sharing into this event, active status, owner membership and "not the viewer's
    own wish" are all decided here, before any claim is read. The wish's owner, a non-member, a
    missing event or wish and a wish not shared into this event all end on the same path.
    """
    event = _member_event_or_404(user, event_pk)
    wish = (
        Wish.objects.filter(
            pk=wish_pk,
            events=event,
            status=Wish.Status.ACTIVE,
            owner__memberships__event=event,
        )
        .exclude(owner=user)
        .first()
    )
    if wish is None:
        raise Http404()
    return event, wish


FALLBACK = "home"


def _back(request, fallback_name):
    """Back to a same-site `next`, else to the fallback page (no open redirect)."""
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(fallback_name)


def _event_anchor(event, wish):
    return reverse("event_detail", args=[event.pk]) + f"#wish-{wish.pk}"


@require_POST
def wish_claim(request, pk, wish_pk):
    event, wish = _participant_wish_or_404(request.user, pk, wish_pk)
    outcome = claims.claim_wish(request.user, wish)
    if outcome == claims.CLAIMED:
        messages.success(request, _("You are getting this one."))
    elif outcome == claims.TAKEN:
        messages.warning(request, _("Someone just took it."))
    return redirect(_event_anchor(event, wish))


@require_POST
def wish_chip_in(request, pk, wish_pk):
    event, wish = _participant_wish_or_404(request.user, pk, wish_pk)
    form = ChipInForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors["note"][0])
        return redirect(_event_anchor(event, wish))
    outcome = claims.chip_in(request.user, wish, form.cleaned_data["note"])
    if outcome == claims.JOINED:
        messages.success(request, _("You are chipping in."))
    elif outcome == claims.NO_CLAIM:
        messages.warning(request, _("This wish is free again."))
    elif outcome == claims.OWN_CLAIM:
        messages.info(request, _("You are already getting this one."))
    else:
        messages.warning(request, _("This wish just changed. Please look at it again."))
    return redirect(_event_anchor(event, wish))


@require_POST
def claim_purchased(request, wish_pk):
    if not claims.mark_purchased(request.user, wish_pk):
        raise Http404()
    messages.success(request, _("Marked as purchased."))
    return _back(request, FALLBACK)


@require_POST
def claim_release(request, wish_pk):
    if claims.release_claim(request.user, wish_pk) is None:
        raise Http404()
    messages.success(request, _("You released it."))
    return _back(request, FALLBACK)


@require_POST
def chip_in_leave(request, wish_pk):
    if not claims.leave_contribution(request.user, wish_pk):
        raise Http404()
    messages.success(request, _("You stopped chipping in."))
    return _back(request, FALLBACK)
