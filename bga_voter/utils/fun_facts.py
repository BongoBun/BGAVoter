"""Fun facts utilities."""

from pathlib import Path
import random


def load_fun_facts(filename: str = "ark_nova_fun_facts.txt") -> list[str]:
    data_file = Path(__file__).resolve().parent.parent.parent / "data" / filename
    with open(data_file, "r", encoding="utf-8") as f:
        facts = [line.strip() for line in f if line.strip()]
    return [f"{i+1}. {fact}" for i, fact in enumerate(facts)]


def random_fun_fact(filename: str = "ark_nova_fun_facts.txt") -> None:
    facts = load_fun_facts(filename)
    print(f"\nFun Fact!\n{random.choice(facts)}\n")
