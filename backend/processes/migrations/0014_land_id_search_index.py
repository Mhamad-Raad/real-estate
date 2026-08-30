"""Let the search box find a case by its land number (UC-113).

Trigram GIN, like `ix_process_code_trgm`: the box matches a *fragment*, and a btree cannot serve
`ILIKE '%…%'`. `land_id` had no index at all — it is not unique, because one plot can be split and
allocated more than once, which the office says is expected.
"""

import django.contrib.postgres.indexes
from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
        ('clients', '0005_client_ix_client_pid_trgm'),
        ('processes', '0013_entry_filing_order'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name='process',
            index=django.contrib.postgres.indexes.GinIndex(fields=['land_id'], name='ix_process_land_trgm', opclasses=['gin_trgm_ops']),
        ),
    ]
