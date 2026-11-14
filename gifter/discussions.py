"""The only place discussion data is read or written.

Secrecy rules (DISC-04, D-05): the person a discussion is about (the giftee: a wish's owner, or
the member a person-thread is about) must never learn that a thread or comment exists. So every
public function here refuses with `SecrecyViolation` when the viewer is that person, and
templates receive plain dataclasses, never Thread or Comment rows. Nothing here saves a Wish,
Event or Membership, so no owner-visible field changes.

Opening a thread is the viewer's read receipt (D-04, P-05): `_read` upserts the viewer's own
`ThreadVisit` row. It is the one write on a GET in the app. It runs only after the view's gate
has passed, touches only the viewer's own row, and `_read` still refuses the giftee first.
"""

from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from .claims import SecrecyViolation
from .models import Comment, Thread, ThreadVisit


@dataclass(frozen=True)
class CommentView:
    pk: int
    author_name: str
    is_mine: bool
    body: str
    created_at: datetime
    is_new: bool = False


@dataclass(frozen=True)
class ThreadSummary:
    count: int = 0
    new: int = 0


NO_DISCUSSION = ThreadSummary()


@dataclass(frozen=True)
class Summaries:
    wishes: dict[int, ThreadSummary]
    members: dict[int, ThreadSummary]


def _find_thread(event, giftee_id, wish):
    """Read-only lookup. Never creates anything."""
    if wish is not None:
        return Thread.objects.filter(event=event, wish=wish).first()
    return Thread.objects.filter(event=event, wish__isnull=True, giftee_id=giftee_id).first()


def _read(viewer, event, giftee_id, wish) -> tuple[CommentView, ...]:
    if viewer.pk == giftee_id:
        raise SecrecyViolation("The person a discussion is about may not read it.")
    now = timezone.now()
    thread = _find_thread(event, giftee_id, wish)
    if thread is None:
        return ()
    visit = ThreadVisit.objects.filter(thread=thread, user=viewer).first()
    previous = visit.last_seen_at if visit else None
    comments = Comment.objects.filter(thread=thread).select_related("author").order_by(
        "created_at", "pk"
    )
    views = tuple(
        CommentView(
            pk=comment.pk,
            author_name=comment.author.display_name,
            is_mine=comment.author_id == viewer.pk,
            body=comment.body,
            created_at=comment.created_at,
            is_new=comment.author_id != viewer.pk
            and (previous is None or comment.created_at > previous),
        )
        for comment in comments
    )
    # Read receipt: only the viewer's own row, only after the gate. Taken before the read so a
    # comment landing during it still counts as new next time. Two racing tabs are harmless.
    try:
        with transaction.atomic():
            ThreadVisit.objects.update_or_create(
                thread=thread, user=viewer, defaults={"last_seen_at": now}
            )
    except IntegrityError:
        pass
    return views


def summaries_for(viewer, event) -> Summaries:
    """Counts and unseen counts per thread for the event page, never the bodies.

    Threads about the viewer are excluded in the query, so they are never loaded (D-05). At most
    three queries however many threads exist.
    """
    threads = list(
        Thread.objects.filter(event=event)
        .exclude(giftee=viewer)
        .values_list("pk", "wish_id", "giftee_id")
    )
    if not threads:
        return Summaries(wishes={}, members={})
    ids = [pk for pk, _w, _g in threads]
    seen = dict(
        ThreadVisit.objects.filter(thread_id__in=ids, user=viewer).values_list(
            "thread_id", "last_seen_at"
        )
    )
    counts = {pk: [0, 0] for pk in ids}
    for thread_id, author_id, created_at in Comment.objects.filter(
        thread_id__in=ids
    ).values_list("thread_id", "author_id", "created_at"):
        entry = counts[thread_id]
        entry[0] += 1
        last = seen.get(thread_id)
        if author_id != viewer.pk and (last is None or created_at > last):
            entry[1] += 1
    wishes, members = {}, {}
    for pk, wish_id, giftee_id in threads:
        summary = ThreadSummary(count=counts[pk][0], new=counts[pk][1])
        if wish_id is not None:
            wishes[wish_id] = summary
        else:
            members[giftee_id] = summary
    return Summaries(wishes=wishes, members=members)


def delete_comment(user, comment_pk) -> bool:
    """Delete the user's own comment (D-03). Only the author can; any miss (not found, someone
    else's) is the same False, so the route is one uniform 404 and cannot probe threads. The
    giftee can never be the author in a thread about themselves: they cannot reach it (D-05)."""
    deleted, _by_model = Comment.objects.filter(pk=comment_pk, author=user).delete()
    return deleted > 0


def _post(viewer, event, giftee_id, wish, body) -> int:
    if viewer.pk == giftee_id:
        raise SecrecyViolation("The person a discussion is about may not write in it.")
    if wish is not None:
        thread, _ = Thread.objects.get_or_create(
            event=event, wish=wish, defaults={"giftee_id": giftee_id}
        )
    else:
        thread, _ = Thread.objects.get_or_create(event=event, wish=None, giftee_id=giftee_id)
    return Comment.objects.create(thread=thread, author=viewer, body=body).pk


def read_wish_thread(viewer, event, wish):
    return _read(viewer, event, wish.owner_id, wish)


def post_wish_comment(viewer, event, wish, body) -> int:
    return _post(viewer, event, wish.owner_id, wish, body)


def read_member_thread(viewer, event, member):
    return _read(viewer, event, member.pk, None)


def post_member_comment(viewer, event, member, body) -> int:
    return _post(viewer, event, member.pk, None, body)
