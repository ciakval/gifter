"""Shared test helpers for the secrecy checks (Phase 3)."""

import re

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


def claim_state_markers(html):
    """The claim-state markers found in html, in tuple order."""
    return [marker for marker in CLAIM_STATE_MARKERS if marker in html]
