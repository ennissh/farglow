import pytest

from farglow import db, migrate

pytestmark = pytest.mark.db


def test_rerun_is_noop(pg_settings):
    assert migrate.run(pg_settings) == 0


def test_edited_migration_is_refused(pg_settings, tmp_path):
    for m in migrate.discover():
        (tmp_path / m.path.name).write_text(m.sql + "\n-- edited\n")
    with pytest.raises(RuntimeError, match="changed after it was applied"):
        migrate.run(pg_settings, tmp_path)


def test_unknown_applied_migration_is_refused(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        conn.execute("INSERT INTO schema_migrations (version, name, checksum) VALUES (9999, 'future', 'x')")
        with pytest.raises(RuntimeError, match="does not know"):
            migrate.pending(conn, migrate.discover())
