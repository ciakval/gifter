"""The only place claim data is read or written.

Secrecy rules (SECR-01, D-13, D-15): the owner of a wish (the giftee) must never learn whether it
is claimed. So claim reads happen only on participant code paths, `claim_views_for` refuses any
wish the viewer owns, and templates receive plain dataclasses, never Claim or Contribution rows.
No function here saves a Wish, so `wish.updated_at` and every owner-visible field stay untouched.
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Prefetch

from .models import Claim, Contribution, Membership

CLAIMED = "claimed"
ALREADY_YOURS = "already_yours"
TAKEN = "taken"
JOINED = "joined"
NO_CLAIM = "no_claim"
OWN_CLAIM = "own_claim"
CHANGED = "changed"
HANDED_OVER = "handed_over"
FREED = "freed"


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
    contributors: tuple[Person, ...] = ()
    i_contribute: bool = False
    can_chip_in: bool = False


def _ordered_contributions():
    return Prefetch(
        "contributions",
        queryset=Contribution.objects.select_related("user").order_by("created_at", "pk"),
    )


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
    claims = (
        Claim.objects.filter(wish__in=wishes)
        .select_related("claimer")
        .prefetch_related(_ordered_contributions())
    )
    visible = co_member_ids(viewer)
    views = {}
    for claim in claims:
        contributions = list(claim.contributions.all())
        is_mine = claim.claimer_id == viewer.pk
        i_contribute = any(c.user_id == viewer.pk for c in contributions)
        views[claim.wish_id] = ClaimView(
            is_purchased=claim.status == Claim.Status.PURCHASED,
            claimer=_person(claim.claimer, viewer, visible),
            is_mine=is_mine,
            contributors=tuple(_person(c.user, viewer, visible, c.note) for c in contributions),
            i_contribute=i_contribute,
            can_chip_in=not is_mine and not i_contribute,
        )
    return views


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


def chip_in(user, wish, note) -> str:
    """Join someone's claim. Repeating it keeps one row and replaces the note."""
    if wish.owner_id == user.pk:
        raise SecrecyViolation("a giftee cannot chip in on their own wish")
    claim = Claim.objects.filter(wish=wish).first()
    if claim is None:
        return NO_CLAIM
    if claim.claimer_id == user.pk:
        return OWN_CLAIM
    try:
        with transaction.atomic():
            contribution, created = Contribution.objects.get_or_create(
                claim=claim, user=user, defaults={"note": note}
            )
            if not created and contribution.note != note:
                contribution.note = note
                contribution.save(update_fields=["note"])
    except IntegrityError:
        # The claim vanished between the lookup and the insert.
        return CHANGED
    return JOINED


def mark_purchased(user, wish_pk) -> bool:
    with transaction.atomic():
        claim = Claim.objects.filter(wish_id=wish_pk, claimer=user).first()
        if claim is None:
            return False
        claim.status = Claim.Status.PURCHASED
        claim.save(update_fields=["status"])
    return True


def release_claim(user, wish_pk) -> str | None:
    """Give up a claim (D-06): the earliest contributor takes over, or the wish is free again."""
    with transaction.atomic():
        claim = Claim.objects.filter(wish_id=wish_pk, claimer=user).first()
        if claim is None:
            return None
        successor = claim.contributions.select_related("user").order_by("created_at", "pk").first()
        if successor is None:
            claim.delete()
            return FREED
        claim.claimer = successor.user
        claim.status = Claim.Status.RESERVED
        claim.acknowledged_at = successor.acknowledged_at
        claim.save(update_fields=["claimer", "status", "acknowledged_at"])
        successor.delete()
        return HANDED_OVER


def leave_contribution(user, wish_pk) -> bool:
    deleted, _by_model = Contribution.objects.filter(claim__wish_id=wish_pk, user=user).delete()
    return deleted > 0
