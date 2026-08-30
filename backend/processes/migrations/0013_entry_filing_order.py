"""Give the institute rows a filing order (UC-110).

State-only — `ordering` adds no SQL — but it is what stops two out-of-city rows swapping places
on screen when one of them is saved. Without it the rows come back in heap order, and an UPDATE
moves the row it touched.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('processes', '0012_drop_dead_step_approval_status'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='processinstituteentry',
            options={'ordering': ('id',)},
        ),
    ]
