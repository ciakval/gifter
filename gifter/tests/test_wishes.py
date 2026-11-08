"""
Wishlists, sharing into events and browsing (Phase 2, plan 02-02, WISH-01..04, CLAM-01).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_wishes
"""

import datetime

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from gifter.models import Wish
from gifter.tests.test_events import join, make_event, make_user


def make_wish(owner, name="Lego set", events=(), **fields):
    wish = Wish.objects.create(owner=owner, name=name, **fields)
    if events:
        wish.events.add(*events)
    return wish


class TracerTests(TestCase):
    def setUp(self):
        self.anna = make_user("anna", first_name="Anna")
        self.bob = make_user("bob", first_name="Bob")
        self.event = make_event(self.anna, name="Family Christmas")
        join(self.event, self.bob)

    def add(self, **data):
        payload = {"name": "Lego set", "description": "", "priority": "2"}
        payload.update(data)
        return self.client.post("/wishes/new/", payload)

    def test_tracer_anna_adds_wish_and_bob_sees_it_in_her_card(self):
        self.client.force_login(self.anna)
        response = self.add(events=[self.event.pk])
        self.assertRedirects(response, "/wishes/")
        wish = Wish.objects.get()
        self.assertEqual(wish.owner, self.anna)
        self.assertContains(self.client.get("/wishes/"), "Lego set")
        own_page = self.client.get(f"/events/{self.event.pk}/")
        self.assertNotContains(own_page, '<div class="card-header fw-semibold">Anna</div>')

        self.client.force_login(self.bob)
        page = self.client.get(f"/events/{self.event.pk}/")
        card = page.content.decode().split('<div class="card-header fw-semibold">Anna</div>')[1]
        self.assertIn("Lego set", card)

    def test_unshared_wish_is_invisible_to_other_members(self):
        self.client.force_login(self.anna)
        self.add(name="Secret telescope")
        self.assertEqual(Wish.objects.get().events.count(), 0)
        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(f"/events/{self.event.pk}/"), "Secret telescope")

    def test_wish_shared_elsewhere_is_not_in_this_event(self):
        other = make_event(self.anna, name="Wedding")
        make_wish(self.anna, "Wedding gift", events=[other])
        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(f"/events/{self.event.pk}/"), "Wedding gift")

    def test_member_without_wishes_still_gets_a_card(self):
        self.client.force_login(self.bob)
        page = self.client.get(f"/events/{self.event.pk}/")
        self.assertContains(page, "No wishes shared here yet.")

    def test_forged_event_id_is_rejected(self):
        carol = make_user("carol", first_name="Carol")
        foreign = make_event(carol, name="Carol party")
        self.client.force_login(self.anna)
        response = self.add(events=[foreign.pk])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["events"])
        self.assertEqual(Wish.objects.count(), 0)
        self.assertEqual(Wish.events.through.objects.count(), 0)

    def test_user_without_events_can_add_a_wish(self):
        loner = make_user("loner", first_name="Loner")
        self.client.force_login(loner)
        form_page = self.client.get("/wishes/new/")
        self.assertContains(form_page, "not in any events yet")
        response = self.add()
        self.assertRedirects(response, "/wishes/")
        self.assertEqual(Wish.objects.get().owner, loner)

    def test_event_checkboxes_follow_my_events_order(self):
        undated = make_event(self.anna, name="Zeta undated")
        late = make_event(self.anna, name="Late", date=datetime.date(2026, 12, 30))
        early = make_event(self.anna, name="Early", date=datetime.date(2026, 12, 1))
        self.client.force_login(self.anna)
        form = self.client.get("/wishes/new/").context["form"]
        pks = [choice.data["value"].value for choice in form["events"]]
        self.assertEqual(
            pks, [early.pk, late.pk, self.event.pk, undated.pk]
        )

    def test_same_name_events_show_dates_in_labels(self):
        make_event(self.anna, name="Party", date=datetime.date(2026, 12, 1))
        make_event(self.anna, name="Party", date=datetime.date(2026, 12, 2))
        self.client.force_login(self.anna)
        form = self.client.get("/wishes/new/").context["form"]
        labels = [str(choice.choice_label) for choice in form["events"] if "Party" in str(choice.choice_label)]
        self.assertEqual(len(labels), 2)
        self.assertEqual(len(set(labels)), 2)
        for label in labels:
            self.assertIn("(", label)

    def test_new_wish_form_preselects_all_events(self):
        other = make_event(self.anna, name="Wedding")
        self.client.force_login(self.anna)
        form = self.client.get("/wishes/new/").context["form"]
        self.assertCountEqual(form.initial["events"], [self.event.pk, other.pk])
        page = self.client.get("/wishes/new/")
        self.assertContains(page, '<option value="2" selected>Normal</option>', html=False)
        html = page.content.decode()
        self.assertEqual(html.count(" checked"), 2)

    def test_non_member_gets_404_with_no_wish_names(self):
        make_wish(self.anna, "Hidden gem", events=[self.event])
        carol = make_user("carol", first_name="Carol")
        self.client.force_login(carol)
        response = self.client.get(f"/events/{self.event.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Hidden gem", status_code=404)

    def test_anonymous_wishlist_redirects_to_landing(self):
        response = self.client.get("/wishes/")
        self.assertRedirects(response, "/?next=/wishes/", fetch_redirect_response=False)

    def test_navbar_has_my_wishlist_link(self):
        self.client.force_login(self.anna)
        self.assertContains(self.client.get("/wishes/"), 'href="/wishes/"')

    def test_wish_has_no_claim_fields(self):
        for field in Wish._meta.get_fields():
            self.assertNotIn("claim", field.name.lower())

    def test_owner_pages_render_no_claim_data(self):
        self.client.force_login(self.anna)
        for url in ("/wishes/", "/wishes/new/"):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode().lower()
                self.assertNotIn("claim", html)


