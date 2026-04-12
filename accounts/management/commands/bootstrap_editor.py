from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


User = get_user_model()


class Command(BaseCommand):
    help = "Create or promote a user to editor/superuser for local bootstrap."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument("--display-name", dest="display_name", default="")

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        email = options["email"].strip()
        display_name = options["display_name"].strip() or username

        if not username:
            raise CommandError("Username is required.")

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created superuser: {username}"))
        else:
            user.email = email or user.email
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save(update_fields=["email", "is_staff", "is_superuser", "password"])
            self.stdout.write(self.style.SUCCESS(f"Updated existing user: {username}"))

        user.profile.display_name = display_name
        user.profile.role = user.profile.Role.EDITOR
        user.profile.save(update_fields=["display_name", "role"])

        self.stdout.write(
            self.style.SUCCESS(
                f"User {username} is now an editor and superuser."
            )
        )
