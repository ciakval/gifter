from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """The one identity in Gifter. Google accounts are matched by allauth on Google's `sub`."""

    @property
    def display_name(self) -> str:
        return self.first_name or self.username


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
