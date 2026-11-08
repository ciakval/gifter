import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
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


# Create your models here.
class Wish(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishes')
    is_active = models.BooleanField(default=True)
    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='claimed_wishes')

    def __str__(self):
        return self.name
