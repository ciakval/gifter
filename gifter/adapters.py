"""
allauth adapters for Google-only sign-in (Phase 1, plan 01-07).

web/urls.py routes only the allauth pages Google sign-in needs. These two adapters keep the
flows that would otherwise reverse into a removed route (inactive account, account connect)
from ending in a NoReverseMatch 500.
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.base import AuthProcess


class AccountAdapter(DefaultAccountAdapter):
    def respond_user_inactive(self, request, user):
        """An inactive account ends on the landing page with a plain message.

        The default redirects to the account_inactive page, which is deliberately not routed.
        """
        messages.error(
            request,
            _(
                "This Gifter account is switched off. "
                "If you think this is a mistake, ask the person who invited you."
            ),
        )
        return redirect("landing")


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Refuse the connect process: a second Google identity is never attached to an account.

        A signed-in user can POST process=connect to the Google login view; without this the
        callback would add a SocialAccount to the current user.
        """
        super().pre_social_login(request, sociallogin)
        if sociallogin.state.get("process") == AuthProcess.CONNECT:
            raise ImmediateHttpResponse(redirect("home"))

    def get_connect_redirect_url(self, request, socialaccount):
        """Belt and braces: the default reverses the connections page, which is not routed."""
        return reverse("home")
