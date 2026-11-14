"""
Secret discussions about a wish and about a person (Phase 5, plan 05-01, DISC-01, DISC-02).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_discussions
"""

import importlib

from django.contrib.auth import get_user_model
from django.db import IntegrityError, migrations, transaction
from django.test import TestCase

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
