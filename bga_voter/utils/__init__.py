"""Utility package: progress display & fun facts."""

from .progress import progress_bar
from .fun_facts import load_fun_facts, random_fun_fact

__all__ = ["progress_bar", "load_fun_facts", "random_fun_fact"]
