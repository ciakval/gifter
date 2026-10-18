from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User

# Google credentials live only in settings; never add a SocialApp row in the admin
# (a DB row on top of settings APPS raises MultipleObjectsReturned on sign-in).
admin.site.site_header = _("Gifter admin")
admin.site.site_title = _("Gifter admin")

admin.site.register(User, UserAdmin)
