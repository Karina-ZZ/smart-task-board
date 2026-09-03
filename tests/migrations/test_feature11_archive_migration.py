"""Feature 11 migration contract: new archives do not require snapshots."""
import importlib.util
from pathlib import Path


PATH = Path("alembic/versions/f9a1b2c3d4e5_feature11_archive_snapshot_nullable.py")


class Recorder:
    def __init__(self) -> None:
        self.alters = []
        self.statements = []

    def alter_column(self, table_name, column_name, **kwargs):
        self.alters.append((table_name, column_name, kwargs))

    def execute(self, statement):
        self.statements.append(str(statement))


def _module():
    spec = importlib.util.spec_from_file_location("feature11_archive_migration", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feature11_archive_snapshot_becomes_nullable_without_rewriting_history() -> None:
    module = _module()
    recorder = Recorder()
    module.op = recorder

    assert module.revision == "a9c4e7f1b2d3"
    assert module.down_revision == "f8a1b2c3d4e5"
    module.upgrade()

    assert len(recorder.alters) == 1
    table, column, kwargs = recorder.alters[0]
    assert (table, column) == ("task_archives", "archive_snapshot")
    assert kwargs["nullable"] is True
    assert recorder.statements == []
