from django.conf import settings
from django.db import migrations
from django.utils import timezone


def verify_existing_accounts(apps, schema_editor):
    """Accounts created before verification existed shouldn't be locked out."""
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Profile = apps.get_model("therapybot", "Profile")
    now = timezone.now()
    for user in User.objects.all():
        profile, _ = Profile.objects.get_or_create(user=user)
        if profile.email_verified_at is None:
            profile.email_verified_at = now
            profile.save(update_fields=["email_verified_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("therapybot", "0003_plans_providers_email_verification"),
    ]

    operations = [
        migrations.RunPython(verify_existing_accounts, migrations.RunPython.noop),
    ]