def normalize_links(raw):
    # Imported lazily so the module loads while the function is still being written.
    from gifter.forms import normalize_links as real

    return real(raw)


class NormalizeLinksTests(SimpleTestCase):
    def test_normalizes_trims_dedupes_and_lowercases_scheme_and_host(self):
        raw = "alza.cz/lego-123\n\n  https://EXAMPLE.com/a?b=C \nhttps://example.com/a?b=C"
        self.assertEqual(
            normalize_links(raw), ["https://alza.cz/lego-123", "https://example.com/a?b=C"]
        )

    def test_scripted_and_other_schemes_are_rejected(self):
        for line in (
            "javascript:alert(1)",
            "ftp://example.com/x",
            "data:text/html,hi",
            "mailto:anna@example.com",
        ):
            with self.subTest(line=line):
                with self.assertRaises(ValidationError) as ctx:
                    normalize_links(line)
                self.assertIn(line, " ".join(ctx.exception.messages))

    def test_every_bad_line_is_reported(self):
        with self.assertRaises(ValidationError) as ctx:
            normalize_links("javascript:a\nhttps://ok.example\nftp://b.example")
        self.assertEqual(len(ctx.exception.messages), 2)

    def test_empty_is_empty_list(self):
        self.assertEqual(normalize_links(""), [])
        self.assertEqual(normalize_links("  \n \n"), [])

    def test_host_with_port_is_not_a_scheme(self):
        self.assertEqual(normalize_links("alza.cz:8080/x"), ["https://alza.cz:8080/x"])

    def test_overlong_line_is_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_links("https://example.com/" + "a" * 2000)


