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
