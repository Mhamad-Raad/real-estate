from django.db import migrations

# Columns added by LATER migrations. This file deliberately uses the LIVE model (the status rules
# live in services and a historical model carries none of them), but the live class declares every
# field the model will ever have — including ones whose column does not exist yet when this runs on
# a fresh database. **Add every new `Process` field here.**
LATER_COLUMNS = ("unique_code", "completed_by")


def move_requirements_to_step_4(apps, schema_editor):
    """The real-estate paper and `land_id` are Step-4 requirements now, not Step-1 (UC-037/UC-041).

    Two things have to follow the rule change or the existing cases contradict it:
    1. Real-estate documents already filed under step 1 are re-pointed to step 4 — otherwise Step 4
       reports the paper missing while the file sits on the case, filed under the old step.
    2. **Every** process has its steps 1 and 4 re-derived. Unlike a normal data migration this is
       not limited to "affected rows": the requirement list itself changed, so every stored status
       computed under the old rules is now stale — Step 1 is blocked on a `land_id` it no longer
       needs, and Step 4 is green without a paper it now does.
    """
    Document = apps.get_model("documents", "Document")
    # The historical model's plain manager sees soft-deleted rows too, which is what we want: a
    # deleted real-estate doc must still be filed under the right step if it is ever restored.
    Document.objects.filter(document_type="RealEstate", step_number=1).update(step_number=4)

    # The real models and service on purpose — the status rules live there and a historical model
    # carries none of them. `all_objects` because the default manager hides soft-deleted cases.
    from processes.models import Process as LiveProcess
    from processes.services import recompute_step

    # Only cases whose steps are still live. A soft-deleted case has its `ProcessStep` rows
    # soft-deleted with it, and `recompute_step` reads them through the active manager — it would
    # raise `DoesNotExist` rather than skip them. Restoring such a case restores its steps, and the
    # first save after that re-derives the status anyway.
    # `steps__is_deleted=False`, not `steps__isnull=False`: the reverse relation is a plain join
    # that does not honour the active manager, so `isnull` would still match the deleted rows.
    # `.defer(*LATER_COLUMNS)`: this migration deliberately uses the LIVE model (the status rules
    # live there and a historical model carries none of them), but the live class also declares
    # every column added by LATER migrations — which do not exist in the database yet when this
    # runs on a fresh install. Deferring keeps them out of the SELECT.
    for process in LiveProcess.all_objects.defer(*LATER_COLUMNS).filter(steps__is_deleted=False).distinct():
        recompute_step(process, 1)
        recompute_step(process, 4)


def move_requirements_back(apps, schema_editor):
    """Reversible: the documents go back to step 1 and both steps are re-derived under the old rules."""
    Document = apps.get_model("documents", "Document")
    Document.objects.filter(document_type="RealEstate", step_number=4).update(step_number=1)

    from processes.models import Process as LiveProcess
    from processes.services import recompute_step

    # Only cases whose steps are still live. A soft-deleted case has its `ProcessStep` rows
    # soft-deleted with it, and `recompute_step` reads them through the active manager — it would
    # raise `DoesNotExist` rather than skip them. Restoring such a case restores its steps, and the
    # first save after that re-derives the status anyway.
    # `steps__is_deleted=False`, not `steps__isnull=False`: the reverse relation is a plain join
    # that does not honour the active manager, so `isnull` would still match the deleted rows.
    # `.defer(*LATER_COLUMNS)`: this migration deliberately uses the LIVE model (the status rules
    # live there and a historical model carries none of them), but the live class also declares
    # every column added by LATER migrations — which do not exist in the database yet when this
    # runs on a fresh install. Deferring keeps them out of the SELECT.
    for process in LiveProcess.all_objects.defer(*LATER_COLUMNS).filter(steps__is_deleted=False).distinct():
        recompute_step(process, 1)
        recompute_step(process, 4)


class Migration(migrations.Migration):
    dependencies = [
        ("processes", "0006_resplit_duplicate_flags"),
        ("documents", "0004_refile_under_pid_folders"),
    ]

    operations = [migrations.RunPython(move_requirements_to_step_4, move_requirements_back)]
