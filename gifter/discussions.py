"""The only place discussion data is read or written.

Secrecy rules (DISC-04, D-05): the person a discussion is about (the giftee: a wish's owner, or
the member a person-thread is about) must never learn that a thread or comment exists. So every
public function here refuses with `SecrecyViolation` when the viewer is that person, and
templates receive plain dataclasses, never Thread or Comment rows. Nothing here saves a Wish,
Event or Membership, so no owner-visible field changes.
"""

from dataclasses import dataclass
from datetime import datetime

from .claims import SecrecyViolation
from .models import Comment, Thread


@dataclass(frozen=True)
class CommentView:
    pk: int
    author_name: str
    is_mine: bool
    body: str
    created_at: datetime


def _find_thread(event, giftee_id, wish):
    """Read-only lookup. Never creates anything."""
    if wish is not None:
        return Thread.objects.filter(event=event, wish=wish).first()
    return Thread.objects.filter(event=event, wish__isnull=True, giftee_id=giftee_id).first()


def _read(viewer, event, giftee_id, wish) -> tuple[CommentView, ...]:
    if viewer.pk == giftee_id:
        raise SecrecyViolation("The person a discussion is about may not read it.")
    thread = _find_thread(event, giftee_id, wish)
    if thread is None:
        return ()
    comments = Comment.objects.filter(thread=thread).select_related("author").order_by(
        "created_at", "pk"
    )
    return tuple(
        CommentView(
            pk=comment.pk,
            author_name=comment.author.display_name,
            is_mine=comment.author_id == viewer.pk,
            body=comment.body,
            created_at=comment.created_at,
        )
        for comment in comments
    )


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
