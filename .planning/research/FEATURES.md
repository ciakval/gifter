# Feature Landscape

**Domain:** Group gift wishlists with secret claiming and chip-in (Gifter: personal wishlist shared into Events, hidden from the giftee)
**Researched:** 2026-10-15
**Overall confidence:** MEDIUM. The claim and secrecy conventions are well documented (HIGH). Chip-in is documented only for some competitors (MEDIUM). Behavior when a claimed wish is edited or deleted is not documented by any product I could find (LOW). Section "Edge-case behavior" is therefore my recommendation, not an industry standard.

## How comparable products work (evidence)

| Product | Claim model | Hidden from owner? | Group gift / chip-in | Notes |
|---------|-------------|--------------------|----------------------|-------|
| Giftster | "Reserved" (intend to buy) then "Purchased"; release via unlock icon; per-unit quantities; personal "My shopping list" | Yes. The owner sees neither status. Exception: parent-managed child lists show status to the parent. | No pooled money. Workaround is listing an expensive item as several smaller units. | Shoppers on public lists can claim as guests (name and email). Members can secretly suggest items on someone's list. (HIGH, official help pages) |
| Elfster | "Mark as purchased" with quantity; undo available | Yes. The owner is not notified. Other viewers see "bought" but not by whom. | Not documented in official sources. | Primary product is Secret Santa draw, with wishlists as a side feature. Priority is high/low. (HIGH for claim, LOW for group gifts) |
| GiftList | Reserve on a linked wishlist | Yes, visible to other viewers to avoid duplicates | Group gifting and cash contributions, payments via external services | Vendor marketing, treat as MEDIUM. |
| Wishpicks | Reserve | Hidden by default, with an owner opt-in "Reveal reservations" setting | Not checked | Shows that some products let the owner opt in to seeing claims. This contradicts Gifter's strict-secrecy promise. (MEDIUM) |
| Amazon lists | "Purchased" tracking | "Don't spoil my surprises" setting, on by default, keeps the item showing as unpurchased to the owner. Buyers get a duplicate-purchase warning. | None | Amazon also sends the owner a notification when an item is bought, with no buyer identity. (HIGH for the setting, MEDIUM for the notification) |
| Tomikup.cz (Czech) | Login-gated reservation | Owner does not see who reserved. Other participants see who did. | Not described | Shared via link. Items from description, picture or e-shop link, plus a browser extension. 2020 article, no groups documented. (MEDIUM) |
| Wishfox, WishApp | Reservation, in Wishfox without an account | Hidden from the recipient, visible to other givers | Not described | Same pattern. Czech-language reservation apps are thin on the ground, so the market is "same model as Giftster, in Czech". (LOW-MEDIUM) |

The core convention is consistent across all of them. A claim is visible to every viewer except the owner, it can be undone, and the owner is not notified. Gifter's "claim lives on the Wish, visible across all events" is the same model as Giftster's, where a wish is claimed once on the list itself.

## Table Stakes

