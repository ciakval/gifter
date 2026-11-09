"""Participant claim views (Phase 3). Owner pages never import this module."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import claims
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
