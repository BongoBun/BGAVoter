"""Utility functions for BGA Voter."""

import random
import sys
from pathlib import Path
import asyncio
from datetime import datetime
import aiofiles


LOGFILE = "bga_voter.log"


def progress_bar(iteration: int, total: int, length: int = 40) -> None:
    """
    Display a progress bar in the terminal.

    Args:
        iteration: Current iteration number
        total: Total number of iterations
        length: Length of the progress bar in characters
    """
    percent = iteration / total
    filled_length = int(length * percent)
    bar = "█" * filled_length + "-" * (length - filled_length)
    sys.stdout.write(f"\rProgress: |{bar}| {percent*100:6.2f}%")
    sys.stdout.flush()
    if iteration == total:
        print()


def load_fun_facts(filename: str = "ark_nova_fun_facts.txt") -> list[str]:
    """
    Load fun facts.
    Returns a numbered list of facts.
    """
    # Path relative to project root (two levels up from utils.py)
    data_file = Path(__file__).resolve().parent.parent / "data" / filename

    with open(data_file, "r", encoding="utf-8") as f:
        fun_facts_raw = [line.strip() for line in f if line.strip()]

    # Automatically number the facts
    return [f"{i+1}. {fact}" for i, fact in enumerate(fun_facts_raw)]


def random_fun_fact(filename: str = "ark_nova_fun_facts.txt") -> None:
    """
    Print a random fun fact.
    """
    fun_fact = load_fun_facts(filename)
    print(f"\nFun Fact!\n{random.choice(fun_fact)}\n")


# --- Async Logging -------------------------------------------------------------


class AsyncLogger:
    """Lightweight async file logger using an internal queue with optional rotation.

    Features:
      - Non-blocking logging via queue + background task
      - Automatic timestamp prefixing (configurable)
      - Size-based rotation (``max_bytes`` + ``backup_count``)
      - Fallback to synchronous writes if ``aiofiles`` not installed

    Rotation strategy:
      When the active log file size >= ``max_bytes`` before a write:
        log    -> log.1 -> log.2 -> ... -> log.<backup_count>
        Oldest (log.<backup_count>) is deleted, names shift up, current file becomes log.1
        A fresh file is created for subsequent writes.
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

    async def start(self) -> None:
        if self._task is None:
            if aiofiles is None:
                # Defer error until first log attempt to allow user to install deps.
                await self._queue.put(
                    "[WARN] aiofiles not installed; logging will be synchronous."
                )
            self._task = asyncio.create_task(self._worker())

    async def log(self, message: str, *, timestamp: bool | None = None) -> None:
        if timestamp is None:
            timestamp = self.auto_timestamp
        prefix = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] " if timestamp else ""
        )
        await self._queue.put(prefix + message + "\n")

    async def stop(self) -> None:
        if self._task and not self._stopping:
            self._stopping = True
            await self._queue.put(None)
            await self._task
            self._task = None

    def _maybe_rotate(self, incoming_len: int) -> None:
        """Rotate log files if size threshold would be exceeded by incoming write.

        Called inside worker (single-threaded context), so no extra locking needed.
        """
        if self.max_bytes is None:
            return
        try:
            log_path = Path(self.path)
            if (
                log_path.exists()
                and log_path.stat().st_size + incoming_len >= self.max_bytes
            ):
                # Perform rotation chain
                if self.backup_count > 0:
                    # Delete oldest
                    oldest = log_path.with_name(log_path.name + f".{self.backup_count}")
                    if oldest.exists():
                        oldest.unlink(missing_ok=True)
                    # Shift others
                    for idx in range(self.backup_count - 1, 0, -1):
                        src = log_path.with_name(log_path.name + f".{idx}")
                        if src.exists():
                            dst = log_path.with_name(log_path.name + f".{idx+1}")
                            src.replace(dst)
                    # Rotate current to .1
                    if log_path.exists():
                        log_path.replace(log_path.with_name(log_path.name + ".1"))
                # Fresh file will be created automatically on write
        except Exception as e:  # Rotation errors should not crash logger
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
                else:  # Fallback synchronous write
                    with open(self.path, "a", encoding="utf-8") as f:
                        f.write(item)
            except Exception as e:  # Log internal failures to stderr
                sys.stderr.write(f"\n[AsyncLogger ERROR] {e}\n")
            finally:
                self._queue.task_done()
