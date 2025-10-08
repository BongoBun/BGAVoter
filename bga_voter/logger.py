"""Async logging utilities and log constants for BGA Voter."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional

try:
    import aiofiles  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    aiofiles = None  # type: ignore

LOGFILE = "bga_voter.log"


class AsyncLogger:
    """Lightweight async file logger with size-based rotation.

    Parameters:
        path: log file path
        auto_timestamp: prepend timestamps automatically
        max_bytes: rotate when file would exceed this size (None disables)
        backup_count: number of rotated backups to keep
    """

    def __init__(
        self,
        path: str,
        *,
        auto_timestamp: bool = True,
        max_bytes: int | None = None,
        backup_count: int = 3,
    ) -> None:
        self.path = path
        self.auto_timestamp = auto_timestamp
        self.max_bytes = max_bytes if (max_bytes and max_bytes > 0) else None
        self.backup_count = max(0, backup_count)
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._stopping = False

    # Lifecycle
    async def start(self) -> None:
        if self._task is None:
            if aiofiles is None:
                await self._queue.put(
                    "[WARN] aiofiles not installed; logging will be synchronous."
                )
            self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task and not self._stopping:
            self._stopping = True
            await self._queue.put(None)
            await self._task
            self._task = None

    # Public API
    async def log(self, message: str, *, timestamp: Optional[bool] = None) -> None:
        if timestamp is None:
            timestamp = self.auto_timestamp
        prefix = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] " if timestamp else ""
        )
        await self._queue.put(prefix + message + "\n")

    # Internals
    def _maybe_rotate(self, incoming_len: int) -> None:
        if self.max_bytes is None:
            return
        try:
            path = Path(self.path)
            if path.exists() and path.stat().st_size + incoming_len >= self.max_bytes:
                if self.backup_count > 0:
                    oldest = path.with_name(path.name + f".{self.backup_count}")
                    if oldest.exists():
                        oldest.unlink(missing_ok=True)
                    for idx in range(self.backup_count - 1, 0, -1):
                        src = path.with_name(path.name + f".{idx}")
                        if src.exists():
                            src.replace(path.with_name(path.name + f".{idx+1}"))
                    if path.exists():
                        path.replace(path.with_name(path.name + ".1"))
        except Exception as e:  # pragma: no cover
            sys.stderr.write(f"\n[AsyncLogger ROTATE ERROR] {e}\n")

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                self._queue.task_done()
                break
            try:
                self._maybe_rotate(len(item.encode("utf-8")))
                if aiofiles is not None:
                    async with aiofiles.open(self.path, "a", encoding="utf-8") as f:
                        await f.write(item)
                else:
                    with open(self.path, "a", encoding="utf-8") as f:
                        f.write(item)
            except Exception as e:  # pragma: no cover
                sys.stderr.write(f"\n[AsyncLogger ERROR] {e}\n")
            finally:
                self._queue.task_done()
