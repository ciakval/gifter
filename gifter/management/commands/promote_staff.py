from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Make an existing Google-created user staff and superuser, so they can open "
        "/gifter-admin/. The user must have signed in with Google at least once."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email address of the Google account to promote")

    def handle(self, *args, **options):
        email = options["email"]
        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise CommandError(
                f"No user with email {email!r}. Sign in with Google first, then run this again."
            )
        except User.MultipleObjectsReturned:
            names = ", ".join(User.objects.filter(email__iexact=email).values_list("username", flat=True))
            raise CommandError(f"More than one user has email {email!r}: {names}")
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(self.style.SUCCESS(f"{user.username} ({user.email}) is now staff and superuser."))
