from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

# Import allauth's admin modules explicitly so their registrations exist before we unregister
# them: gifter is first in INSTALLED_APPS, so admin autodiscovery imports this module first
# and unregistering would otherwise raise NotRegistered.
import allauth.account.admin as allauth_account_admin
import allauth.socialaccount.admin as allauth_socialaccount_admin
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken

from .models import User

admin.site.site_header = _("Gifter admin")
admin.site.site_title = _("Gifter admin")

admin.site.register(User, UserAdmin)

# Google credentials live only in settings. A SocialApp row on top of settings APPS raises
# MultipleObjectsReturned on every sign-in, and tokens are never stored.
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)


class ReadOnlySocialAccountAdmin(allauth_socialaccount_admin.SocialAccountAdmin):
    """View and delete only: editing a social account would forge an identity.

    Delete stays allowed because deleting a User cascades to these rows, and Django blocks the
    deletion if a registered related model denies delete.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ReadOnlyEmailAddressAdmin(allauth_account_admin.EmailAddressAdmin):
    """View and delete only; the make_verified action is dropped (it forges verification)."""

    actions = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.unregister(SocialAccount)
admin.site.register(SocialAccount, ReadOnlySocialAccountAdmin)
admin.site.unregister(EmailAddress)
admin.site.register(EmailAddress, ReadOnlyEmailAddressAdmin)

# Deliberately NOT registered: Wish and any claim or contribution model. The author is staff
# and also a giftee, and must never see who claimed his wishes (SECR-01).
