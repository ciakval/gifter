# Architecture Research

**Domain:** Group gift wishlist with secret claiming / chip-in (Django 5.1 monolith, brownfield)
**Researched:** 2026-10-15
**Confidence:** HIGH on model/secrecy design (standard Django patterns applied to the stated requirements); MEDIUM on django-allauth specifics (not re-verified against current docs this session, so confirm in the auth phase; STACK.md owns that choice)

## Headline Recommendations

1. **Keep one Django app (`gifter`) and `auth.User`.** Split code *inside* the app by responsibility (selectors / services / owner views / participant views), not into many apps. At roughly 8 models and 8 weeks, more apps is overhead.
2. **Claim data is structurally separate from the Wish.** `Wish` has no claim fields. `Claim` (OneToOne to Wish) and `Contribution` live in their own tables, with `related_name="+"` on the Wish side so `wish.claim` is not reachable from a template.
3. **Secrecy is enforced by construction, then verified by canary tests.** The owner's pages never load claim data. Participant pages only show wishes the viewer does not own. A single selector chokepoint asserts "viewer is not the owner" before returning any claim info.
4. **The invite link is a rotatable random token on `Event`.** Opening it shows a confirm page, and joining happens on POST. Do not join on GET, because chat-app link previewers fetch URLs.
5. **Receipt and deletion are status transitions, not row deletes.** `Wish.status` is `ACTIVE`, `RECEIVED` or `WITHDRAWN`. A hard delete would silently destroy a claimer's commitment, and it would make "delete" behave differently depending on whether a claim exists (a side channel).

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  AUTH BOUNDARY  (allauth Google + LoginRequiredMiddleware, 5.1+)      │
│  every view login-protected by default; public views opt out          │
├──────────────────────────────────────────────────────────────────────┤
│                         PRESENTATION (views + templates)             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐   │
│  │ OWNER SPACE  │  │ EVENT SPACE  │  │ PARTICIPANT SPACE         │   │
│  │ /wishes/...  │  │ /events/...  │  │ /events/<e>/wishes/<w>/.. │   │
│  │ my wishes    │  │ create, join │  │ browse, claim, chip in,   │   │
│  │ share, recv  │  │ invite, leave│  │ release, "My gifts"       │   │
│  │ NEVER imports│  │              │  │ ONLY place claims render  │   │
│  │ claims code  │  │              │  │                           │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬────────────────┘   │
│  templates/gifter/owner/  │  templates/gifter/participant/ (separate) │
├─────────┴─────────────────┴─────────────────────┴────────────────────┤
│                         DOMAIN LAYER (gifter/)                        │
│  ┌────────────────────────────┐  ┌──────────────────────────────┐    │
│  │ selectors.py  (READ)       │  │ services.py  (WRITE)         │    │
│  │ visibility rules:          │  │ claim / release / contribute │    │
│  │ owned_by, shared_with,     │  │ join_event / leave_event     │    │
│  │ claim_views_for(viewer,..) │  │ share_wish / mark_received   │    │
│  │ <- secrecy chokepoint      │  │ withdraw_wish (transactions) │    │
│  └─────────────┬──────────────┘  └───────────────┬──────────────┘    │
├────────────────┴─────────────────────────────────┴───────────────────┤
│                              DATA (ORM)                               │
│  User  Event  EventMembership  Wish  WishLink  EventWish              │
│  Claim  Contribution   (DB constraints enforce the invariants)        │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Auth boundary | Google sign-in, session, "next" redirect after login (including the invite flow) | django-allauth + Django 5.1 `LoginRequiredMiddleware`. Views are protected by default; `@login_not_required` marks the few public ones (allauth pages, health check). |
| Owner space | CRUD of the user's own wishes, links, priority, choosing events to share into, mark received/withdraw | CBVs with `LoginRequiredMixin`-style ownership via `Wish.objects.owned_by(request.user)`. It never imports `Claim`, `Contribution` or `claim_views_for`. |
| Event space | Create event, member list, invite link (view and rotate), leave | Plain CBVs. Access via `get_event_for_member(user, pk)`, which raises 404 for non-members. |
| Participant space | Browse others' wishes in an event, wish detail, claim / release / chip in / withdraw chip-in, "My gifts" | Views call selectors for reads and services for writes. This is the only place claim state reaches templates. |
| `selectors.py` | All visibility rules for reads | Functions and QuerySet methods returning only what a given viewer may see. |
| `services.py` | All state transitions with invariants, wrapped in `transaction.atomic` | Plain functions taking `(user, wish)` and raising domain exceptions (`NotVisible`, `AlreadyClaimed`, `NotAllowed`). |
| Models and constraints | Final line of defence for data integrity | `UniqueConstraint`, `OneToOneField`, `CheckConstraint`. |
| i18n layer | EN/CZ strings | `LocaleMiddleware`, `gettext`/`{% trans %}` from the first template, language switcher via `set_language`. |

