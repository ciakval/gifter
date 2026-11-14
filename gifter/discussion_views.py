"""Participant discussion views (Phase 5). Owner pages never import this module."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext
from django.views.decorators.http import require_http_methods, require_POST

from . import discussions
from .claim_views import _back, _participant_wish_or_404
from .forms import CommentForm
from .views import _member_event_or_404


def _thread_page(request, event, wish, member, heading, person_name, read, post, thread_url):
    form = CommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pk = post(form.cleaned_data["body"])
        return redirect(f"{thread_url}#comment-{pk}")
    return render(
        request,
        "gifter/discussion.html",
        {
            "event": event,
            "wish": wish,
            "heading": heading,
            "person_name": person_name,
            "comments": read(),
            "form": form,
            "thread_url": thread_url,
        },
    )


@require_http_methods(["GET", "POST"])
def wish_discussion(request, pk, wish_pk):
    # The gate comes first: the owner, non-members, missing ids and un-shared, withdrawn or
    # received wishes all end on the one bare 404, before any discussion is read or written.
    event, wish = _participant_wish_or_404(request.user, pk, wish_pk)
    return _thread_page(
        request,
        event,
        wish,
        None,
        heading=wish.name,
        person_name=wish.owner.display_name,
        read=lambda: discussions.read_wish_thread(request.user, event, wish),
        post=lambda body: discussions.post_wish_comment(request.user, event, wish, body),
        thread_url=reverse("wish_discussion", args=[event.pk, wish.pk]),
    )


@require_http_methods(["GET", "POST"])
def member_discussion(request, pk, user_pk):
    event = _member_event_or_404(request.user, pk)
    member = (
        get_user_model()
        .objects.filter(pk=user_pk, memberships__event=event)
        .exclude(pk=request.user.pk)
        .first()
    )
    if member is None:
        raise Http404()
    return _thread_page(
        request,
        event,
        None,
        member,
        heading=gettext("Discussion: %(name)s") % {"name": member.display_name},
        person_name=member.display_name,
        read=lambda: discussions.read_member_thread(request.user, event, member),
        post=lambda body: discussions.post_member_comment(request.user, event, member, body),
        thread_url=reverse("member_discussion", args=[event.pk, member.pk]),
    )


@require_POST
def comment_delete(request, comment_pk):
    # Authors only; every miss (missing, foreign, giftee) is the same bare 404 (D-03, T-05-07).
    if not discussions.delete_comment(request.user, comment_pk):
        raise Http404()
    messages.success(request, gettext("Comment deleted."))
    return _back(request, "home")
