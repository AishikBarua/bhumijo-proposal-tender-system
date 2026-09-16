"""
Every address, port, path and secret the system uses, read once from the
environment (or a .env file sitting next to the project).

Nothing else in the codebase is allowed to hardcode a port, a folder or a
host name. If you find yourself typing 8585 anywhere else, it belongs here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader — no dependency, no surprises."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(PROJECT_ROOT / ".env")


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default).strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- identity -------------------------------------------------------
    app_name: str = "Bhumijo Proposal & Grant Tracker"
    version: str = "2.0.0"
    environment: str = field(default_factory=lambda: _str("BHUMIJO_ENV", "development"))

    # --- network --------------------------------------------------------
    host: str = field(default_factory=lambda: _str("BHUMIJO_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _int("BHUMIJO_PORT", 8787))

    # Explicit list, never "*". Empty list means same-origin only.
    cors_origins: list[str] = field(
        default_factory=lambda: _list("BHUMIJO_CORS_ORIGINS", "")
    )

    # --- storage --------------------------------------------------------
    data_dir: Path = field(
        default_factory=lambda: Path(_str("BHUMIJO_DATA_DIR", str(PROJECT_ROOT / "data")))
    )
    backup_dir: Path = field(
        default_factory=lambda: Path(
            _str("BHUMIJO_BACKUP_DIR", str(PROJECT_ROOT / "data" / "backups"))
        )
    )
    legacy_data_dir: Path = field(
        default_factory=lambda: Path(
            _str("BHUMIJO_LEGACY_DATA_DIR", str(PROJECT_ROOT.parent / "proposal_backups"))
        )
    )

    # --- frontend -------------------------------------------------------
    frontend_dir: Path = field(
        default_factory=lambda: Path(
            _str("BHUMIJO_FRONTEND_DIR", str(PROJECT_ROOT / "frontend"))
        )
    )

    # --- security -------------------------------------------------------
    # Shared token kept only so today's screens keep working unchanged.
    # It is replaced by real accounts when the login phase lands.
    # These follow data_dir unless explicitly overridden — pointing the data
    # directory somewhere else must take the token and secret with it.
    token_file_override: str = field(default_factory=lambda: _str("BHUMIJO_TOKEN_FILE", ""))
    secret_file_override: str = field(default_factory=lambda: _str("BHUMIJO_SECRET_FILE", ""))
    session_hours: int = field(default_factory=lambda: _int("BHUMIJO_SESSION_HOURS", 12))

    # Devices on the office network are let in without the access token, so
    # nobody has to type anything to open the tracker.
    #
    # What this means in plain terms: anyone who can reach this PC on your
    # local network can read and edit every record, with no password. That
    # is a deliberate choice for a tool on a private office LAN, and it is
    # what the old 8585 server effectively did anyway (its token file could
    # be downloaded by anyone on the network).
    #
    # It does NOT open anything to the internet: only private addresses
    # (192.168.x, 10.x, 172.16-31.x and this PC itself) are trusted. A
    # request from any public address still needs the token.
    #
    # Set BHUMIJO_TRUST_LOCAL_NETWORK=false to require the token again.
    # When real logins are switched on, this setting goes away.
    trust_local_network: bool = field(
        default_factory=lambda: _bool("BHUMIJO_TRUST_LOCAL_NETWORK", True)
    )
    # Deletes were restricted to the server PC. Kept until roles replace it.
    restrict_delete_to_localhost: bool = field(
        default_factory=lambda: _bool("BHUMIJO_DELETE_LOCALHOST_ONLY", True)
    )

    # --- logging --------------------------------------------------------
    log_dir: Path = field(
        default_factory=lambda: Path(_str("BHUMIJO_LOG_DIR", str(PROJECT_ROOT / "data" / "logs")))
    )
    log_level: str = field(default_factory=lambda: _str("BHUMIJO_LOG_LEVEL", "INFO"))

    @property
    def database_path(self) -> Path:
        return self.data_dir / "bhumijo.db"

    @property
    def token_file(self) -> Path:
        return Path(self.token_file_override) if self.token_file_override \
            else self.data_dir / "access_token.txt"

    @property
    def session_secret_file(self) -> Path:
        return Path(self.secret_file_override) if self.secret_file_override \
            else self.data_dir / "session_secret.txt"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.backup_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
