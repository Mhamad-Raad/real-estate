"""Spouse details for the generated letter, and a birth date every client must have (§6.6).

Deliberately **no backfill** of `date_of_birth`: inventing a birth date on a government record is
worse than a failed migration, so a database still holding clients without one stops here with an
explanation instead of being silently filled in.
"""

from django.db import migrations, models


def ensure_every_client_has_a_birth_date(apps, schema_editor):
    Client = apps.get_model("clients", "Client")
    missing = Client.objects.filter(date_of_birth__isnull=True)
    count = missing.count()
    if count:
        pids = ", ".join(missing.values_list("pid", flat=True)[:10])
        raise RuntimeError(
            f"{count} client(s) have no date_of_birth, which is now required. "
            f"Set it for these PIDs before migrating: {pids}"
        )


def noop(apps, schema_editor):
    """Reversing only relaxes the column again — nothing to undo."""


class Migration(migrations.Migration):
    dependencies = [("clients", "0002_client_created_by")]

    operations = [
        migrations.AddField(
            model_name="client",
            name="spouse_date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="spouse_mother_full_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(ensure_every_client_has_a_birth_date, noop),
        migrations.AlterField(
            model_name="client",
            name="date_of_birth",
            field=models.DateField(),
        ),
        migrations.AddConstraint(
            model_name="client",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(marital_status="married")
                    | (
                        ~models.Q(spouse_name="")
                        & models.Q(spouse_date_of_birth__isnull=False)
                        & ~models.Q(spouse_mother_full_name="")
                    )
                ),
                name="ck_client_married_has_spouse_details",
            ),
        ),
    ]