Missing any of these and the family cannot use the app for Christmas 2026.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Google sign-in | Chosen login; relatives will not create passwords | Low-Med | Use django-allauth. The existing `LoginView` is replaced. A "log in to see this invite" redirect flow matters (see invite link). |
| Create Event (name, optional date) | Container for an occasion | Low | Creator becomes organizer. Date is optional and display-only. |
| Invite link, join on open | Chosen join mechanism; share via chat apps | Med | Unguessable token, login-then-join redirect (preserve `next` through the Google OAuth round trip), idempotent re-join. |
| Invite-link regeneration or revoke | A public link in a family chat can leak. Event contents are the secret. | Low | One button "new link, old link dies". Cheaper than per-member approval. |
| Member list in event | Everyone sees who is in the event | Low | Also needed so the browse page can list "people". |
| Leave event | Basic hygiene | Low | Claims stay on the wish (claims live on the Wish). Define what happens to a leaver's contributions (see edge cases). |
| Personal wishlist CRUD (name, description, link(s), priority) | The core object. Priority is the one metadata field Elfster and others agree on. | Med | Multiple links per wish means a `WishLink` child table. Priority as 3 levels (high/normal/low). Fix the existing `Add Wish` view (it does not set owner). |
| Choose which wishes go to which events | The "personal wishlist shared into events" model | Med | Many-to-many Wish to Event. Provide "share all my wishes" as a one-click default plus per-wish checkboxes. This is the highest UX-risk screen for non-technical users. |
| Participation is optional | Wedding guests have no wishes | Low | Members with zero shared wishes still see others' wishes. Empty state says "nothing shared yet", not an error. |
| Browse others' wishes in an event | Core read path | Low-Med | Grouped by person, sorted by priority, available items first. |
| Claim a wish (single claimer), shown to everyone except the giftee, with claimer name | Core value | Med | The claim sits on the Wish, not the event membership. Shows as taken in every event the wish is shared into. Atomic claim (unique constraint or `select_for_update`) to survive two people tapping at once. |
| Release my claim | Every product has undo (Giftster unlock, Elfster undo). People claim by mistake or change plans. | Low | See the edge case for release when contributors exist. |
| "My claims" view (what I am buying, across events) | Giftster "My shopping list". Users need a to-buy checklist, and claims span events. | Low | Doubles as the surface where "wish was withdrawn or changed" notices appear. |
| Chip-in on a claimed wish | Chosen feature | Med | A `Contribution` row (wish, user). No money amounts. The claimer remains the responsible person. Contributors can leave. |
| Strict giftee secrecy | The core promise | Med-High (care, not code volume) | See "Secrecy rules" below. Must be enforced in queries, not templates. Needs automated tests. |
| Giftee marks wish as received, which closes it | Chosen feature, closes the loop | Low | Closed wishes move to a collapsed "received" section for the owner. Claim data is retained but never shown to the giftee. |
| EN + CZ UI | Chosen requirement | Med | `gettext` from the first template. Language from the browser with a manual switch. Czech plural forms (three forms) and date formatting. |
| Responsive mobile layout | Relatives open links in chat apps on phones | Low-Med | Invite links open in an in-app browser (WhatsApp/Messenger/Viber). Google OAuth can be blocked in some embedded webviews ("disallowed_useragent"). Test this early. |
| Public hosting with HTTPS | Chosen requirement | Med | Production settings, secret management, static files, OAuth redirect URIs registered. |

## Secrecy rules (table stakes, spelled out)

The giftee's own view is the highest-risk surface. Competitors handle it by simply not rendering status for the owner. Amazon goes further and shows items as unpurchased. Recommended rules for Gifter:

1. **Giftee view of own wish = a view that never loads claim or contribution data.** Use a separate queryset and template for "my wishes". Do not reuse the participant card with `if not is_owner` conditionals. This is the common leak pattern.
2. **Wish detail URLs for own wishes route to the owner view.** Any endpoint returning a wish checks `wish.owner == request.user` and drops claim fields. This includes JSON endpoints, HTMX partials and admin-ish pages.
3. **A giftee cannot claim or chip in on own wish.** Enforce server-side.
4. **No side channels.** No notifications or emails on claim (Amazon notifies the owner on purchase, so do not copy that). No "N claimed" counts in event summaries shown to a giftee. No ordering or sorting by claimed state in the owner view. No claim-timing in logs surfaced to the owner.
5. **Owner can edit and delete without a warning dialog about claims.** A warning ("someone has claimed this") is itself a leak. Same for the giftee seeing disabled controls.
6. **Event-creator is not special.** An organizer must not see claims on their own wishes either. Do not build any organizer overview of all claims.
7. **Receipt does not show the giver.** (Already decided.)
8. **Strict means no opt-in reveal.** Wishpicks has a "reveal reservations" setting. Do not add one.

## Edge-case behavior (recommendations, LOW confidence on industry practice)

No source documented these. Proposed defaults, chosen to keep secrecy intact and stay cheap.

