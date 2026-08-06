"""Drop `ProcessStep.approval_status` — dead since approval moved to the institute entry.

§0 has listed it as "dead field … cleanup (drop the field in a later migration)" since It.2.5. It
was never in `EDITABLE_STEP_FIELDS`, so nothing could write it, and nothing read it: the only
approval any screen shows is `ProcessInstituteEntry.approval_status`, which stays. It was still
being serialized into every step payload, which is the part that invites a future reader to trust
it. Column dropped in It.8's dead-code sweep; no data is lost that anything ever set.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('processes', '0011_code_search_index'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='processstep',
            name='approval_status',
        ),
    ]
