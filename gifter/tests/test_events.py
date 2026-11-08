"""
Events, memberships and invite links (Phase 2, plan 02-01, EVNT-01..EVNT-05).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_events
"""

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from gifter.models import Event, Membership

User = get_user_model()


def make_user(username, first_name="", last_name="", email=""):
    return User.objects.create(
        username=username, first_name=first_name, last_name=last_name, email=email
    )


def make_event(creator, name="Christmas", date=None, description=""):
    event = Event.objects.create(name=name, date=date, description=description, created_by=creator)
    Membership.objects.create(event=event, user=creator)
    return event


def join(event, user, joined_at=None):
    membership = Membership.objects.create(event=event, user=user)
    if joined_at is not None:
        Membership.objects.filter(pk=membership.pk).update(joined_at=joined_at)
    return membership


class DisplayNameTests(TestCase):
    def test_first_name_wins(self):
        user = make_user("jan.novak", first_name="Jan", last_name="Novak")
        self.assertEqual(user.display_name, "Jan")

    def test_last_name_only(self):
        user = make_user("jan.novak", last_name="Novak")
        self.assertEqual(user.display_name, "Novak")

    def test_neither_name_is_never_the_username(self):
        user = make_user("jan.novak", email="jan.novak@example.com")
        self.assertEqual(user.display_name, "Unnamed member")
        self.assertNotIn("jan.novak", user.display_name)


class EventCreateTests(TestCase):
    def setUp(self):
        self.user = make_user("anna", first_name="Anna")
        self.client.force_login(self.user)

    def post(self, **data):
        payload = {"name": "Christmas", "date": "", "description": ""}
        payload.update(data)
        return self.client.post("/events/new/", payload)

    def test_create_round_trip(self):
        response = self.post(name="Family Christmas", date="2026-12-24", description="At home")
        event = Event.objects.get()
        self.assertRedirects(response, f"/events/{event.pk}/")
        self.assertEqual(event.created_by, self.user)
        self.assertEqual(event.date, datetime.date(2026, 12, 24))
        self.assertEqual(event.description, "At home")
        self.assertEqual(Membership.objects.filter(event=event, user=self.user).count(), 1)
        self.assertContains(self.client.get("/events/"), "Family Christmas")
        page = self.client.get(f"/events/{event.pk}/")
        self.assertContains(page, "Family Christmas")
        self.assertContains(page, "Anna")

    def test_get_shows_empty_form(self):
        response = self.client.get("/events/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')

    def test_whitespace_only_name_rejected(self):
        response = self.post(name="   ")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertEqual(Event.objects.count(), 0)

    def test_blank_name_rejected(self):
        self.assertEqual(self.post(name="").status_code, 200)
        self.assertEqual(Event.objects.count(), 0)

    def test_empty_date_and_description(self):
        self.post()
        event = Event.objects.get()
        self.assertIsNone(event.date)
        self.assertEqual(event.description, "")

    def test_name_limit_counts_code_points(self):
        self.assertEqual(self.post(name="ž" * 200).status_code, 302)
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(self.post(name="ž" * 201).status_code, 200)
        self.assertEqual(Event.objects.count(), 1)

    def test_name_is_stripped(self):
        self.post(name="  Christmas  ")
        self.assertEqual(Event.objects.get().name, "Christmas")

    def test_czech_text_unchanged(self):
        self.post(name="Vánoce u babičky", description="Příjemné svátky")
        event = Event.objects.get()
        self.assertEqual(event.name, "Vánoce u babičky")
        page = self.client.get(f"/events/{event.pk}/")
        self.assertContains(page, "Vánoce u babičky")
        self.assertContains(page, "Příjemné svátky")

    def test_post_redirect_get_and_distinct_tokens(self):
        first = self.post(name="Same")
        second = self.post(name="Same")
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertNotEqual(first["Location"], second["Location"])
        tokens = list(Event.objects.values_list("invite_token", flat=True))
        self.assertEqual(len(set(tokens)), 2)
        for token in tokens:
            self.assertGreaterEqual(len(token), 22)

    def test_event_and_membership_are_atomic(self):
        with mock.patch(
            "gifter.views.Membership.objects.create", side_effect=IntegrityError("boom")
        ):
            with self.assertRaises(IntegrityError):
                self.post(name="Doomed")
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(Membership.objects.count(), 0)


class MyEventsTests(TestCase):
    def setUp(self):
        self.user = make_user("anna", first_name="Anna")
        self.client.force_login(self.user)

    def test_ordering_date_then_name_then_pk(self):
        d1, d2 = datetime.date(2026, 12, 24), datetime.date(2027, 1, 5)
        late = make_event(self.user, "Late", d2)
        undated = make_event(self.user, "Aaa undated")
        early_b = make_event(self.user, "B early", d1)
        early_a = make_event(self.user, "A early", d1)
        twin1 = make_event(self.user, "Twin", d2)
        twin2 = make_event(self.user, "Twin", d2)
        outsider = make_user("bob", first_name="Bob")
        make_event(outsider, "Secret of Bob", d1)
        response = self.client.get("/events/")
        self.assertEqual(
            [e.pk for e in response.context["events"]],
            [early_a.pk, early_b.pk, late.pk, twin1.pk, twin2.pk, undated.pk],
        )
        self.assertEqual(twin1.pk < twin2.pk, True)
        self.assertNotContains(response, "Secret of Bob")

    def test_identical_name_and_date_both_listed(self):
        day = datetime.date(2026, 12, 24)
        make_event(self.user, "Twin", day)
        make_event(self.user, "Twin", day)
        self.assertContains(self.client.get("/events/"), "Twin", count=2)

    def test_empty_state(self):
        response = self.client.get("/events/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not in any events yet")
        self.assertContains(response, 'href="/events/new/"')

    def test_navbar(self):
        response = self.client.get("/events/")
        self.assertContains(response, 'href="/events/"')
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, "navbar-toggler")
        self.assertContains(response, "My events")
        self.assertNotContains(response, "Hi Anna")


