from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount


class Command(BaseCommand):
    help = (
        "Make one Google-created user staff and superuser, so they can open /gifter-admin/. "
        "Only the single user whose Google account reports EMAIL as verified (and who has a "
        "verified email address row for it) is promoted; the command prints that account's "
        "Google uid. It refuses for an unknown, unverified, non-Google or ambiguous match."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email address of the Google account to promote")

    def handle(self, *args, **options):
        email = options["email"].strip()
        User = get_user_model()

        verified_addresses = EmailAddress.objects.filter(email__iexact=email, verified=True)
        user_ids = set(verified_addresses.values_list("user_id", flat=True))
        accounts = [
            account
            for account in SocialAccount.objects.filter(provider="google", user_id__in=user_ids)
            if str(account.extra_data.get("email", "")).lower() == email.lower()
            and account.extra_data.get("email_verified")
        ]

        if not accounts:
            raise CommandError(
                f"No Google account has the verified email {email!r}. "
                "Sign in with Google first, then run this again."
            )

        if len(accounts) > 1:
            lines = ", ".join(
                f"{account.user.get_username()} (Google uid {account.uid})" for account in accounts
            )
            raise CommandError(
                f"More than one Google account matches {email!r}: {lines}. Nobody was promoted."
            )

        account = accounts[0]
        user = User.objects.get(pk=account.user_id)
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(
            self.style.SUCCESS(
                f"{user.get_username()} ({email}, Google uid {account.uid}) is now staff and superuser."
            )
        )
