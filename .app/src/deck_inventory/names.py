import re


def normalize(name: str) -> str:
    name = name.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", name).strip().lower()


def is_rune(name: str) -> bool:
    return normalize(name).endswith(" rune")
