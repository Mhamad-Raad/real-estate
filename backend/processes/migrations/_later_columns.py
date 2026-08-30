"""Columns added to `Process` by migrations later than the data migrations that read it.

Two data migrations (0007, 0008) deliberately use the **live** `Process` model, because the status
rules they re-derive live in `services` and a historical model carries none of them. The live class
declares every field the model will ever have — including columns that do not exist yet when those
migrations run on a fresh database — so both `.defer()` them.

Kept here rather than copied into each: the list was duplicated, so adding a field to one copy and
not the other leaves a fresh install unable to migrate at all. Deferring a column that *does* already exist is harmless, so one always-growing list is correct for
every migration that reads it.

**Add every new `Process` field here.**
"""

LATER_COLUMNS = ("unique_code", "completed_by")
