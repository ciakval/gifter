from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Delete one user and everything Gifter stores about them, for data requests from "
        "/privacy/. USERNAME is the username shown in the admin user list. It is a dry run "
        "unless --yes is given. The output never says what was deleted with the user, because "
        "the operator is also a giftee and must not learn who claimed or chipped in on a wish. "
        "The command refuses to delete the last active staff account (a command line has no "
        "signed-in user, so this stands in for a self-deletion check and keeps the admin "
        "reachable)."
    )

    def add_arguments(self, parser):
        parser.add_argument("username", help="Exact username of the account to delete")
        parser.add_argument(
            "--yes", action="store_true", help="Really delete; without it only show the account"
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"No user has the username {username!r}. Nobody was deleted.")

        if user.is_staff:
            others = User.objects.filter(is_staff=True, is_active=True).exclude(pk=user.pk)
            if not others.exists():
                raise CommandError(
                    f"{username!r} is the only active staff account. Promote someone else first "
                    "with promote_staff, or the admin would be out of reach. Nobody was deleted."
                )

        description = f"{user.get_username()} ({user.display_name}, {user.email or 'no email'})"
        if not options["yes"]:
            self.stdout.write(f"{description}. Nothing was deleted; run again with --yes to delete.")
            return

        # delete() returns per-model counts, claims included; they are discarded on purpose.
        user.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {description} and everything Gifter stored about them.")
        )
