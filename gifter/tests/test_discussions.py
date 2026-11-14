"""
Secret discussions about a wish and about a person (Phase 5, plan 05-01, DISC-01, DISC-02).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_discussions
"""

import importlib

from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch, reverse
from django.db import IntegrityError, migrations, transaction
from datetime import timedelta

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from gifter.discussions import NO_DISCUSSION, ThreadSummary, summaries_for
from gifter.models import Comment, Event, Thread, ThreadVisit, Wish
from gifter.tests.test_events import join, make_event, make_user
from gifter.tests.test_wishes import make_wish


class DiscussionScenario:
    """Anna owns "Lego set", shared into E1 (Anna, Bob, Carol) and E2 (Anna, Dave)."""

    def build(self):
        self.anna = make_user("anna", first_name="Anna")
        self.bob = make_user("bob", first_name="Bob")
        self.carol = make_user("carol", first_name="Carol")
        self.dave = make_user("dave", first_name="Dave")
        self.e1 = make_event(self.anna, name="Family")
        join(self.e1, self.bob)
        join(self.e1, self.carol)
        self.e2 = make_event(self.anna, name="Friends")
        join(self.e2, self.dave)
        self.wish = make_wish(self.anna, name="Lego set", events=[self.e1, self.e2])

    def thread_url(self, event=None, wish=None, wish_pk=None):
        event = event or self.e1
        wish_pk = wish_pk or (wish or self.wish).pk
        return f"/events/{event.pk}/wishes/{wish_pk}/discussion/"

    def member_url(self, member, event=None, user_pk=None):
        event = event or self.e1
        return f"/events/{event.pk}/members/{user_pk or member.pk}/discussion/"

    def event_url(self, event=None):
        return f"/events/{(event or self.e1).pk}/"


class DiscussionTracerTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()

    def test_bob_opens_an_empty_thread(self):
        self.client.force_login(self.bob)
        response = self.client.get(self.thread_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gifter/discussion.html")
        self.assertContains(response, "Lego set")
        self.assertContains(response, "Anna will never see this discussion.")
        self.assertContains(response, "No comments yet. Start the discussion.")

    def test_bob_posts_and_carol_reads(self):
        self.client.force_login(self.bob)
        response = self.client.post(self.thread_url(), {"body": "Hello zork"})
        comment = Comment.objects.get()
        self.assertRedirects(
            response,
            f"{self.thread_url()}#comment-{comment.pk}",
            fetch_redirect_response=False,
        )
        thread = Thread.objects.get()
        self.assertEqual(thread.event, self.e1)
        self.assertEqual(thread.wish, self.wish)
        self.assertEqual(thread.giftee, self.anna)
        self.assertEqual(comment.author, self.bob)
        self.client.force_login(self.carol)
        page = self.client.get(self.thread_url())
        self.assertContains(page, "Hello zork")
        self.assertContains(page, "Bob")

    def test_owner_gets_the_same_404_as_a_missing_wish_and_nothing_is_written(self):
        self.client.force_login(self.anna)
        baseline = self.client.post(self.thread_url(wish_pk=999999), {"body": "x"})
        self.assertEqual(baseline.status_code, 404)
        post = self.client.post(self.thread_url(), {"body": "Hello zork"})
        get = self.client.get(self.thread_url())
        self.assertEqual(post.status_code, 404)
        self.assertEqual(get.status_code, 404)
        self.assertEqual(post.content, baseline.content)
        self.assertEqual(get.content, baseline.content)
        self.assertEqual(Thread.objects.count(), 0)
        self.assertEqual(Comment.objects.count(), 0)

    def test_event_page_links_to_the_thread_for_bob_but_not_for_the_owner(self):
        self.client.force_login(self.bob)
        self.assertContains(self.client.get(self.event_url()), self.thread_url())
        self.client.force_login(self.anna)
        self.assertNotContains(self.client.get(self.event_url()), self.thread_url())

    def test_a_duplicate_thread_for_the_same_event_and_wish_is_rejected(self):
        Thread.objects.create(event=self.e1, wish=self.wish, giftee=self.anna)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Thread.objects.create(event=self.e1, wish=self.wish, giftee=self.anna)

    def test_a_duplicate_member_thread_is_rejected(self):
        Thread.objects.create(event=self.e1, giftee=self.carol)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Thread.objects.create(event=self.e1, giftee=self.carol)

    def test_the_tables_have_no_accessor_from_wish_event_or_user(self):
        hidden = {Thread, Comment, ThreadVisit}
        for model in (Wish, Event, get_user_model()):
            related = {f.related_model for f in model._meta.get_fields() if f.is_relation}
            self.assertFalse(related & hidden, model)

    def test_the_migration_only_creates_tables_and_their_constraints(self):
        module = importlib.import_module("gifter.migrations.0005_discussions")
        operations = module.Migration.operations
        creates = [op for op in operations if isinstance(op, migrations.CreateModel)]
        self.assertEqual(len(creates), 3)
        for op in operations:
            self.assertIsInstance(op, migrations.CreateModel | migrations.AddConstraint)
            if isinstance(op, migrations.AddConstraint):
                self.assertIn(op.model_name, {"thread", "threadvisit"})

    def test_str_never_shows_the_body_or_the_wish_name(self):
        thread = Thread.objects.create(event=self.e1, wish=self.wish, giftee=self.anna)
        comment = Comment.objects.create(thread=thread, author=self.bob, body="secret zork")
        visit = ThreadVisit.objects.create(thread=thread, user=self.bob)
        for obj in (thread, comment, visit):
            self.assertNotIn("zork", str(obj))
            self.assertNotIn("Lego", str(obj))


class MemberThreadTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()

    def test_bob_posts_about_carol_and_everyone_but_carol_can_read_and_post(self):
        self.client.force_login(self.bob)
        response = self.client.post(self.member_url(self.carol), {"body": "Surprise zork"})
        self.assertEqual(response.status_code, 302)
        thread = Thread.objects.get()
        self.assertIsNone(thread.wish)
        self.assertEqual(thread.giftee, self.carol)
        self.assertEqual(thread.event, self.e1)
        # Anna is not the person, so she can read and post.
        self.client.force_login(self.anna)
        page = self.client.get(self.member_url(self.carol))
        self.assertContains(page, "Surprise zork")
        self.assertContains(page, "Bob")
        self.assertContains(page, "Carol will never see this discussion.")
        self.client.post(self.member_url(self.carol), {"body": "Agreed"})
        self.assertEqual(Comment.objects.count(), 2)

    def test_the_person_gets_the_missing_user_404_and_nothing_is_written(self):
        self.client.force_login(self.carol)
        baseline = self.client.get(self.member_url(self.carol, user_pk=999999))
        self.assertEqual(baseline.status_code, 404)
        for method in (self.client.get, self.client.post):
            response = method(self.member_url(self.carol), {"body": "zork"} if method == self.client.post else {})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.content, baseline.content)
        self.assertEqual(Thread.objects.count(), 0)
        self.assertEqual(Comment.objects.count(), 0)

    def test_a_person_with_no_wishes_still_has_a_thread(self):
        self.assertEqual(Wish.objects.filter(owner=self.carol).count(), 0)
        self.client.force_login(self.bob)
        page = self.client.get(self.member_url(self.carol))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Discussion: Carol")


class GateMatrixTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()
        self.client.force_login(self.bob)
        self.baseline = self.client.get(self.thread_url(wish_pk=999999)).content

    def assert_uniform(self, user, url):
        self.client.force_login(user)
        for response in (self.client.get(url), self.client.post(url, {"body": "zork"})):
            self.assertEqual(response.status_code, 404, url)
            self.assertEqual(response.content, self.baseline, url)
        self.assertEqual(Thread.objects.count(), 0, url)
        self.assertEqual(Comment.objects.count(), 0, url)

    def test_wish_route_gates(self):
        only_e2 = make_wish(self.anna, name="Only friends", events=[self.e2])
        withdrawn = make_wish(
            self.anna, name="Gone", events=[self.e1], status=Wish.Status.WITHDRAWN
        )
        received = make_wish(
            self.anna, name="Got it", events=[self.e1], status=Wish.Status.RECEIVED
        )
        orphan_owner = make_user("erin", first_name="Erin")
        orphan = make_wish(orphan_owner, name="Orphan", events=[self.e1])
        join(self.e1, orphan_owner)
        orphan_owner.memberships.filter(event=self.e1).delete()
        self.assert_uniform(self.dave, self.thread_url())
        self.assert_uniform(self.bob, f"/events/999999/wishes/{self.wish.pk}/discussion/")
        self.assert_uniform(self.bob, self.thread_url(wish_pk=999999))
        self.assert_uniform(self.bob, self.thread_url(wish=only_e2))
        self.assert_uniform(self.bob, self.thread_url(wish=withdrawn))
        self.assert_uniform(self.bob, self.thread_url(wish=received))
        self.assert_uniform(self.bob, self.thread_url(wish=orphan))
        self.assert_uniform(self.anna, self.thread_url())

    def test_member_route_gates(self):
        outsider = make_user("erin", first_name="Erin")
        self.assert_uniform(self.dave, self.member_url(self.carol))
        self.assert_uniform(self.bob, f"/events/999999/members/{self.carol.pk}/discussion/")
        self.assert_uniform(self.bob, self.member_url(self.carol, user_pk=999999))
        self.assert_uniform(self.bob, self.member_url(outsider))
        self.assert_uniform(self.bob, self.member_url(self.dave))
        self.assert_uniform(self.bob, self.member_url(self.bob))
        self.assert_uniform(self.carol, self.member_url(self.carol))


class OneThreadPerEventTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()

    def test_the_same_wish_has_separate_threads_in_two_events(self):
        self.client.force_login(self.bob)
        self.client.post(self.thread_url(), {"body": "From E1"})
        self.client.force_login(self.carol)
        self.assertEqual(self.client.get(self.thread_url(self.e2)).status_code, 404)
        self.client.force_login(self.dave)
        page = self.client.get(self.thread_url(self.e2))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "From E1")
        self.client.post(self.thread_url(self.e2), {"body": "From E2"})
        self.assertEqual(Thread.objects.filter(wish=self.wish).count(), 2)
        self.client.force_login(self.carol)
        e1_page = self.client.get(self.thread_url())
        self.assertContains(e1_page, "From E1")
        self.assertNotContains(e1_page, "From E2")

    def test_reading_never_creates_a_thread(self):
        self.client.force_login(self.bob)
        self.client.get(self.thread_url())
        self.client.get(self.member_url(self.carol))
        self.assertEqual(Thread.objects.count(), 0)


class EventPageLinkTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()
        self.carol_wish = make_wish(self.carol, name="Scarf", events=[self.e1])

    def test_links_for_others_never_for_oneself(self):
        self.client.force_login(self.bob)
        page = self.client.get(self.event_url())
        self.assertContains(page, self.member_url(self.carol))
        self.assertContains(page, self.member_url(self.anna))
        self.assertNotContains(page, self.member_url(self.bob))
        self.assertContains(page, self.thread_url(wish=self.carol_wish))

    def test_the_owner_sees_nothing_about_her_own_wish_or_herself(self):
        self.client.force_login(self.anna)
        page = self.client.get(self.event_url())
        self.assertNotContains(page, self.thread_url())
        self.assertNotContains(page, self.member_url(self.anna))
        self.assertContains(page, self.member_url(self.bob))


class ValidationTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()
        self.client.force_login(self.bob)
        self.client.post(self.thread_url(), {"body": "Earlier zork"})

    def assert_rejected(self, body):
        before = Comment.objects.count()
        response = self.client.post(self.thread_url(), {"body": body})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid-feedback")
        self.assertContains(response, "Earlier zork")
        self.assertEqual(Comment.objects.count(), before)
        self.assertEqual(Thread.objects.count(), 1)

    def test_empty_whitespace_and_too_long_bodies_are_rejected(self):
        self.assert_rejected("")
        self.assert_rejected("   \n  ")
        self.assert_rejected("x" * 1001)

    def test_rejected_on_a_fresh_thread_creates_no_thread(self):
        before = Thread.objects.count()
        response = self.client.post(self.member_url(self.carol), {"body": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Thread.objects.count(), before)
        self.assertEqual(Comment.objects.count(), 1)

    def test_a_1000_character_body_is_accepted(self):
        response = self.client.post(self.thread_url(), {"body": "ž" * 1000})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(Comment.objects.latest("pk").body), 1000)

    def test_windows_line_endings_become_newlines_and_edges_are_stripped(self):
        self.client.post(self.thread_url(), {"body": "  one\r\ntwo\rthree  "})
        self.assertEqual(Comment.objects.latest("pk").body, "one\ntwo\nthree")


class OutputTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()
        self.client.force_login(self.bob)

    def test_html_is_escaped_and_line_breaks_render(self):
        self.client.post(self.thread_url(), {"body": "<script>alert(1)</script>\nsecond"})
        page = self.client.get(self.thread_url())
        self.assertContains(page, "&lt;script&gt;")
        self.assertNotContains(page, "<script>alert(1)")
        self.assertContains(page, "&lt;/script&gt;<br>second")

    def test_comments_are_oldest_first_with_author_names(self):
        thread = Thread.objects.create(event=self.e1, wish=self.wish, giftee=self.anna)
        Comment.objects.create(thread=thread, author=self.carol, body="first zork")
        Comment.objects.create(thread=thread, author=self.bob, body="second zork")
        content = self.client.get(self.thread_url()).content.decode()
        self.assertLess(content.index("first zork"), content.index("second zork"))
        self.assertIn("Carol", content)
        self.assertIn("Bob", content)


class MethodAndLoginTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()

    def urls(self):
        return [self.thread_url(), self.member_url(self.carol)]

    def test_put_and_delete_are_not_allowed(self):
        self.client.force_login(self.bob)
        for url in self.urls():
            self.assertEqual(self.client.put(url).status_code, 405)
            self.assertEqual(self.client.delete(url).status_code, 405)

    def test_signed_out_requests_go_to_the_landing_page_with_next(self):
        for url in self.urls():
            for response in (self.client.get(url), self.client.post(url, {"body": "x"})):
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], f"/?next={url}")
        self.assertEqual(Thread.objects.count(), 0)


class CzechTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()
        self.client.force_login(self.bob)

    def test_thread_page_renders_czech_from_the_catalogue(self):
        from gifter.tests.test_i18n import czech

        page = self.client.get(self.thread_url(), headers={"accept-language": "cs"})
        for msgid in (
            "Discussion",
            "Back to the event",
            "No comments yet. Start the discussion.",
            "Your comment",
            "Post comment",
        ):
            self.assertNotEqual(czech(msgid), msgid)
            self.assertContains(page, czech(msgid))
        self.assertContains(page, czech("%(name)s will never see this discussion.") % {"name": "Anna"})
        self.assertNotContains(page, "Post comment")
        self.assertNotContains(page, "will never see this discussion")

    def test_event_page_and_member_heading_are_czech(self):
        from gifter.tests.test_i18n import czech

        page = self.client.get(self.event_url(), headers={"accept-language": "cs"})
        self.assertContains(page, czech("Discussion about this person"))
        self.assertContains(page, czech("Discuss"))
        member = self.client.get(self.member_url(self.carol), headers={"accept-language": "cs"})
        self.assertContains(member, czech("Discussion: %(name)s") % {"name": "Carol"})


MARKER = "New since your last visit"


def age(comment, hours=2):
    """Move a comment into the past so that the order of events is explicit in a test."""
    Comment.objects.filter(pk=comment.pk).update(created_at=timezone.now() - timedelta(hours=hours))
    comment.refresh_from_db()


class MarkerTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()

    def page(self, user, event=None):
        self.client.force_login(user)
        return self.client.get(self.event_url(event))

    def post(self, user, body, url=None):
        self.client.force_login(user)
        self.client.post(url or self.thread_url(), {"body": body})
        return Comment.objects.order_by("pk").last()

    def test_no_threads_means_plain_label_and_no_marker(self):
        page = self.page(self.carol)
        self.assertContains(page, "Discuss")
        self.assertNotContains(page, MARKER)
        self.assertNotContains(page, "comment)")

    def test_a_comment_by_bob_marks_carols_page_but_not_his_own_or_annas(self):
        self.post(self.bob, "Hello")
        carol = self.page(self.carol)
        self.assertContains(carol, "Discussion (1 comment)")
        self.assertContains(carol, MARKER, count=1)
        bob = self.page(self.bob)
        self.assertContains(bob, "Discussion (1 comment)")
        self.assertNotContains(bob, MARKER)
        anna = self.page(self.anna)
        self.assertNotContains(anna, MARKER)
        self.assertNotContains(anna, "comment)")

    def test_opening_clears_the_marker_and_new_comments_bring_it_back(self):
        first = self.post(self.bob, "Hello")
        age(first)
        self.client.force_login(self.carol)
        thread = self.client.get(self.thread_url())
        self.assertContains(thread, "badge text-bg-info")
        self.assertContains(thread, ">New</span>", count=1)
        self.assertNotContains(self.page(self.carol), MARKER)
        again = self.client.get(self.thread_url())
        self.assertNotContains(again, ">New</span>")
        self.post(self.bob, "Again")
        carol = self.page(self.carol)
        self.assertContains(carol, MARKER, count=1)
        self.assertContains(carol, "Discussion (2 comments)")

    def test_only_unseen_comments_carry_the_new_badge(self):
        first = self.post(self.bob, "Hello")
        age(first, 3)
        self.client.force_login(self.carol)
        self.client.get(self.thread_url())
        ThreadVisit.objects.update(last_seen_at=timezone.now() - timedelta(hours=1))
        self.post(self.bob, "Second")
        self.client.force_login(self.carol)
        page = self.client.get(self.thread_url())
        self.assertContains(page, ">New</span>", count=1)

    def test_own_comments_never_mark_anything_new_for_the_author(self):
        self.post(self.bob, "Mine")
        self.client.force_login(self.bob)
        page = self.client.get(self.thread_url())
        self.assertNotContains(page, ">New</span>")

    def test_member_thread_marker_and_giftee_blindness(self):
        self.post(self.carol, "About Bob", url=self.member_url(self.bob))
        anna = self.page(self.anna)
        self.assertContains(anna, MARKER, count=1)
        self.assertContains(anna, "Discussion about this person (1 comment)")
        bob = self.page(self.bob)
        self.assertNotContains(bob, MARKER)
        self.assertNotContains(bob, "comment)")
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.member_url(self.bob)).status_code, 404)
        self.client.force_login(self.anna)
        self.client.get(self.member_url(self.bob))
        self.assertNotContains(self.page(self.anna), MARKER)


class ThreadVisitRuleTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()
        thread = Thread.objects.create(event=self.e1, wish=self.wish, giftee=self.anna)
        Comment.objects.create(thread=thread, author=self.bob, body="Hello")
        self.thread = thread

    def test_first_open_creates_one_row_and_second_updates_it(self):
        self.client.force_login(self.carol)
        self.client.get(self.thread_url())
        visit = ThreadVisit.objects.get(thread=self.thread, user=self.carol)
        ThreadVisit.objects.filter(pk=visit.pk).update(last_seen_at=timezone.now() - timedelta(days=1))
        before = ThreadVisit.objects.get(pk=visit.pk).last_seen_at
        self.client.get(self.thread_url())
        self.assertEqual(ThreadVisit.objects.filter(thread=self.thread, user=self.carol).count(), 1)
        self.assertGreater(ThreadVisit.objects.get(pk=visit.pk).last_seen_at, before)

    def test_a_gate_failure_creates_no_visit(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.thread_url()).status_code, 404)
        self.assertEqual(self.client.get(self.member_url(self.anna)).status_code, 404)
        stranger = make_user("zed", first_name="Zed")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(self.thread_url()).status_code, 404)
        self.assertEqual(ThreadVisit.objects.count(), 0)

    def test_an_empty_thread_creates_no_thread_and_no_visit(self):
        Thread.objects.all().delete()
        self.client.force_login(self.carol)
        self.client.get(self.thread_url())
        self.client.get(self.member_url(self.bob))
        self.assertEqual(Thread.objects.count(), 0)
        self.assertEqual(ThreadVisit.objects.count(), 0)

    def test_posting_alone_creates_no_visit(self):
        self.client.force_login(self.bob)
        self.client.post(self.thread_url(), {"body": "More"})
        self.assertEqual(ThreadVisit.objects.count(), 0)

    def test_an_invalid_post_does_not_change_another_viewers_marker(self):
        self.client.force_login(self.bob)
        self.client.post(self.thread_url(), {"body": "   "})
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertContains(page, MARKER, count=1)
        self.assertFalse(ThreadVisit.objects.filter(user=self.carol).exists())


class SummariesForTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()

    def make_thread(self, wish=None, event=None, giftee=None):
        event = event or self.e1
        if wish is not None:
            return Thread.objects.create(event=event, wish=wish, giftee=wish.owner)
        return Thread.objects.create(event=event, giftee=giftee)

    def test_a_thread_about_the_viewer_is_absent(self):
        thread = self.make_thread(wish=self.wish)
        Comment.objects.create(thread=thread, author=self.bob, body="x")
        about_anna = self.make_thread(giftee=self.anna)
        Comment.objects.create(thread=about_anna, author=self.bob, body="x")
        mine = summaries_for(self.anna, self.e1)
        self.assertEqual(mine.wishes, {})
        self.assertEqual(mine.members, {})
        theirs = summaries_for(self.carol, self.e1)
        self.assertIn(self.wish.pk, theirs.wishes)
        self.assertIn(self.anna.pk, theirs.members)

    def test_another_event_is_absent(self):
        thread = self.make_thread(wish=self.wish, event=self.e2)
        Comment.objects.create(thread=thread, author=self.dave, body="x")
        result = summaries_for(self.bob, self.e1)
        self.assertEqual((result.wishes, result.members), ({}, {}))

    def test_counts_and_new_for_author_reader_and_visitor(self):
        thread = self.make_thread(wish=self.wish)
        old = Comment.objects.create(thread=thread, author=self.bob, body="a")
        Comment.objects.create(thread=thread, author=self.carol, body="b")
        Comment.objects.create(thread=thread, author=self.bob, body="c")
        age(old, 5)
        self.assertEqual(
            summaries_for(self.bob, self.e1).wishes[self.wish.pk], ThreadSummary(count=3, new=1)
        )
        self.assertEqual(
            summaries_for(self.carol, self.e1).wishes[self.wish.pk], ThreadSummary(count=3, new=2)
        )
        ThreadVisit.objects.create(
            thread=thread, user=self.carol, last_seen_at=timezone.now() - timedelta(hours=1)
        )
        self.assertEqual(
            summaries_for(self.carol, self.e1).wishes[self.wish.pk], ThreadSummary(count=3, new=1)
        )
        ThreadVisit.objects.filter(user=self.carol).update(
            last_seen_at=timezone.now() + timedelta(hours=1)
        )
        self.assertEqual(
            summaries_for(self.carol, self.e1).wishes[self.wish.pk], ThreadSummary(count=3, new=0)
        )

    def test_member_threads_are_keyed_by_person(self):
        thread = self.make_thread(giftee=self.bob)
        Comment.objects.create(thread=thread, author=self.carol, body="x")
        result = summaries_for(self.carol, self.e1)
        self.assertEqual(result.members[self.bob.pk], ThreadSummary(count=1, new=0))
        self.assertEqual(result.members.get(self.carol.pk, NO_DISCUSSION), NO_DISCUSSION)

    def queries(self, viewer):
        with CaptureQueriesContext(connection) as ctx:
            summaries_for(viewer, self.e1)
        return ctx

    def test_query_budget_and_no_body_column(self):
        with CaptureQueriesContext(connection) as none:
            summaries_for(self.carol, self.e1)
        self.assertEqual(len(none), 1)
        thread = self.make_thread(wish=self.wish)
        Comment.objects.create(thread=thread, author=self.bob, body="x")
        self.assertLessEqual(len(self.queries(self.carol)), 3)
        for i in range(5):
            wish = make_wish(self.bob, name=f"W{i}", events=[self.e1])
            t = self.make_thread(wish=wish)
            Comment.objects.create(thread=t, author=self.anna, body="y")
        ctx = self.queries(self.carol)
        self.assertLessEqual(len(ctx), 3)
        for q in ctx.captured_queries:
            self.assertNotIn('"body"', q["sql"])