## Recommended Project Structure

```
src/
├── manage.py
├── web/                         # project: settings (env-driven), root urls, wsgi
│   ├── settings.py              # split dev/prod via env vars; allauth, i18n, middleware
│   └── urls.py                  # admin, allauth (accounts/), include("gifter.urls") at ROOT
└── gifter/                      # the single domain app
    ├── models.py                # Event, EventMembership, Wish, WishLink, EventWish, Claim, Contribution
    ├── querysets.py             # WishQuerySet / EventQuerySet (owned_by, shared_with, member_of)
    ├── selectors.py             # read-side: claim_views_for(), event_wish_cards(), my_gifts()
    ├── services.py              # write-side: claim, release, contribute, join_event, mark_received...
    ├── exceptions.py            # NotVisible, AlreadyClaimed, ...
    ├── forms.py                 # WishForm (explicit fields!), WishLinkFormSet, EventForm
    ├── views/
    │   ├── owner.py             # /wishes/...   (no claim imports)
    │   ├── events.py            # /events/..., /join/<token>/
    │   └── participant.py       # /events/<e>/wishes/<w>/... and /gifts/
    ├── urls.py                  # app_name = "gifter"
    ├── templates/gifter/
    │   ├── base.html            # responsive layout, language switcher
    │   ├── owner/               # templates that must NEVER mention claims
    │   ├── events/
    │   └── participant/         # the only templates that render claim state
    ├── locale/cs/LC_MESSAGES/   # django.po (Czech)
    ├── migrations/
    └── tests/
        ├── test_secrecy.py      # canary tests (highest value file in the repo)
        ├── test_claims.py       # concurrency/invariants
        ├── test_invites.py
        └── test_visibility.py
```

### Structure Rationale