| Situation | Recommended behavior | Rationale |
|-----------|---------------------|-----------|
| Giftee edits a claimed wish | Allow. Claimer and contributors see the updated text. Show a small "changed since you claimed" marker (store `updated_at` and `claim.created_at`). | The giftee cannot be told about the claim. The claimer needs to know a link or description changed, e.g. a different color. The marker is cheap. |
| Giftee deletes a claimed wish | Allow without warning. Soft-delete: the wish disappears from the giftee's lists and from browse. The claimer's "My claims" shows it as "withdrawn by owner" with the original name and link retained, and a one-click dismiss. | Hard-delete cascades away the claimer's record and they may have already bought it. A silent disappearance is the worst outcome. Soft-delete also avoids a leak, because the giftee sees nothing different. |
| Giftee un-shares a claimed wish from one event | Allow. The claim persists if the wish remains in any other event. If it was in only that event, treat as withdrawn (same as delete). | The claim belongs to the Wish. |
| Claimer releases a claim that has contributors | Promote the earliest contributor to claimer, and tell them. If none, wish becomes available. | Avoids orphaned group gifts and needs no negotiation UI. |
| Contributor leaves | Remove the row, no notification needed. | Simple. |
| Event member leaves | Their claims and contributions remain. They stay visible as the claimer name. | The claim belongs to the Wish. Releasing them silently could cause duplicate gifts. |
| Claimer's name visibility across events | Show claimer name to anyone who can see the wish in any event. | Matches the PROJECT.md decision. Note it can expose a name to people in another event. Acceptable for family and friends. Flag it as a decision to confirm. |
| Receipt then claimer view | In the claimer's "My claims", the wish shows as "received". The giver gets a confirmation. The giftee still does not learn who. | Closes the loop for the giver. Consistent with "receipt does not reveal the giver". |
| Mark received by mistake | Allow "reopen". Low cost, avoids a support burden. | |
| Quantity greater than 1 (e.g. 3 pairs of socks) | Not supported in v1. Document the workaround of creating separate wishes. | Giftster and Elfster track per-unit quantities. It changes the claim model (N claims per wish), so defer it. |
| Giftee's own claim attempt via URL | 403/404. | See secrecy rules. |

## Differentiators

Not expected for v1. Pick sparingly. The strict-secrecy-plus-chip-in model is itself the differentiator.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Reserved vs purchased status (Giftster) | Shows "I plan to buy" versus "bought", which reduces last-minute panic before Dec 24 | Low | One enum field on the claim. Recommend including in v1 if the claim model is built anyway. Cheap and high value for Christmas. |
| Free-text contribution note ("I'll put in 500 Kč") | Group gift coordination without handling money | Low | A text field on `Contribution`. Visible to other non-giftees. |
| "Changed since you claimed" marker | Prevents buying a stale spec | Low | Already in edge cases. |
| Secret suggestions on someone's list (Giftster) | Relatives add ideas for the giftee that only other givers see | Med | Needs a second visibility class of Wish. Defer past v1. This is also the natural stepping stone to the "hidden discussion" feature that PROJECT.md defers. |
| Hidden comments on a wish (among non-giftees) | Coordinating chip-in details | Med-High | Already out of scope (PROJECT.md). Secrecy surface grows. |
| Event date with countdown or "gifts opened" state | Context for Christmas | Low | Display-only. In Czech families gifts are usually opened on Dec 24, so receipts will cluster on Dec 24-26. Keep mark-received to one tap per wish, mobile friendly. |
| Add-to-wishlist from a URL (title and image scraping) | Faster entry. Tomikup and most Giftster-class apps have it. | Med-High, brittle | Scrapers break on e-shops and anti-bot pages. Price and images are already out of scope. Store the URL and show its domain. Do not scrape in v1. |
| Bookmarklet or browser extension | Competitors have one | High | Defer indefinitely. |
| Email or push reminders (release unclaimed claims, event date coming) | Retention | Med | Email infrastructure plus the secrecy review. Defer. |
| Multiple-claim quantities | Realistic for consumables | Med | See edge cases. |
| Event-level wish "pinning" of favorites | Marginal | Low | Skip. |

## Anti-Features

Deliberately not building.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Money handling or payment pooling (collect, split, track funds) | Legal and PCI exposure, trust issues, and none of the free Giftster-class products do it. Family settles up in person. | Chip-in is only a "who is in" list plus an optional free-text note. |
| Secret Santa draw, exclusions, anonymous messaging | That is Elfster's category. It is a different product with a different data model. | Stay with open wishlists plus claims. |
| Opt-in reveal of claims to the giftee (Wishpicks style), or an owner notification on purchase (Amazon style) | Breaks the core promise. Both leak. | Strict secrecy only. Receipt is the sole giftee-visible signal. |
| Guest or anonymous claiming without login (Giftster public lists, Wishfox) | Claims need an identity so others see "taken by Anna" and the giftee-exclusion check works. Accounts are Google-only, which is already low friction. | Login via invite link only. |
| Email or password signup | Already out of scope | Google only. |
| Persistent groups, per-person friend graph | Already out of scope | Events plus personal wishlist. |
| Email invitations | Already out of scope | Invite link. |
| Revealing the giver after receipt | Already out of scope | Receipt closes the wish. |
| Price tracking, price fields, wish images | Already out of scope | Link plus description. |
| Parent-managed child lists (Giftster style, where the parent sees claims) | Introduces an exception to strict secrecy and a delegated-account model | A parent can add wishes on the child's behalf in a later milestone, if needed. Not v1. |
| Organizer/admin dashboard showing all claims | Violates secrecy for organizers who are also giftees | No such view. |
| Social features (feeds, likes, followers) | Not relevant to the occasion-based model | None. |
| Native mobile app | 8-week timeline | Responsive web. |

