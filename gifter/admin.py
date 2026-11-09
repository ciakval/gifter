from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import FieldDoesNotExist
from django.db.models.constants import LOOKUP_SEP
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



class GifterUserAdmin(UserAdmin):
    """Users can be viewed and edited here, never deleted (SECR-01, T-03-18).

    The delete confirmation lists every row a deletion would take with it, including rows of
    models that are not registered (Claim and Contribution), shown by their string form. The
    author is staff and also a giftee, so that page would tell him who claimed his wishes.
    Denying delete also removes the delete_selected bulk action. People are deleted with
    ``manage.py delete_user``, whose output does not depend on claims.
    """

    def has_delete_permission(self, request, obj=None):
        return False

    def lookup_allowed(self, lookup, value, request):
        """Refuse list filters on reverse relations of User (SECR-01, T-03-19).

        ?claims__isnull=False, ?contributions__isnull=False or ?claims=<pk> would narrow the
        user list to the people who claimed or chipped in. Django answers a refused lookup with
        a 400 for every value. The list_filter fields and the search box are unaffected.
        """
        first = lookup.split(LOOKUP_SEP)[0]
        try:
            field = self.model._meta.get_field(first)
        except FieldDoesNotExist:
            return super().lookup_allowed(lookup, value, request)
        if field.auto_created and not field.concrete:
            return False
        return super().lookup_allowed(lookup, value, request)


admin.site.register(User, GifterUserAdmin)

# Google credentials live only in settings. A SocialApp row on top of settings APPS raises
# MultipleObjectsReturned on every sign-in, and tokens are never stored.
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)


class ReadOnlySocialAccountAdmin(allauth_socialaccount_admin.SocialAccountAdmin):
    """View only: editing would forge an identity, deleting would break someone's sign-in.

    The rows are removed together with their user by ``manage.py delete_user``.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyEmailAddressAdmin(allauth_account_admin.EmailAddressAdmin):
    """View only: editing would forge an identity, deleting would break someone's sign-in.

    The make_verified action is dropped (it forges verification). The rows are removed together
    with their user by ``manage.py delete_user``.
    """

    actions = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.unregister(SocialAccount)
admin.site.register(SocialAccount, ReadOnlySocialAccountAdmin)
admin.site.unregister(EmailAddress)
admin.site.register(EmailAddress, ReadOnlyEmailAddressAdmin)

# Deliberately NOT registered: Wish and any claim or contribution model. The author is staff
# and also a giftee, and must never see who claimed his wishes (SECR-01). For the same reason
# deleting a user is denied in the admin: the deletion summary would list the Claim rows.