- **One app, internal layers:** the domain is tightly coupled (Wish, Event, Claim all enforce each other's visibility). Splitting into apps would create circular imports for no benefit.
- **selectors / services split:** reads and writes are the two places rules live. Views stay thin, and the secrecy rule has exactly one home.
- **owner/ vs participant/ templates and views:** the core promise is "the giftee never sees claims". The strongest guard is that the code and templates the giftee uses cannot reach claim data. Do not share a wish-card partial that hides claim info with `{% if viewer != wish.owner %}`.
- **Move `gifter.urls` to the root** (`path("", include("gifter.urls"))`, `app_name = "gifter"`) now. Only one URL exists today, so the change is free.

## Data Model

```python
# gifter/models.py  (sketch, not final code)
import secrets
from django.conf import settings
from django.db import models
from django.db.models import Q

User = settings.AUTH_USER_MODEL

def new_invite_token():
    return secrets.token_urlsafe(32)          # ~256 bits; unguessable

class Event(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField(null=True, blank=True)          # display only
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_events")
    invite_token = models.CharField(max_length=64, unique=True, default=new_invite_token)
    invite_enabled = models.BooleanField(default=True)       # owner can switch the link off
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(User, through="EventMembership", related_name="events")

class EventMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner"; MEMBER = "member"
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="uniq_membership")]

class Wish(models.Model):
    class Priority(models.IntegerChoices):
        NICE = 1; WANT = 2; MUST = 3                         # label via gettext_lazy
    class Status(models.TextChoices):
        ACTIVE = "active"; RECEIVED = "received"; WITHDRAWN = "withdrawn"
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishes")  # was `user`
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)               # was required
    priority = models.PositiveSmallIntegerField(choices=Priority, default=Priority.WANT)
    status = models.CharField(max_length=10, choices=Status, default=Status.ACTIVE, db_index=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)        # NEVER touched by claim operations
    events = models.ManyToManyField(Event, through="EventWish", related_name="wishes")
    objects = WishQuerySet.as_manager()

class WishLink(models.Model):                                # 0..n links per wish
    wish = models.ForeignKey(Wish, on_delete=models.CASCADE, related_name="links")
    url = models.URLField(max_length=2000)                   # http/https only
    label = models.CharField(max_length=100, blank=True)

class EventWish(models.Model):                               # "share wish into event"
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    wish = models.ForeignKey(Wish, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "wish"], name="uniq_event_wish")]

class Claim(models.Model):                                   # lives on the WISH, global across events
    wish = models.OneToOneField(Wish, on_delete=models.CASCADE, related_name="+")  # DB-enforced single claimer
    claimer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="claims")
    created_at = models.DateTimeField(auto_now_add=True)

class Contribution(models.Model):                            # chip-in; claimer is NOT a contribution row
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="contributions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contributions")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["claim", "user"], name="uniq_contribution")]
```

### Modelling decisions and why

| Decision | Rationale |
|----------|-----------|
| **Keep `auth.User`** and reference it via `settings.AUTH_USER_MODEL` in all new code | allauth works with it; the display name comes from Google `first_name`/`last_name`. A custom user is only worth it if you need email-as-username, and allauth covers that. Centralise display in one helper `display_name(user)`. |
| **Rename `Wish.user` to `owner`** (`RenameField`) | "user" is ambiguous now that claimer, contributor and member exist. Use `owner` or `giftee` consistently. A rename is trivial pre-launch. |
| **Drop `Wish.claimed_by`; replace `is_active` with `status`** | `claimed_by` cannot model chip-in, and keeping it creates two sources of truth. `is_active` cannot distinguish received from withdrawn. Migration: add `status`, RunPython `is_active -> status`, remove old fields. Any existing rows are dev data. |
| **`Claim` OneToOne to `Wish`** | "Taken" equals "a Claim row exists". The single-claimer rule is a DB constraint, not application logic. `related_name="+"` removes the `wish.claim` accessor from templates. |
| **Claimer separate from `Contribution`** | Matches the domain wording (one responsible person plus helpers). The alternative is a single `Pledge(wish, user, is_lead)` table with a partial unique constraint on `is_lead=True`. It makes hand-over simpler but blurs "taken" semantics. Either works; this doc uses Claim plus Contribution. |
| **`Wish` to `Event` is M2M through `EventWish`** | The claim hangs off the Wish, so the same claim shows in every event the wish is shared into. `EventWish` can grow later (for example per-event notes) without a migration scare. |
| **Priority on Wish, links in `WishLink`** | A separate link table gives an inline formset with per-URL validation. Do not use a comma-separated text field or JSON. `URLField` restricts schemes, which blocks `javascript:` URLs. Render links with `rel="noopener noreferrer nofollow"`. |
| **Invite token on `Event`, not a separate Invite table** | Requirement is one shareable link per event. Rotate by regenerating the token; disable via `invite_enabled`. Add `expires_at` only if wanted. A per-invite table is only needed for single-use or per-person invites (out of scope). |
| **Use `PROTECT` on `Event.created_by`** | Avoids silently destroying an event if the creator's account is deleted. Transfer ownership first. |

## Secrecy Enforcement (the core promise)

### Visibility rules (the contract)

| Question | Rule |
|----------|------|
| Which wishes can viewer V browse? | `status=ACTIVE`, `owner != V`, and the wish is in at least one event where V is a member. |
| Who sees a Claim and its Contributions? | Anyone who can browse the wish under the rule above. The owner never does. The claimer and contributors also see it in "My gifts", even if they lost access through un-sharing or leaving (they know they committed). |
| Can V claim or chip in? | V can browse the wish, `owner != V`, and the claim does not exist yet (claim) or exists with `claimer != V` and no duplicate contribution (chip in). |
| Can owner O see their own wishes in an event? | Yes, through the owner space (a "Your wishes" section on the event page rendered from owner querysets and templates, with no claim data). |
| Who may mark received, edit, withdraw? | Owner only, via `Wish.objects.owned_by(user)`. |

Claim visibility is deliberately global: a viewer in event B sees "taken by Alice" even if Alice is not in B. This is what the requirement "no duplicate gifts across groups" implies. It is a privacy trade-off to confirm with the user (see Open Questions).

### Six layers of defence

1. **Structural separation (strongest).** No claim columns on `Wish`. The owner space never imports claim code. Owner and participant templates live in separate directories with separate card partials.
2. **Query-level exclusion.** `WishQuerySet.shared_with(user)` bakes in `exclude(owner=user)`. The owner's own wishes cannot appear in any participant list, even if a template renders claim data by mistake.
3. **Single chokepoint for claim reads.** One function returns claim info, and it raises if the viewer owns any of the wishes:

```python
# gifter/selectors.py
def claim_views_for(viewer, wishes):
    wishes = list(wishes)
    if any(w.owner_id == viewer.id for w in wishes):
        raise SecrecyViolation("claim data requested for viewer's own wish")  # loud, tested
    claims = (Claim.objects.filter(wish__in=wishes)
              .select_related("claimer").prefetch_related("contributions__user"))
    return {c.wish_id: ClaimView.from_claim(c, viewer) for c in claims}   # plain dataclass, no ORM objects
```

   Returning plain dataclasses (`ClaimView(claimer_name, contributor_names, is_mine, can_chip_in)`) means templates never hold a `Claim` and cannot traverse relations.
4. **404, not 403.** Guessing `/events/<e>/wishes/<w>/claim` as the owner or a non-member returns 404 via `get_object_or_404(Wish.objects.shared_with(user), pk=...)`, so the response reveals neither the wish nor the claim.
5. **Secure-by-default routing.** `LoginRequiredMiddleware` protects every new view. Every participant view resolves its event with `get_event_for_member`.
6. **Canary tests in CI (see below).** These catch regressions the structure does not.

### Side channels to close explicitly

| Leak | Prevention |
|------|-----------|
| `Wish.updated_at` changes when claimed | Claim writes go only to `Claim`/`Contribution`. Never call `wish.save()` from claim services. |
| Owner sees ordering/filtering/counts by claimed state | Owner lists sort by priority and created date only. No "claimed" filter or badge count. |
| Owner deletes a claimed wish and gets a different response | Owner "delete" is always a soft `WITHDRAWN`. Same response either way. The claimer sees "withdrawn by owner" in My gifts. |
| Owner edits a claimed wish and gets a blocked/different flow | Edits are always allowed, with no "can't edit, claimed" error. |
| Error messages and `messages` framework | No claim-aware text in any owner-space response. |
| Notifications and email (later) | Any future notification goes to claimers/participants, never to the owner. Do not build a "someone claimed your wish" notification. |
| Django admin | Do not register `Claim`/`Contribution` in admin, or restrict them to superuser. The author is also a giftee, so treat admin as a known self-spoiler risk. |
| Debug output | `DEBUG=False` in production. No `django-debug-toolbar` in prod. Never log claim payloads. |
| Shared URL structure | Participant URLs carry the event id, and the owner's own wishes use `/wishes/<pk>/`. There is no `/wishes/<pk>/claim`. |

### Canary test pattern (the highest-value test file)

```python
# gifter/tests/test_secrecy.py
CANARY_CLAIMER = "Zxqv Canary-Claimer"
CANARY_CONTRIB = "Zxqv Canary-Contrib"

def test_owner_never_sees_claim_anywhere(client, owner, claimed_wish_with_contributors):
    client.force_login(owner)
    for name, kwargs in OWNER_REACHABLE_URLS(owner):       # enumerate ALL named routes, with args
        resp = client.get(reverse(name, kwargs=kwargs))
        body = resp.content.decode()
        assert CANARY_CLAIMER not in body and CANARY_CONTRIB not in body
```

Also add a test that fails if a new URL name is added without being registered in the route inventory (forces every new route into the secrecy sweep). Additionally cover:
- POST claim as owner returns 404.
- Non-member gets 404 on event and wish routes.
- Owner's event page shows "Your wishes" with no claim data.
- Withdrawn and received wishes are identical in the owner's view.
- Query-count test on the event page (no N+1).

## Architectural Patterns

### Pattern 1: Selectors for reads, services for writes

**What:** Views never build visibility filters or mutate state themselves. They call `selectors.*` and `services.*`.
**When to use:** Any rule that touches secrecy or invariants (all of them here).
**Trade-offs:** A little indirection. At this size it is still cheap, and it makes the secrecy audit one file.

```python
# gifter/services.py
@transaction.atomic
def claim_wish(user, wish_id):
    wish = get_object_or_404(Wish.objects.shared_with(user), pk=wish_id)   # visibility + not-owner
    try:
        with transaction.atomic():
            return Claim.objects.create(wish=wish, claimer=user)
    except IntegrityError:                                                  # OneToOne race
        raise AlreadyClaimed()
```

Do not rely on `select_for_update` (no-op on SQLite). The unique constraint plus catching `IntegrityError` works on SQLite and Postgres.

### Pattern 2: Release with hand-over

**What:** If the claimer releases and contributors exist, promote the earliest contributor to claimer (update `Claim.claimer`, delete their `Contribution`). If none, delete the Claim.
**When to use:** The `release_claim` service. It keeps a group gift alive when the lead drops out.
**Trade-offs:** Slightly more code than "release deletes everything". The simpler fallback is acceptable if time is short, but flag it in the UI ("this removes the group").

### Pattern 3: Wish status as a small state machine

```
ACTIVE ──owner marks received──▶ RECEIVED ──owner "undo"──▶ ACTIVE
ACTIVE ──owner removes──────────▶ WITHDRAWN        (terminal for v1)
```

- Claims and contributions are retained on `RECEIVED` and `WITHDRAWN`. They are not shown to anyone except in "My gifts" for involved users.
- Others' event lists filter `status=ACTIVE`. The owner's list shows Active and a "Received" archive tab.
- The owner sees only status, never "who gave", which satisfies "still without revealing the giver".
- Give the giver a positive signal in My gifts ("Received" tick). It does not reveal anything to the owner.

### Pattern 4: Invite-join flow (safe against link previewers)

```
GET /join/<token>/
   ├─ invalid / disabled token → friendly 404 page
   ├─ not authenticated → store token in session, redirect to allauth login (next=/join/<token>/)
   └─ authenticated → confirm page "Join <event>?" (shows event name and organiser)
POST /join/<token>/  → services.join_event(user, token): get_or_create membership → redirect to event
```

- Joining is idempotent (`get_or_create` plus the unique constraint).
- Do not mutate state on GET: WhatsApp, Messenger and similar link previewers fetch URLs.
- Keep the token in the session as a fallback in case the OAuth round trip drops `next`.
- `/join/<token>/` is the one public-ish route. It uses `@login_not_required` and handles auth itself.

### Pattern 5: Sharing wishes into events

- Owner space wish form includes a `ModelMultipleChoiceField` of events the owner belongs to (queryset `Event.objects.member_of(user)`). The service re-validates membership server-side.
- The event page offers "Add my wishes to this event" as a bulk shortcut using the same service.
- Leaving an event deletes the leaver's `EventWish` rows for that event and releases claims or contributions the leaver made on wishes no longer visible to them (`services.leave_event`).
- Everyone may add and share, and no one is required to. A member with zero shared wishes appears in the participant list as "no wishes yet", and nothing is forced.

### Pattern 6: i18n from the first template

- `LocaleMiddleware` (after `SessionMiddleware`), `LANGUAGES = [("en", ...), ("cs", ...)]`, `LOCALE_PATHS`, and a `set_language` switcher that stores the choice in a cookie.
- **No URL language prefixes.** Invite links stay language-neutral and short. If a user's language preference should follow them across devices, add a small `Profile.language` later.
- Wrap every string in `gettext_lazy` or `{% trans %}` from the first view. Enum labels (`Priority`) too. The `.po` translation can be filled in near the end, but the marking cannot be retrofitted cheaply.
- Czech plurals have three forms (`ngettext` or `{% blocktrans count %}`). Avoid counting strings that need plurals wherever possible.

## Data Flow

### Request flow (participant claiming a wish)

```
Participant taps "I'll get this"
    ↓
POST /events/<e>/wishes/<w>/claim  → LoginRequiredMiddleware → participant.ClaimView
    ↓                                       ↓
get_event_for_member (404)     services.claim_wish(user, w)
    ↓                                       ↓
Wish.objects.shared_with(user)  → INSERT Claim (UNIQUE wish_id)
    ↓                                       ↓
redirect (PRG) ← messages ←──── IntegrityError → AlreadyClaimed → "someone just took it"
    ↓
GET event page → selectors.event_wish_cards(user, event)
    → Wish rows (owner != user, ACTIVE) + claim_views_for(user, wishes) → ClaimView dataclasses
    → templates/gifter/participant/*.html
```

### Key Data Flows

1. **Sign-in:** Google, then allauth creates or links the `User`, then a redirect to `next` or the dashboard. For invite arrivals, `next` is `/join/<token>/`.
2. **Owner edits a wish:** owner view, `WishForm` (explicit `fields = [...]`, never `__all__`), `form.save(commit=False)`, set `owner=request.user`, save the links formset, then `share_wish` syncs `EventWish` rows. No claim code is touched.
3. **Claim visible across events:** the Claim is keyed by `wish_id`. Event A's and event B's participant pages both call `claim_views_for`, so both show "taken". There is no per-event claim row to keep in sync.
4. **Receive:** owner POST `/wishes/<pk>/received` runs `services.mark_received(owner, pk)`, which sets `status` and `received_at`. The wish disappears from every participant's event list immediately, and the claimers' My gifts shows it as received.
5. **My gifts (claimer or contributor):** `selectors.my_gifts(user)` queries `Claim` and `Contribution` by `user` directly (not through event visibility), so commitments never vanish if the wish is un-shared or withdrawn. Withdrawn and received states are shown explicitly.

## Suggested URL Map

| Route | Space | Purpose |
|-------|-------|---------|
| `/accounts/...` | auth | allauth (replaces `/login/` and `registration/login.html`) |
| `/` | event | Dashboard: my events, link to my wishes, My gifts |
| `/wishes/`, `/wishes/add/`, `/wishes/<pk>/edit/` | owner | Own list (Active / Received tabs), create, edit (including links and sharing) |
| `POST /wishes/<pk>/received/`, `/withdraw/` | owner | Status transitions |
| `/events/new/`, `/events/<pk>/` | event | Create, event page (people and wishes, plus "Your wishes") |
| `/events/<pk>/members/<uid>/` | participant | One person's wishes in this event (owner viewing self gets redirected to owner space) |
| `/events/<pk>/wishes/<wid>/` | participant | Wish detail with claim state |
| `POST /events/<pk>/wishes/<wid>/claim\|release\|chip-in\|unchip/` | participant | Claim actions |
| `POST /events/<pk>/invite/rotate/`, `/leave/` | event | Invite management, leave event |
| `/join/<token>/` | event (public-ish) | Invite landing, confirm, POST to join |
| `/gifts/` | participant | "My gifts": my claims and chip-ins with status |

Existing `/gifter/add` should move to `/wishes/add/`. Update `create_wish.html` and links in one pass.

## Fixes Required in Existing Code

| Existing | Problem | Fix |
|----------|---------|-----|
| `CreateWishView.post` calls `form.save()` | `user` is non-null and not set, so `IntegrityError`. Also no login required. | `obj = form.save(commit=False); obj.owner = request.user; obj.save()`. Replace `HttpResponse('...')` with a redirect to the list. Convert to `CreateView`. |
| `WishForm.fields` includes `is_active` | Owner could set state through the form. Becomes `status`, which is service-controlled. | `fields = ["name", "description", "priority"]`. Links and sharing come through a formset and a separate field. |
| `Wish.description` required | Wedding guests and quick adds will not write one. | `blank=True`. |
| `INSTALLED_APPS` / `MIDDLEWARE` | No auth, i18n or login-required middleware. | Add allauth apps, `LocaleMiddleware`, `LoginRequiredMiddleware`, `LOGIN_URL`, `LOGIN_REDIRECT_URL`. |
| Settings are dev-only | Hard-coded `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=[]`. | Env-driven settings in the foundation phase (deployment is a requirement). |
| `TEMPLATES["DIRS"]` empty | No shared base template. | Add `templates/gifter/base.html` (in-app), keep `APP_DIRS=True`. |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k users (the real target: families, friends) | The monolith as designed. SQLite or Postgres both fine. Use `select_related`/`prefetch_related` in `event_wish_cards` to avoid N+1 (events hold at most about 20 people x 20 wishes). |
| 1k-100k users | Postgres, DB indexes on `EventWish(event)`, `Claim(claimer)`, `EventMembership(user)`. The unique constraints already index most paths. |
| 100k+ users | Not a concern for this project. |

### Scaling Priorities

1. **First bottleneck:** SQLite on an ephemeral PaaS filesystem is a durability risk, not a scale risk. Hosting choice (STACK.md) should provide a persistent volume or managed Postgres.
2. **Second bottleneck:** event page query count. Keep `claim_views_for` to one query plus prefetches.

## Anti-Patterns

### Anti-Pattern 1: One wish-card template with `{% if viewer != wish.owner %}`

**What people do:** Share one partial between owner and participant views and hide claim info with a conditional.
**Why it's wrong:** One missed context variable or a copied partial leaks the secret. The failure is silent.
**Do this instead:** Separate `owner/` and `participant/` templates. The owner's context never contains claim data.

### Anti-Pattern 2: Claim fields or a `claimed` annotation on `Wish` serialised everywhere

**What people do:** Keep `Wish.claimed_by`, add `is_claimed`, annotate querysets, use `ModelForm` with `__all__`.
**Why it's wrong:** Every owner-facing path now carries the secret, and one `{{ wish.claimed_by }}` or form field leaks it.
**Do this instead:** Claim tables separate from Wish, `related_name="+"`, explicit form `fields`, plain-dataclass `ClaimView` for participants.

### Anti-Pattern 3: 403 or distinct errors that confirm existence

**What people do:** Return "you can't claim your own wish" or 403 on a probe.
**Why it's wrong:** It confirms the wish exists and discloses claim logic to the owner.
**Do this instead:** Resolve objects through visibility querysets and return 404.

### Anti-Pattern 4: Hard-deleting claimed wishes or claim-aware owner UX

**What people do:** `wish.delete()`, or "this wish is claimed, you can't delete it".
**Why it's wrong:** The first strands a claimer who has already bought the gift. The second tells the owner it is claimed.
**Do this instead:** Soft `WITHDRAWN` status, identical owner-side behaviour.

### Anti-Pattern 5: State change on GET invite

**What people do:** `/join/<token>/` joins immediately.
**Why it's wrong:** Link previewers and prefetchers will join the bot, or fail to complete the auth hop.
**Do this instead:** GET shows a confirm page and POST joins.

### Anti-Pattern 6: Premature generalisation

**What people do:** Add Groups, Invite tables, notification frameworks, a REST API, a Profile model, or per-event claims "just in case".
**Why it's wrong:** Eight weeks to Christmas. All of these are explicitly out of scope or deferrable.
**Do this instead:** Build exactly the models above. `EventWish` and `Event.invite_token` leave room to grow.

### Anti-Pattern 7: Relying on `select_for_update` for single-claimer races

**What people do:** `select_for_update()` then check-and-insert.
**Why it's wrong:** It is silently a no-op on SQLite.
**Do this instead:** The `OneToOneField` unique constraint plus `IntegrityError` handling.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google OAuth | django-allauth Google provider; configure the consent screen and redirect URI for the production host | Needs HTTPS and a real domain. Deploy a skeleton early (see build order). Consent screens left in "testing" restrict logins to listed test users, so publish the app before the family uses it. Verify current requirements in the auth phase. |
| Hosting / static | Behind a TLS-terminating proxy: `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS`, static served by WhiteNoise or the host | Decided in STACK.md. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Owner views to claim code | **Forbidden** (enforce by test or lint: owner modules do not import `Claim`, `Contribution`, `claim_views_for`) | A tiny test that greps `views/owner.py` and `templates/gifter/owner/` for these names is cheap and effective. |
| Views to selectors/services | Direct function calls | Views do not hand-build visibility filters. |
| Participant templates to claim data | `ClaimView` dataclasses only | No ORM objects for claims in context. |
| Event space to owner space | Event page includes an owner-built "Your wishes" block | Rendered from owner querysets and templates. |
| Services to models | `transaction.atomic`, DB constraints as backstop | Domain exceptions map to user-facing messages in views. |

## Build Order (dependencies, for roadmap phasing)

```
0 Foundation ─▶ 1 Auth (+ early deploy) ─┬▶ 2 Owner wishlist ─┐
                                          └▶ 3 Events + invite ┴▶ 4 Sharing + participant browse
                                                                       ▼
                                                          5 Claims + chip-in + secrecy tests
                                                                       ▼
                                                          6 Received/withdraw + My gifts
                                                                       ▼
                                                          7 Czech translation, responsive polish, hardening
```

| # | Phase | Contents | Depends on | Why this position |
|---|-------|----------|-----------|-------------------|
| 0 | Foundation | Fix `owner` bug, rename `user` to `owner`, `status` migration (drop `claimed_by`), views/ package and urls at root, base template with i18n marking, `LocaleMiddleware`, env-driven settings, test scaffolding | none | Everything else builds on these names and layout. Cheap now, expensive after more code exists. |
| 1 | Auth (Google) + skeleton deploy | allauth Google, `LoginRequiredMiddleware`, login/logout UI, deploy to public host with HTTPS | 0 | OAuth needs a real redirect URI and domain, and the deployment is the likeliest source of schedule surprise. Doing it at about week 2-3 leaves buffer before Christmas. |
| 2 | Owner wishlist | Wish CRUD with priority and links (formset), Active/Received lists | 1 | Needs only the user. It can run in parallel with phase 3. |
| 3 | Events + invite | Event, EventMembership, create, event page shell, invite token, join flow with session fallback, leave | 1 | Independent of wishes. Invite and OAuth interplay is the risky part (phase flag below). |
| 4 | Sharing + participant browse | `EventWish`, share selector in wish form, `selectors.shared_with`, participant event/member pages (read-only), "Your wishes" owner block | 2, 3 | Builds the `shared_with` visibility foundation that claims will plug into. Establish the owner/participant template split here, before claims exist. |
| 5 | Claims + chip-in + secrecy suite | `Claim`, `Contribution`, `claim_views_for` chokepoint, services (claim, release with hand-over, contribute, uncontribute), canary tests, route-inventory test | 4 | The core promise. The canary suite must be merged in this same phase and run in CI from here on. |
| 6 | Lifecycle | `mark_received` (and undo), `withdraw`, "My gifts" page, hide non-active from others | 5 | Needs claims to exist so received and withdrawn semantics can be tested against them. |
| 7 | Polish and release | Czech `.po`, responsive pass on the real phone flow, production hardening, `requirements.txt` trim, family beta | all | i18n marking was done earlier, so only translation work remains. |

**Parallelism:** phases 2 and 3 can run in parallel. Phase 5 is the critical path; start the canary-test harness (fixtures and the route inventory) in phase 4 so it is ready.

**Research flags:**
- Phase 1: needs phase-level research (allauth version and settings, Google consent screen publishing status, `next` preservation across social login, `django.contrib.sites` requirement).
- Phase 3: moderate (invite token plus OAuth round trip when the user is not yet logged in).
- Phases 2, 4, 5, 6: standard Django patterns, no further research needed.
- Phase 7: Czech plural forms, and the hosting-specific static and proxy settings.

## Open Questions (confirm with the user)

1. **Cross-event claim visibility of names.** A viewer in event B sees "taken by Alice" even if Alice is not in B. This follows the stated requirement. Alternative: show only "taken" to viewers who share no event with the claimer. Needs a product decision.
2. **Stale claims across years.** The claim lives on the wish, and the wish lives on the personal wishlist. A Christmas 2026 claim remains if the gift is never marked received. Mitigations: show the claim date, let claimers release, and optionally prompt claimers after an event date passes. No auto-expiry in v1.
3. **Claimer release with contributors.** Hand-over to the earliest contributor (recommended) versus dissolving the group.
4. **Leaving an event.** Does it release the leaver's claims on wishes no longer visible to them? Recommended: yes, and warn first.
5. **Undo received.** Is it allowed? Recommended: yes, to cover mis-taps.

## Sources

- Django 5.1 release notes (`LoginRequiredMiddleware`, `login_not_required`); Django docs on `UniqueConstraint`, `OneToOneField`, `transaction.atomic` and `select_for_update` backend caveats; i18n docs (`LocaleMiddleware`, `set_language`, pluralisation). All from established knowledge of Django 5.1 docs. Confidence HIGH, though the docs were not re-fetched this session.
- Selectors and services layering is the common "HackSoft Django Styleguide" convention. Confidence HIGH as a pattern, and an opinionated fit here.
- django-allauth Google provider details. MEDIUM, to be verified in phase 1 research.
- Project inputs: `/home/ciakval/GIT/gifter/.planning/PROJECT.md`, `src/gifter/{models,views,urls,forms}.py`, `src/web/{settings,urls}.py` (read directly).

---
*Architecture research for: group gift wishlist with secret claiming (Django)*
*Researched: 2026-10-15*
