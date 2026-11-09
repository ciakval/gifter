"""The only place claim data is read or written.

Secrecy rules (SECR-01, D-13, D-15): the owner of a wish (the giftee) must never learn whether it
is claimed. So claim reads happen only on participant code paths, `claim_views_for` refuses any
wish the viewer owns, and templates receive plain dataclasses, never Claim or Contribution rows.
No function here saves a Wish, so `wish.updated_at` and every owner-visible field stay untouched.
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction

from .models import Claim, Membership

CLAIMED = "claimed"
ALREADY_YOURS = "already_yours"
TAKEN = "taken"


class SecrecyViolation(Exception):
    """Claim data was requested for a wish the viewer owns."""


@dataclass(frozen=True)
class Person:
    """A claimer or contributor as one particular viewer may see them.

    `name` None means the template shows "someone".
    """

    name: str | None
    is_you: bool
    note: str = ""


@dataclass(frozen=True)
class ClaimView:
    is_purchased: bool
    claimer: Person
    is_mine: bool


def co_member_ids(viewer) -> set[int]:
    """Ids of users who share at least one event with the viewer (the viewer included)."""
    return set(
        Membership.objects.filter(event__memberships__user=viewer).values_list(
            "user_id", flat=True
        )
    )


def _person(user, viewer, visible, note="") -> Person:
    """D-02 / CLAM-03: a name (and a note) only for people who share an event with the viewer."""
    is_you = user.pk == viewer.pk
    show = is_you or user.pk in visible
    return Person(
        name=user.display_name if show else None,
        is_you=is_you,
        note=note if show else "",
    )


def claim_views_for(viewer, wishes) -> dict[int, ClaimView]:
    """Claim state of other members' wishes, as the viewer may see it."""
    wishes = list(wishes)
    if any(wish.owner_id == viewer.pk for wish in wishes):
        raise SecrecyViolation("claim data requested for a wish the viewer owns")
    if not wishes:
        return {}
    claims = Claim.objects.filter(wish__in=wishes).select_related("claimer")
    visible = co_member_ids(viewer)
    return {
        claim.wish_id: ClaimView(
            is_purchased=claim.status == Claim.Status.PURCHASED,
            claimer=_person(claim.claimer, viewer, visible),
            is_mine=claim.claimer_id == viewer.pk,
        )
        for claim in claims
    }


def claim_wish(user, wish) -> str:
    """Try to take a wish. The unique constraint decides, never a check followed by an insert."""
    if wish.owner_id == user.pk:
        raise SecrecyViolation("a giftee cannot claim their own wish")
    try:
        with transaction.atomic():
            Claim.objects.create(wish=wish, claimer=user)
    except IntegrityError:
        if Claim.objects.filter(wish=wish, claimer=user).exists():
            return ALREADY_YOURS
        return TAKEN
    return CLAIMED
