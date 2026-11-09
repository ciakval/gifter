"""The only place claim data is read or written.

Secrecy rules (SECR-01, D-13, D-15): the owner of a wish (the giftee) must never learn whether it
is claimed. So claim reads happen only on participant code paths, `claim_views_for` refuses any
wish the viewer owns, and templates receive plain dataclasses, never Claim or Contribution rows.
No function here saves a Wish, so `wish.updated_at` and every owner-visible field stay untouched.
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from .models import Claim, Contribution, Membership, Wish

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
    changed: bool = False


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
        .select_related("claimer", "wish")
        .prefetch_related(_ordered_contributions())
    )
    visible = co_member_ids(viewer)
    return {claim.wish_id: _claim_view(claim, viewer, visible) for claim in claims}


def _claim_view(claim, viewer, visible) -> ClaimView:
    """One claim as `viewer` may see it. `claim.wish` and ordered contributions are preloaded."""
    contributions = list(claim.contributions.all())
    is_mine = claim.claimer_id == viewer.pk
    mine = next((c for c in contributions if c.user_id == viewer.pk), None)
    acknowledged_at = claim.acknowledged_at if is_mine else mine.acknowledged_at if mine else None
    changed = (
        acknowledged_at is not None
        and claim.wish.status == Wish.Status.ACTIVE
        and claim.wish.updated_at > acknowledged_at
    )
    return ClaimView(
        is_purchased=claim.status == Claim.Status.PURCHASED,
        claimer=_person(claim.claimer, viewer, visible),
        is_mine=is_mine,
        contributors=tuple(_person(c.user, viewer, visible, c.note) for c in contributions),
        i_contribute=mine is not None,
        can_chip_in=not is_mine and mine is None,
        changed=changed,
    )


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


def acknowledge(user, wish_pk) -> bool:
    """"Got it": the user has seen the owner's latest edit (D-08)."""
    now = timezone.now()
    updated = Claim.objects.filter(wish_id=wish_pk, claimer=user).update(acknowledged_at=now)
    updated += Contribution.objects.filter(claim__wish_id=wish_pk, user=user).update(
        acknowledged_at=now
    )
    return updated > 0


ROLE_CLAIMER = "claimer"
ROLE_CONTRIBUTOR = "contributor"
_STATE_RANK = {"active": 0, "withdrawn": 1, "received": 2}


@dataclass(frozen=True)
class MyClaimRow:
    wish: Wish
    owner_name: str
    role: str
    view: ClaimView
    state: str


def my_claims_for(viewer) -> list[MyClaimRow]:
    """Everything the viewer claimed or chipped in on, whatever the wish's current sharing (D-05).

    Queries go straight to Claim and Contribution by user, never through event visibility, so
    un-shared, withdrawn and received wishes stay listed. A giftee is never involved with their
    own wish; the exclusions are belt and braces.
    """
    visible = co_member_ids(viewer)
    ordered = _ordered_contributions()
    own_claims = (
        Claim.objects.filter(claimer=viewer)
        .exclude(wish__owner=viewer)
        .select_related("wish__owner", "claimer")
        .prefetch_related(ordered)
    )
    own_contributions = (
        Contribution.objects.filter(user=viewer)
        .exclude(claim__wish__owner=viewer)
        .select_related("claim__wish__owner", "claim__claimer")
        .prefetch_related(Prefetch("claim__contributions", queryset=ordered.queryset))
    )
    keyed = []
    for claim in own_claims:
        keyed.append((claim.created_at, claim.pk, ROLE_CLAIMER, claim))
    for contribution in own_contributions:
        keyed.append(
            (contribution.created_at, contribution.pk, ROLE_CONTRIBUTOR, contribution.claim)
        )
    rows = []
    for _when, _pk, role, claim in sorted(keyed, key=lambda k: (k[0], k[1]), reverse=True):
        rows.append(
            MyClaimRow(
                wish=claim.wish,
                owner_name=claim.wish.owner.display_name,
                role=role,
                view=_claim_view(claim, viewer, visible),
                state=claim.wish.status,
            )
        )
    # Stable sort: active, withdrawn, received; newest involvement first inside each group.
    rows.sort(key=lambda row: _STATE_RANK.get(row.state, 0))
    return rows