class CommentDeleteTests(DiscussionScenario, TestCase):
    def setUp(self):
        self.build()
        self.thread = Thread.objects.create(event=self.e1, wish=self.wish, giftee=self.anna)
        self.bobs = Comment.objects.create(thread=self.thread, author=self.bob, body="Bob says")
        self.carols = Comment.objects.create(thread=self.thread, author=self.carol, body="Carol says")

    def delete_url(self, comment):
        return reverse("comment_delete", args=[comment.pk])

    def test_the_author_deletes_and_returns_to_the_thread(self):
        self.client.force_login(self.bob)
        response = self.client.post(self.delete_url(self.bobs), {"next": self.thread_url()})
        self.assertRedirects(response, self.thread_url(), fetch_redirect_response=False)
        self.assertFalse(Comment.objects.filter(pk=self.bobs.pk).exists())
        self.assertTrue(Thread.objects.filter(pk=self.thread.pk).exists())
        self.assertTrue(Comment.objects.filter(pk=self.carols.pk).exists())
        page = self.client.get(self.thread_url())
        self.assertContains(page, "Comment deleted.")
        self.assertNotContains(page, "Bob says")

    def test_an_emptied_thread_shows_no_count_and_no_marker(self):
        Comment.objects.filter(pk=self.carols.pk).delete()
        self.client.force_login(self.carol)
        self.assertContains(self.client.get(self.event_url()), MARKER)
        self.client.force_login(self.bob)
        self.client.post(self.delete_url(self.bobs), {"next": self.thread_url()})
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertNotContains(page, MARKER)
        self.assertNotContains(page, "comment)")

    def test_everyone_else_gets_the_missing_comment_404_and_nothing_is_deleted(self):
        self.client.force_login(self.carol)
        baseline = self.client.post(reverse("comment_delete", args=[999999]))
        self.assertEqual(baseline.status_code, 404)
        stranger = make_user("zed", first_name="Zed")
        for user in (self.carol, self.anna, stranger):
            self.client.force_login(user)
            response = self.client.post(self.delete_url(self.bobs))
            self.assertEqual(response.status_code, 404, user)
            self.assertEqual(response.content, baseline.content, user)
        self.assertTrue(Comment.objects.filter(pk=self.bobs.pk).exists())

    def test_get_is_not_allowed_and_signed_out_goes_to_sign_in(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.delete_url(self.bobs)).status_code, 405)
        self.client.logout()
        response = self.client.post(self.delete_url(self.bobs))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(pk=self.bobs.pk).exists())

    def test_an_external_next_goes_to_the_events_list(self):
        self.client.force_login(self.bob)
        response = self.client.post(self.delete_url(self.bobs), {"next": "https://evil.example/x"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_nothing_can_edit_a_comment(self):
        for name in ("comment_edit", "comment_update"):
            with self.assertRaises(NoReverseMatch):
                reverse(name)
        names = {f.name for f in Comment._meta.get_fields()}
        self.assertFalse({"updated_at", "edited_at"} & names)
        self.client.force_login(self.carol)
        self.client.post(self.delete_url(self.bobs), {"body": "Changed"})
        self.bobs.refresh_from_db()
        self.assertEqual(self.bobs.body, "Bob says")

    def test_a_delete_form_appears_only_on_the_viewers_own_comments(self):
        for user, own, other in (
            (self.bob, self.bobs, self.carols),
            (self.carol, self.carols, self.bobs),
        ):
            self.client.force_login(user)
            page = self.client.get(self.thread_url())
            self.assertContains(page, self.delete_url(own))
            self.assertNotContains(page, self.delete_url(other))
