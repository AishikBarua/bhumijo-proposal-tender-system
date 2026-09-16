"""Engine/session setup. Schema changes are owned by Alembic (see alembic/ and
docs/MIGRATIONS.md) - this module no longer creates or alters tables itself. init_db()
only checks the database is at Alembic's latest revision and warns loudly if not,
rather than silently running against a stale schema.

(Earlier versions of this file ran Base.metadata.create_all() plus a hand-rolled list
of ALTER TABLE statements for columns added after the first release. That covered
missing tables but not schema drift on existing ones, and every new column needed a
manual entry here - exactly the problem migrations solve. Superseded by Alembic.)
"""
import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.models import Base  # noqa: F401 - kept as the single source of truth for alembic/env.py

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger("tender_agent")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _check_migrations_current():
    # Alembic's own loggers are chatty at INFO level (plugin setup, dialect detection -
    # some of it fires as a side effect of the imports below) - fine for the `alembic`
    # CLI, just noise in this app's own startup log. The one line that matters (the
    # warning below, if the DB is behind) still goes through. Set BEFORE importing:
    # some of this chatter happens at import time, not at call time.
    logging.getLogger("alembic").setLevel(logging.WARNING)

    # Imported lazily (not at module level) so the log-level suppression above is
    # guaranteed to be in effect before anything alembic logs, regardless of what else
    # has or hasn't called logging.basicConfig by the time this module is first
    # imported elsewhere.
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    alembic_cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()

    if current_rev != head_rev:
        logger.warning(
            "Database is NOT at the latest migration (current=%s, head=%s). Run "
            "'alembic upgrade head' before continuing - see docs/MIGRATIONS.md. Code "
            "that touches a column added since this revision will fail with "
            "'no such column' until this is fixed.",
            current_rev, head_rev,
        )


def init_db():
    _check_migrations_current()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