class EventDetailTests(TestCase):
    def setUp(self):
        self.anna = make_user("anna", first_name="Anna", email="anna@example.com")
        self.client.force_login(self.anna)
        self.event = make_event(self.anna, "Secret party")

    def test_non_member_and_missing_id_get_identical_404(self):
        outsider = make_user("eve", first_name="Eve")
        self.client.force_login(outsider)
        real = self.client.get(f"/events/{self.event.pk}/")
        missing = self.client.get("/events/999999/")
        self.assertEqual(real.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(real.content, missing.content)
        self.assertNotContains(real, "Secret party", status_code=404)

    def test_anonymous_redirects_to_landing(self):
        self.client.logout()
        response = self.client.get(f"/events/{self.event.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/?next=/events/{self.event.pk}/")

    def test_members_in_join_order_creator_first(self):
        base = timezone.now()
        late = make_user("late", first_name="Late")
        early = make_user("early", first_name="Early")
        join(self.event, late, base + datetime.timedelta(hours=2))
        join(self.event, early, base + datetime.timedelta(hours=1))
        response = self.client.get(f"/events/{self.event.pk}/")
        self.assertEqual(
            [m.user.pk for m in response.context["memberships"]],
            [self.anna.pk, early.pk, late.pk],
        )

    def test_same_display_name_listed_twice(self):
        join(self.event, make_user("a1", first_name="Pavel"))
        join(self.event, make_user("a2", first_name="Pavel"))
        self.assertContains(self.client.get(f"/events/{self.event.pk}/"), "<li>Pavel</li>", count=2)

    def test_sole_member_sees_invite_prompt(self):
        response = self.client.get(f"/events/{self.event.pk}/")
        self.assertContains(response, "<li>Anna</li>", count=1)
        self.assertContains(response, "only member so far")

    def test_member_email_never_shown(self):
        other = make_user("pavel", first_name="Pavel", email="pavel.secret@example.com")
        join(self.event, other)
        response = self.client.get(f"/events/{self.event.pk}/")
        self.assertNotContains(response, "pavel.secret@example.com")
        self.assertNotContains(response, "anna@example.com")

    def test_nameless_member_shown_as_unnamed_never_username(self):
        nameless = make_user("jan.novak", email="jan.novak@example.com")
        join(self.event, nameless)
        viewer = make_user("viewer", first_name="Viewer")
        join(self.event, viewer)
        self.client.force_login(viewer)
        response = self.client.get(f"/events/{self.event.pk}/")
        self.assertContains(response, "Unnamed member")
        self.assertNotContains(response, "jan.novak")
