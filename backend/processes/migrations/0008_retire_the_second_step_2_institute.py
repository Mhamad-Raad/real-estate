from django.db import migrations

RETIRED_CODE = "INST_S2_B"


def retire_second_step_2_institute(apps, schema_editor):
    """Step 2 has one institute, not two (UC-040).

    `INST_S2_B` never stood for a real body, and `_missing_fixed_institutes` demanded *every* code
    for the step — so Step 2 could never complete on any case. Removing the code from the enum
    leaves its existing rows referencing something the validator no longer accepts, so they are
    **soft-deleted** here: nothing in this system is ever hard-deleted (§11.1), and a retired row
    still has to be visible to an admin looking at the history.
    """
    Entry = apps.get_model("processes", "ProcessInstituteEntry")
    Entry.objects.filter(institute_code=RETIRED_CODE, is_deleted=False).update(is_deleted=True)

    # Step 2's requirement list just got shorter, so every stored step-2 status is stale — a case
    # blocked only on the retired institute is now complete and must say so.
    from processes.models import Process as LiveProcess
    from processes.services import recompute_step

    # `steps__is_deleted=False`: a soft-deleted case has soft-deleted step rows, and
    # `recompute_step` reads them through the active manager, so it would raise rather than skip.
    for process in LiveProcess.all_objects.filter(steps__is_deleted=False).distinct():
        recompute_step(process, 2)


def restore_second_step_2_institute(apps, schema_editor):
    """Reversible: the retired rows come back and step 2 is re-derived under the old rules."""
    Entry = apps.get_model("processes", "ProcessInstituteEntry")
    Entry.objects.filter(institute_code=RETIRED_CODE, is_deleted=True).update(is_deleted=False)

    from processes.models import Process as LiveProcess
    from processes.services import recompute_step

    for process in LiveProcess.all_objects.filter(steps__is_deleted=False).distinct():
        recompute_step(process, 2)


class Migration(migrations.Migration):
    dependencies = [("processes", "0007_real_estate_and_land_id_move_to_step_4")]

    operations = [
        migrations.RunPython(retire_second_step_2_institute, restore_second_step_2_institute)
    ]
