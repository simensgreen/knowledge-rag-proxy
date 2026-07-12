"""Optional backup to remote storage — stub."""

from __future__ import annotations


def run_backup() -> None:
    """Copy chroma_db and metadata to remote storage (e.g. rclone).

    TODO Phase 3: implement rclone subprocess from scripts/backup.sh config.
    """
    pass
