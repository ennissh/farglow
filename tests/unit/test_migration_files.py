from farglow import migrate


def test_migrations_are_numbered_and_unique():
    found = migrate.discover()
    assert found, "no migrations"
    assert [m.version for m in found] == sorted({m.version for m in found})
    assert found[0].version == 1
