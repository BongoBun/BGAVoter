"""Utility functions for BGA Voter."""

import random
import sys
from functools import wraps
from pathlib import Path


LOGFILE = "bga_voter.log"


def clear_log(func):
    """Clears LOGFILE before running the wrapped function."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        with open(LOGFILE, "w"):
            pass
        return func(*args, **kwargs)

    return wrapper


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


import random
