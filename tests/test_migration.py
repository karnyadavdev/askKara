from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from kara.config import get_settings
from kara.db import reset_db_state

ROOT = Path(__file__).resolve().parent.parent


def test_migration_upgrade_and_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    reset_db_state()

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    upgraded = inspect(engine).get_table_names()
    assert "users" in upgraded
    assert "queries" in upgraded

    command.downgrade(cfg, "base")
    assert "users" not in inspect(engine).get_table_names()

    get_settings.cache_clear()
    reset_db_state()