class WishCrudTests(TestCase):
    def setUp(self):
        self.anna = make_user("anna", first_name="Anna")
        self.bob = make_user("bob", first_name="Bob")
        self.event = make_event(self.anna, name="Family Christmas")
        self.other_event = make_event(self.anna, name="Wedding")
        join(self.event, self.bob)
        self.client.force_login(self.anna)

    def payload(self, **data):
        payload = {"name": "Lego set", "description": "", "priority": "2", "links": ""}
        payload.update(data)
        return payload

    def test_links_are_stored_and_shown_as_domains_with_safe_rel(self):
        self.client.post(
            "/wishes/new/",
            self.payload(
                links="alza.cz/lego-123\nhttps://www.Example.com/a?b=C", events=[self.event.pk]
            ),
        )
        wish = Wish.objects.get()
        self.assertEqual(wish.links, "https://alza.cz/lego-123\nhttps://www.example.com/a?b=C")
        anchor = (
            'href="https://alza.cz/lego-123" target="_blank" rel="noopener noreferrer nofollow">'
            "alza.cz</a>"
        )
        self.assertContains(self.client.get("/wishes/"), anchor)
        self.client.force_login(self.bob)
        page = self.client.get(f"/events/{self.event.pk}/")
        self.assertContains(page, anchor)
        self.assertContains(
            page,
            'href="https://www.example.com/a?b=C" target="_blank" '
            'rel="noopener noreferrer nofollow">example.com</a>',
        )

    def test_bad_link_rejected_with_message(self):
        response = self.client.post("/wishes/new/", self.payload(links="javascript:alert(1)"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Wish.objects.count(), 0)
        self.assertContains(response, "is not a web address")

    def test_name_only_wish_is_valid_and_blank_name_rejected(self):
        response = self.client.post("/wishes/new/", {"name": "Book", "priority": "2"})
        self.assertRedirects(response, "/wishes/")
        wish = Wish.objects.get()
        self.assertEqual((wish.description, wish.links), ("", ""))
        self.assertEqual(wish.priority, Wish.Priority.NORMAL)
        for name in ("", "   "):
            response = self.client.post("/wishes/new/", self.payload(name=name))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Wish.objects.count(), 1)

    def test_name_length_in_code_points_and_czech_round_trip(self):
        ok = self.client.post("/wishes/new/", self.payload(name="ž" * 200))
        self.assertRedirects(ok, "/wishes/")
        too_long = self.client.post("/wishes/new/", self.payload(name="ž" * 201))
        self.assertEqual(too_long.status_code, 200)
        self.assertEqual(Wish.objects.count(), 1)
        self.client.post("/wishes/new/", self.payload(name="Kniha o houbách"))
        self.assertContains(self.client.get("/wishes/"), "Kniha o houbách")

    def test_edit_form_checks_only_actual_shares(self):
        wish = make_wish(self.anna, events=[self.event])
        html = self.client.get(f"/wishes/{wish.pk}/edit/").content.decode()
        self.assertEqual(html.count(" checked"), 1)
        self.assertIn(f'value="{self.event.pk}" id="id_events_', html.replace('"  ', '" '))

    def test_owner_edit_changes_fields_and_shares(self):
        wish = make_wish(self.anna, events=[self.event])
        response = self.client.post(
            f"/wishes/{wish.pk}/edit/",
            self.payload(
                name="Bigger set",
                priority="1",
                links="example.com/x",
                events=[self.other_event.pk],
            ),
            follow=True,
        )
        self.assertRedirects(response, "/wishes/")
        self.assertContains(response, "Wish saved.")
        wish.refresh_from_db()
        self.assertEqual(wish.name, "Bigger set")
        self.assertEqual(wish.priority, 1)
        self.assertEqual(wish.links, "https://example.com/x")
        self.assertEqual(list(wish.events.all()), [self.other_event])

    def test_edit_never_writes_status(self):
        wish = make_wish(self.anna, events=[self.event])
        self.client.get(f"/wishes/{wish.pk}/edit/")
        # A delete lands between the edit page load and the save.
        Wish.objects.filter(pk=wish.pk).update(status=Wish.Status.WITHDRAWN)
        response = self.client.post(f"/wishes/{wish.pk}/edit/", self.payload(name="Late edit"))
        self.assertEqual(response.status_code, 404)
        wish.refresh_from_db()
        self.assertEqual(wish.status, Wish.Status.WITHDRAWN)
        self.assertEqual(wish.name, "Lego set")

    def test_other_users_cannot_edit_or_delete(self):
        wish = make_wish(self.anna, events=[self.event])
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(f"/wishes/{wish.pk}/edit/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/wishes/{wish.pk}/edit/", self.payload(name="Hacked")).status_code, 404
        )
        self.assertEqual(self.client.get(f"/wishes/{wish.pk}/delete/").status_code, 404)
        self.assertEqual(self.client.post(f"/wishes/{wish.pk}/delete/").status_code, 404)
        wish.refresh_from_db()
        self.assertEqual((wish.name, wish.status), ("Lego set", Wish.Status.ACTIVE))

    def test_delete_confirm_then_soft_delete_idempotently(self):
        wish = make_wish(self.anna, events=[self.event])
        confirm = self.client.get(f"/wishes/{wish.pk}/delete/")
        self.assertContains(confirm, "Delete this wish?")
        self.assertContains(confirm, 'method="post"')
        self.assertNotIn("claim", confirm.content.decode().lower())
        first = self.client.post(f"/wishes/{wish.pk}/delete/", follow=True)
        self.assertRedirects(first, "/wishes/")
        self.assertContains(first, "Wish deleted.")
        wish.refresh_from_db()
        self.assertEqual(wish.status, Wish.Status.WITHDRAWN)
        second = self.client.post(f"/wishes/{wish.pk}/delete/", follow=True)
        self.assertRedirects(second, "/wishes/")
        self.assertContains(second, "Wish deleted.")
        self.assertEqual(Wish.objects.count(), 1)

    def test_deleted_wish_vanishes_everywhere(self):
        wish = make_wish(self.anna, "Vanishing vase", events=[self.event])
        self.client.post(f"/wishes/{wish.pk}/delete/")
        self.assertNotContains(self.client.get("/wishes/"), "Vanishing vase")
        self.assertEqual(self.client.get(f"/wishes/{wish.pk}/edit/").status_code, 404)
        self.assertEqual(self.client.get(f"/wishes/{wish.pk}/delete/").status_code, 404)
        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(f"/events/{self.event.pk}/"), "Vanishing vase")

    def test_members_see_wishes_by_priority_then_newest(self):
        t0 = datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC)
        specs = [
            ("low-new", 3, 4),
            ("high-old", 1, 1),
            ("normal-old", 2, 1),
            ("high-new", 1, 3),
            ("normal-new", 2, 3),
        ]
        for name, priority, day in specs:
            wish = make_wish(self.anna, name, events=[self.event], priority=priority)
            Wish.objects.filter(pk=wish.pk).update(created_at=t0 + datetime.timedelta(days=day))
        self.client.force_login(self.bob)
        html = self.client.get(f"/events/{self.event.pk}/").content.decode()
        positions = [html.index(name) for name, _p, _d in specs]
        by_name = dict(zip((n for n, _p, _d in specs), positions))
        order = sorted(by_name, key=by_name.get)
        self.assertEqual(order, ["high-new", "high-old", "normal-new", "normal-old", "low-new"])