## Feature Dependencies

```
Google sign-in
  -> Create Event
       -> Invite link (join) -> Member list -> Leave event
  -> Personal wishlist CRUD
       -> Share wishes into events (needs Event and Wish)
            -> Browse others' wishes in an event
                 -> Claim (needs Wish, user identity, giftee exclusion)
                      -> Release claim
                      -> Chip-in (needs an existing claim)
                           -> Release-with-contributors rule
                      -> My claims view
                      -> Reserved vs purchased status (differentiator)
                 -> Mark received (owner action, needs Wish; claim data retained)
Strict secrecy  -> constrains EVERY read path above (owner view must be separate)
i18n (gettext)  -> applies to every template from the first one
Mobile layout   -> applies to every template; test invite-link-in-chat-webview early
Public hosting  -> needs Google OAuth redirect URIs, so do it early, not last
```

Data-model implications for the roadmap: `Wish` (owner, active/closed/deleted state) many-to-many `Event` via a share table. A one-to-one `Claim` on `Wish` (claimer, status, created_at). A `Contribution` (wish, user, note). The existing `Wish.claimed_by` FK gets replaced by `Claim`. Receipt is a state on the Wish (`received_at`), not a deletion, so the claim record survives for the claimer's view.

## MVP Recommendation

Prioritize, in build order:
1. Google sign-in, fix of Wish ownership, production deployment skeleton (OAuth redirect URIs need a real domain early)
2. Events plus invite link plus member list
3. Wish CRUD (name, description, links, priority) plus share-into-events
4. Browse others' wishes, claim, release, "My claims" (with reserved/purchased status)
5. Strict secrecy audit and tests (written alongside step 4, not after)
6. Chip-in
7. Mark received, edit and delete semantics for claimed wishes
8. EN/CZ translation pass and mobile polish (gettext markup from step 1, translation content at the end)

Include a cheap differentiator or two: reserved/purchased status and the contribution note.

Defer: secret suggestions, hidden comments, quantities, URL scraping, notifications, price and images. The first three are the likeliest next-milestone candidates. Notifications need a secrecy review first.

## Sources

- [Giftster help: Will the list owner see if I mark an item reserved or purchased?](https://help.giftster.com/article/72-will-list-maker-see-reserved-purchased) (HIGH, official)
- [Giftster help: Reserve and purchase items](https://help.giftster.com/article/69-mark-gift-purchased) (HIGH, surfaced via search snippet, page itself returned 403)
- [Elfster help: mark an item bought on another wishlist](https://help.elfster.com/en/articles/11517983-how-do-i-mark-that-i-bought-an-item-on-another-elfster-wishlist) (HIGH, official)
- [GiftList vs Elfster](https://giftlist.com/blog/giftlist-vs-elfster) (MEDIUM, competitor marketing)
- [GiftList vs Giftster](https://giftlist.com/blog/giftster-vs-giftlist) and [Giftful vs GiftList](https://giftlist.com/blog/giftful-vs-giftlist) (LOW-MEDIUM, competitor marketing; the claim that Giftster has no pooling is not verified in Giftster's own docs)
- [Wishpicks docs: can I see if someone reserved my gift](https://docs.wishpicks.com/en/articles/16189861-can-i-see-if-someone-reserved-my-gift) (MEDIUM)
- [Amazon help: Set Up Your Surprise Settings](https://digprjsurvey.amazon.com/csad/help/node/G9PJNRV76JRAXDJZ) (MEDIUM, mirror host)
- [Svet Androida: Tomikup.cz seznam prani](https://www.svetandroida.cz/aplikace-tomikup-cz-seznam-prani/) (MEDIUM, 2020 article)
- [Wishfox](https://peerlist.io/xergic/project/wishfox), [WishApp](https://addons.mozilla.org/cs/firefox/addon/wishapp/) (LOW, listings)
- No source found for edit/delete-of-claimed-wish behavior. The edge-case table is the author's recommendation (LOW).
