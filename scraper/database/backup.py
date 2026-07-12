"""Database file backup helpers."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from scraper.database import Database


def backup_database_file(
    db_path: str | Path,
    backup_dir: str | Path,
    *,
    keep: int = 10,
    prefix: str = "arrests",
    open_db: Optional["Database"] = None,
    verify: bool = True,
) -> Tuple[Path, Optional[str]]:
    from scraper.database import Database

    src = Path(db_path)
    if not src.exists() and open_db is None:
        raise FileNotFoundError(f"Database not found: {src}")

    bdir = Path(backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = bdir / f"{prefix}_{stamp}.db"
    n = 0
    while dest.exists():
        n += 1
        dest = bdir / f"{prefix}_{stamp}_{n}.db"

    owned_db: Optional[Database] = None
    try:
        if open_db is not None and str(open_db.db_path) != ":memory:":
            try:
                open_db.checkpoint()
            except Exception:
                pass
            open_db.backup_to(dest, verify=verify)
        elif src.exists():
            owned_db = Database(str(src))
            try:
                owned_db.checkpoint()
            except Exception:
                pass
            owned_db.backup_to(dest, verify=verify)
        else:
            raise FileNotFoundError(f"Database not found: {src}")
    finally:
        if owned_db is not None:
            try:
                owned_db.close()
            except Exception:
                pass

    if verify and dest.exists():
        try:
            vconn = sqlite3.connect(str(dest))
            try:
                row = vconn.execute("PRAGMA integrity_check").fetchone()
                if not row or str(row[0]).lower() != "ok":
                    try:
                        dest.unlink()
                    except OSError:
                        pass
                    raise RuntimeError(
                        f"Backup verification failed: {row[0] if row else 'unknown'}"
                    )
            finally:
                vconn.close()
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Could not verify backup {dest}: {e}") from e

    pruned_note = None
    if keep and keep > 0:
        pruned = _prune_backups(bdir, prefix=prefix, keep=keep)
        if pruned:
            pruned_note = f"pruned {pruned} old backup(s)"
    return dest, pruned_note


def _prune_backups(backup_dir: Path, *, prefix: str, keep: int) -> int:
    if keep <= 0:
        return 0
    pat = re.compile(
        rf"^{re.escape(prefix)}_\d{{8}}_\d{{6}}(?:_\d+)?(?:_\d+)?\.db$", re.I
    )
    files = sorted(
        [p for p in backup_dir.iterdir() if p.is_file() and pat.match(p.name)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed = 0
    for old in files[keep:]:
        try:
            old.unlink()
            removed += 1
        except OSError:
            pass
    return removed
