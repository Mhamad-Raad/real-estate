from django.contrib.postgres.search import TrigramSimilarity
from django.db import migrations

# Kept local to the migration: this is the threshold as it stood when the flags were re-split,
# and it must not drift if clients.selectors is retuned later.
NAME_SIMILARITY_THRESHOLD = 0.5


def resplit(apps, schema_editor):
    """`duplicate_flagged` used to mean 'PID OR similar mother name'; it now means PID only.

    Re-derive both flags for every already-flagged process, otherwise cases flagged for nothing
    worse than a sibling's name stay blocked at Step 1 forever with no way to tell them apart.
    """
    Process = apps.get_model("processes", "Process")
    Client = apps.get_model("clients", "Client")

    affected = []
    for process in Process.objects.filter(duplicate_flagged=True).select_related("client"):
        client = process.client
        others = Client.objects.filter(is_deleted=False).exclude(pk=client.pk)
        pid_hit = bool(client.pid) and others.filter(pid=client.pid).exists()
        name_hit = bool(client.mother_full_name) and (
            others.filter(mother_full_name__trigram_similar=client.mother_full_name)
            .exclude(pid=client.pid)
            .annotate(similarity=TrigramSimilarity("mother_full_name", client.mother_full_name))
            .filter(similarity__gte=NAME_SIMILARITY_THRESHOLD)
            .exists()
        )
        Process.objects.filter(pk=process.pk).update(
            duplicate_flagged=pid_hit, similar_name_flagged=name_hit
        )
        if not pid_hit:
            affected.append(process.pk)

    if affected:
        # Step 1's stored status was computed while the flag was blocking; unblocking it here
        # would otherwise leave the badge reading "incomplete" until the next unrelated save.
        # The real model and service are used deliberately — the status rules live there, and a
        # historical model carries none of them. Safe because on a fresh DB this loop never runs.
        # `all_objects`, not `objects`: the default manager is ActiveManager and hides
        # soft-deleted rows, so a flagged case that was later soft-deleted would raise
        # DoesNotExist here — the historical queryset above can see it, this one could not.
        from processes.models import Process as LiveProcess
        from processes.services import recompute_step

        for process in LiveProcess.all_objects.filter(pk__in=affected):
            recompute_step(process, 1)


def noop_reverse(apps, schema_editor):
    """Irreversible in substance: the original flag conflated two causes that cannot be recovered."""


class Migration(migrations.Migration):
    dependencies = [
        ("processes", "0005_process_similar_name_flagged"),
        ("clients", "0003_spouse_details_and_required_birth_date"),
    ]

    operations = [migrations.RunPython(resplit, noop_reverse)]
