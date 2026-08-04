from django.conf import settings
from django.db import migrations, models


def backfill_codes(apps, schema_editor):
    """Give every existing case its code before the unique constraint goes on (§3.8, UC-056).

    Ordered by **pk**, so the numbering follows the order cases were actually opened: the office's
    first category-A case becomes `A1`, the next `A2`, and so on. Soft-deleted cases are included
    and consume a number — a code is never reissued, so the sequence must account for them.

    Deliberately does not use `services.allocate_unique_code`: that reads the live model, and a
    migration must work against the historical one. The rule it implements is the same.
    """
    Process = apps.get_model("processes", "Process")
    counters: dict[str, int] = {}
    for process in Process.objects.select_related("category").order_by("pk"):
        if not process.category_id or process.unique_code:
            continue
        prefix = process.category.code
        counters[prefix] = counters.get(prefix, 0) + 1
        process.unique_code = f"{prefix}{counters[prefix]}"
        process.save(update_fields=["unique_code"])


def clear_codes(apps, schema_editor):
    apps.get_model("processes", "Process").objects.update(unique_code="")


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("clients", "0005_client_ix_client_pid_trgm"),
        ("processes", "0008_retire_the_second_step_2_institute"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="process",
            name="unique_code",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        # Between the column and the constraint: existing rows all hold "" until this runs, and
        # the constraint would reject them the moment more than one non-blank duplicate appeared.
        migrations.RunPython(backfill_codes, clear_codes),
        migrations.AddConstraint(
            model_name="process",
            constraint=models.UniqueConstraint(
                condition=models.Q(("unique_code", ""), _negated=True),
                fields=("unique_code",),
                name="ix_process_unique_code",
            ),
        ),
    ]
