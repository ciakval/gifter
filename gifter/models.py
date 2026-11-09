import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """The one identity in Gifter. Google accounts are matched by allauth on Google's `sub`."""

    @property
    def display_name(self) -> str:
        # Never fall back to the username: allauth derives it from the email local part when the
        # Google profile has no name, so it would leak email-derived text onto member lists.
        return self.first_name or self.last_name or gettext("Unnamed member")


def new_invite_token() -> str:
    """22 URL-safe characters, 128 random bits."""
    return secrets.token_urlsafe(16)


class Event(models.Model):
    name = models.CharField(_("name"), max_length=200)
    date = models.DateField(_("date"), null=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    # SET_NULL, not PROTECT: deleting an account must never be blocked by events it created.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_events",
    )
    invite_token = models.CharField(
        _("invite token"), max_length=64, unique=True, default=new_invite_token, editable=False
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Membership",
        verbose_name=_("members"),
        related_name="events",
    )

    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")

    def __str__(self):
        return self.name


class Membership(models.Model):
    event = models.ForeignKey(
        Event, verbose_name=_("event"), on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    joined_at = models.DateTimeField(_("joined at"), auto_now_add=True)

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="unique_event_membership"),
        ]

    def __str__(self):
        return self.event.name


class Wish(models.Model):
    class Priority(models.IntegerChoices):
        HIGH = 1, _("High")
        NORMAL = 2, _("Normal")
        LOW = 3, _("Low")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        RECEIVED = "received", _("Received")
        WITHDRAWN = "withdrawn", _("Withdrawn")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishes"
    )
    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    priority = models.PositiveSmallIntegerField(
        _("priority"), choices=Priority, default=Priority.NORMAL
    )
    # Normalized web addresses, one per line (see forms.normalize_links).
    links = models.TextField(_("links"), blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=Status, default=Status.ACTIVE, db_index=True
    )
    # Sharing is explicit: a wish is visible in an event only through a row here.
    events = models.ManyToManyField(
        "Event", related_name="wishes", blank=True, verbose_name=_("events")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def link_items(self):
        items = []
        for line in self.links.splitlines():
            url = line.strip()
            if not url:
                continue
            domain = urlsplit(url).hostname or url
            domain = domain.removeprefix("www.")
            items.append({"url": url, "domain": domain})
        return items


class Claim(models.Model):
    """Someone is getting a wish. At most one per wish: the OneToOne is the unique constraint
    that decides simultaneous claims.

    related_name "+" removes every accessor from a Wish to its claim, so owner code and owner
    templates cannot reach claim data by accident. It also keeps the reverse relation out of
    `Wish._meta.get_fields()`, which the "no claim field on Wish" test walks. All claim reads and
    writes go through gifter/claims.py.
    """

    class Status(models.TextChoices):
        RESERVED = "reserved", _("Reserved")
        PURCHASED = "purchased", _("Purchased")

    wish = models.OneToOneField(
        Wish, on_delete=models.CASCADE, related_name="+", verbose_name=_("wish")
    )
    claimer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="claims",
        verbose_name=_("claimer"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status, default=Status.RESERVED
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    acknowledged_at = models.DateTimeField(_("acknowledged at"), default=timezone.now)

    class Meta:
        verbose_name = _("claim")
        verbose_name_plural = _("claims")

    def __str__(self):
        return self.wish.name


class Contribution(models.Model):
    """Someone chips in on another member's claim, with an optional note. No amounts."""

    claim = models.ForeignKey(
        Claim,
        on_delete=models.CASCADE,
        related_name="contributions",
        verbose_name=_("claim"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contributions",
        verbose_name=_("user"),
    )
    note = models.CharField(_("note"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    acknowledged_at = models.DateTimeField(_("acknowledged at"), default=timezone.now)

    class Meta:
        verbose_name = _("contribution")
        verbose_name_plural = _("contributions")
        constraints = [
            models.UniqueConstraint(fields=["claim", "user"], name="unique_claim_contribution"),
        ]

    def __str__(self):
        return self.claim.wish.name
