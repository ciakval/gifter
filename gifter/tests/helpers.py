"""Shared test helpers for the secrecy checks (Phase 3)."""

import re

from django.utils import translation

_CSRF_VALUE = re.compile(r'(name="csrfmiddlewaretoken" value=")[^"]*(")')
_NAV = re.compile(r"<nav\b.*?</nav>", re.S)


def mask_csrf(html):
    """Replace every CSRF token value with a fixed string, so two renders can be compared."""
    return _CSRF_VALUE.sub(r"\1MASKED\2", html)


def without_nav(html):
    """Remove the top bar. It carries generic copy (such as the My claims link) on every page."""
    return _NAV.sub("", html, count=1)


# Claim-state copy and claim-action URL fragments, case-sensitive, as rendered by
# includes/member_wish.html and my_claims.html. The protected property is information, not
# vocabulary (D-14 as amended on 2026-11-08): owner pages must not carry any of these, but the
# generic top-bar "My claims" link may appear anywhere, so it is deliberately not listed.
# The English copy is listed here; the Czech wording comes from CLAIM_STATE_MSGIDS below, so a
# claim-state label in either language on an owner page is caught.
CLAIM_STATE_MARKERS = (
    "Taken",
    "Purchased",
    "You are getting this",
    "chipping in",
    "Changed since you",
    "get this",
    "Chip in",
    "Mark purchased",
    "Release",
    "Stop chipping in",
    "Got it",
    "Someone just took it",
    "/claim/",
    "/chip-in/",
    "/purchased/",
    "/release/",
    "/leave/",
    "/got-it/",
)


# The msgids of the claim-state copy rendered by member_wish.html, my_claims.html and
# claim_views.py; their Czech translations are checked as markers too (plan 04-03).
CLAIM_STATE_MSGIDS = (
    "Taken",
    "Purchased",
    "Taken by someone",
    "Purchased by someone",
    "You are getting this.",
    "You are getting this one.",
    "You are chipping in.",
    "Someone is chipping in.",
    "Changed since you claimed",
    "Changed since you chipped in",
    "I'll get this",
    "Chip in",
    "Mark purchased",
    "Release",
    "Stop chipping in",
    "Got it",
    "Someone just took it.",
)


def czech_claim_state_markers():
    """Czech translations of CLAIM_STATE_MSGIDS, skipping any that equal their msgid."""
    with translation.override("cs"):
        translated = [translation.gettext(msgid) for msgid in CLAIM_STATE_MSGIDS]
    return [t for t, msgid in zip(translated, CLAIM_STATE_MSGIDS) if t != msgid]


def claim_state_markers(html):
    """The English claim-state markers found in html (tuple order), then the Czech ones."""
    found = [marker for marker in CLAIM_STATE_MARKERS if marker in html]
    return found + [marker for marker in czech_claim_state_markers() if marker in html]
