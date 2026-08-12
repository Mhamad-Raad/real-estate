"""Make `activity_log` append-only in the database itself, not just by convention (§11, §12).

The architecture claimed this control in four places and nothing implemented it: the app connects
as the database **owner**, so anyone holding the password in `deploy/.env` could edit or delete the
row recording what they did. An audit trail that the auditee can rewrite is not one.

A trigger rather than the documented restricted role. It needs no second DB user, no compose or
`.env` change at the office, and it binds every connection — including a `psql` session — where a
`REVOKE` only binds the role it names and never the owner. Deviation recorded in §12.

Only UPDATE and DELETE are blocked. INSERT stays open (the app does nothing else), and TRUNCATE is
deliberately left alone: Django flushes test databases with it, and `pg_restore` needs the table
loadable. Neither is reachable through the app.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION activity_log_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'activity_log is append-only: % is not permitted', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER activity_log_no_update
    BEFORE UPDATE ON activity_log
    FOR EACH ROW EXECUTE FUNCTION activity_log_append_only();

CREATE TRIGGER activity_log_no_delete
    BEFORE DELETE ON activity_log
    FOR EACH ROW EXECUTE FUNCTION activity_log_append_only();
"""

REVERSE = """
DROP TRIGGER IF EXISTS activity_log_no_update ON activity_log;
DROP TRIGGER IF EXISTS activity_log_no_delete ON activity_log;
DROP FUNCTION IF EXISTS activity_log_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [("common", "0002_activitylog_app_build")]

    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE)]
