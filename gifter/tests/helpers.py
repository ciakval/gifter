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
