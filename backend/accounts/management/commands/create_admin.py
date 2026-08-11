"""Create the first administrator on a production install (§7, It.8 finding).

`seed_dev` was the only documented way to get a user, and it ships `admin` / `admin12345` as a
**superuser** — dev-only by its own docstring, but nothing filled the gap, so the office's install
would have gone live with a published password.

This is the supported path: it asks for a password (or takes one from the environment for an
unattended install), refuses the weak ones Django knows about, and is **not** idempotent the way
`seed_dev` is — it will not silently do nothing if an admin already exists, because "the command
ran and reported success" is exactly how a default-password account survives.
"""

import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User

# The credentials `seed_dev` ships. They are written in this repository, in its docs and in every
# runbook example, so they are the first thing anyone types — and Django's validators accept
# `admin12345` for any username that does not literally contain it. Blocked by name because a
# published password is not a password, however well-formed it looks.
PUBLISHED_DEV_PASSWORDS = frozenset({"admin12345", "lawyer12345"})


class Command(BaseCommand):
    help = "Create the first administrator account for a production install."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument(
            "--password",
            help=(
                "Prompted for if omitted. Prefer the prompt or ADMIN_PASSWORD: an argument is "
                "visible in the shell history and to any process listing on the machine."
            ),
        )
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--email", default="")

    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("A username is required.")
        if User.all_objects.filter(username=username).exists():
            raise CommandError(
                f"A user named {username!r} already exists. This command never overwrites one — "
                "change the password from the Users screen instead."
            )

        password = options["password"] or os.getenv("ADMIN_PASSWORD")
        if not password:
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Password (again): "):
                raise CommandError("The two passwords did not match.")

        if password in PUBLISHED_DEV_PASSWORDS:
            raise CommandError(
                "Password rejected:\n  That is the development password published in this "
                "project's own repository and documentation."
            )

        # A password containing the account name. Checked here because **Django does not catch
        # it**: `UserAttributeSimilarityValidator` scores `admin` against `admin12345` at 0.667,
        # just under its 0.7 threshold — measured, not assumed.
        if username.lower() in password.lower():
            raise CommandError(
                "Password rejected:\n  It must not contain the username."
            )

        # Then Django's own: length, common passwords, all-numeric, similarity. The unsaved user
        # is passed so the similarity check has something to compare against at all.
        candidate = User(
            username=username,
            first_name=options["first_name"],
            last_name=options["last_name"],
            email=options["email"],
        )
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError("Password rejected:\n  " + "\n  ".join(exc.messages)) from exc

        user = User.objects.create_user(
            username=username,
            password=password,
            role=User.Role.ADMIN,
            first_name=options["first_name"],
            last_name=options["last_name"],
            email=options["email"],
            # Deliberately NOT a Django superuser: `django.contrib.admin` is not installed and
            # `/admin/` is a 404 (It.8 removed it as a second, unaudited write path). Admin here
            # means this app's Admin role, which goes through the audited service layer.
            is_staff=False,
            is_superuser=False,
        )
        self.stdout.write(self.style.SUCCESS(f"created administrator {user.username!r}"))
        self.stdout.write(
            "This account goes through the same audited write path as every other (§11).\n"
            "Create the lawyers from the Users screen."
        )
