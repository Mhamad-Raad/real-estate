"""Idempotent dev seed: one admin + one lawyer with known credentials (dev only)."""

from django.core.management.base import BaseCommand

from accounts.models import User

DEV_USERS = [
    {"username": "admin", "password": "admin12345", "role": User.Role.ADMIN,
     "is_staff": True, "is_superuser": True},
    {"username": "lawyer", "password": "lawyer12345", "role": User.Role.LAWYER},
]


class Command(BaseCommand):
    help = "Create dev admin/lawyer accounts if they do not exist."

    def handle(self, *args, **options):
        for spec in DEV_USERS:
            username = spec["username"]
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"= {username} already exists")
                continue
            user = User(
                username=username,
                role=spec["role"],
                is_staff=spec.get("is_staff", False),
                is_superuser=spec.get("is_superuser", False),
            )
            user.set_password(spec["password"])
            user.save()
            self.stdout.write(self.style.SUCCESS(f"+ created {username} ({spec['role']})"))
