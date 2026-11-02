"""Storico versioni: CHANGELOG.txt è l'unica fonte, README e note di rilascio ne derivano."""

import re
from dataclasses import dataclass, field

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_HEADER_RE = re.compile(r"^==\s*(\S+?)\s*(?:\((\d{4}-\d{2}-\d{2})\))?\s*==$")
README_TITLE = "NOVITÀ"


@dataclass
class Entry:
    version: str
    date: str = ""
    items: list[str] = field(default_factory=list)


def parse_version(s: str) -> tuple[int, int, int] | None:
    m = _VERSION_RE.match(s.strip())
    return tuple(int(g) for g in m.groups()) if m else None


def parse(text: str) -> list[Entry]:
    entries: list[Entry] = []
    seen: set[tuple[int, int, int]] = set()
    current: Entry | None = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("=="):
            m = _HEADER_RE.match(line)
            ver = parse_version(m.group(1)) if m else None
            if ver is None:
                raise ValueError(f"CHANGELOG riga {n}: versione non valida in {line!r}")
            if ver in seen:
                raise ValueError(f"CHANGELOG riga {n}: versione duplicata {m.group(1)!r}")
            seen.add(ver)
            current = Entry(m.group(1).lstrip("v"), m.group(2) or "", [])
            entries.append(current)
        elif line.startswith("- "):
            if current is None:
                raise ValueError(f"CHANGELOG riga {n}: voce prima di qualsiasi versione")
            current.items.append(line[2:].strip())
        else:
            raise ValueError(f"CHANGELOG riga {n}: riga non riconosciuta {line!r}")
    return entries


def between(entries: list[Entry], old: str, new: str) -> list[Entry]:
    lo, hi = parse_version(old), parse_version(new)
    if lo is None or hi is None:
        raise ValueError(f"versione non valida: {old!r} / {new!r}")
    picked = [e for e in entries if lo < parse_version(e.version) <= hi]
    return sorted(picked, key=lambda e: parse_version(e.version), reverse=True)


def format_entries(entries: list[Entry]) -> str:
    blocks = []
    for e in entries:
        head = f"Versione {e.version}" + (f" ({e.date})" if e.date else "")
        blocks.append("\n".join([head, *(f"• {i}" for i in e.items)]))
    return "\n\n".join(blocks)


def readme_section(entries: list[Entry]) -> str:
    return f"{README_TITLE}\n{'-' * len(README_TITLE)}\n{format_entries(entries)}\n"


def replace_readme_section(readme: str, section: str) -> str:
    m = re.search(rf"^{README_TITLE}[ \t]*$", readme, re.MULTILINE)
    if m:
        return readme[: m.start()] + section
    base = readme if readme.endswith("\n") or not readme else readme + "\n"
    return base + "\n" + section


def set_release_date(text: str, version: str, date: str) -> str:
    target = parse_version(version)
    out = []
    for line in text.split("\n"):
        m = re.match(r"^==\s*(\S+?)\s*==$", line.strip())
        if m and parse_version(m.group(1)) == target:
            line = f"== {m.group(1)} ({date}) =="
        out.append(line)
    return "\n".join(out)
