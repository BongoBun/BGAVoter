"""Progress bar utility."""

import sys


def progress_bar(iteration: int, total: int, length: int = 40) -> None:
    if total <= 0:
        return
    percent = iteration / total
    filled = int(length * percent)
    bar = "█" * filled + "-" * (length - filled)
    sys.stdout.write(f"\rProgress: |{bar}| {percent*100:6.2f}%")
    sys.stdout.flush()
    if iteration >= total:
        print()
