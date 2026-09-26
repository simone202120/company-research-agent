"""SQLite checkpointer: one file on disk holds every research thread, so runs survive restarts."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


@contextmanager
def sqlite_checkpointer(path: str) -> Iterator[SqliteSaver]:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # Shared across API request threads and graph worker threads; SqliteSaver serializes access.
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        yield SqliteSaver(conn)
    finally:
        conn.close()
