from pathlib import Path

import pytest

from deck_inventory import changelog as cl

SAMPLE = """# commento
# altro

== 1.1.0 ==
- Il programma si aggiorna da solo quando esce una versione nuova.
- Il README contiene lo storico delle versioni (questa sezione).

== 1.0.0 (2026-10-31) ==
- Prima versione.
"""

ROOT = Path(__file__).resolve().parents[3]


def test_parse_and_between():
    e = cl.parse(SAMPLE)
    assert [x.version for x in e] == ["1.1.0", "1.0.0"]
    assert e[0].date == "" and e[1].date == "2026-10-31"
    assert len(e[0].items) == 2
    assert [x.version for x in cl.between(e, "1.0.0", "1.1.0")] == ["1.1.0"]
    assert [x.version for x in cl.between(e, "0.9.0", "1.1.0")] == ["1.1.0", "1.0.0"]


def test_parse_version():
    assert cl.parse_version("v1.10.0") == (1, 10, 0)
    assert cl.parse_version("1.2") is None
    assert cl.parse_version("x") is None
    assert cl.parse_version("1.10.0") > cl.parse_version("1.9.9")


def test_duplicate_version_raises():
    with pytest.raises(ValueError, match="duplicata"):
        cl.parse("== 1.0.0 ==\n- a\n\n== v1.0.0 ==\n- b\n")


def test_invalid_version_raises():
    with pytest.raises(ValueError, match="non valida"):
        cl.parse("== abc ==\n- a\n")


def test_format_entries():
    text = cl.format_entries(cl.parse(SAMPLE))
    assert text.startswith("Versione 1.1.0\n• Il programma")
    assert "Versione 1.0.0 (2026-10-31)\n• Prima versione." in text


def test_readme_section_replace():
    section = cl.readme_section(cl.parse(SAMPLE))
    assert section.startswith("NOVITÀ\n------\n")
    base = "TITOLO\n------\nTesto.\n\nALTRO\n-----\nAltro.\n"
    old = base + "\nNOVITÀ\n------\nVersione 0.1.0\n• vecchia\n"
    assert cl.replace_readme_section(old, section) == base + "\n" + section
    assert cl.replace_readme_section(base, section) == base + "\n" + section


def test_set_release_date():
    out = cl.set_release_date(SAMPLE, "1.1.0", "2026-11-02")
    assert "== 1.1.0 (2026-11-02) ==" in out
    assert "== 1.0.0 (2026-10-31) ==" in out


def test_repo_readme_in_sync():
    readme = (ROOT / "README.txt").read_text(encoding="utf-8")
    entries = cl.parse((ROOT / ".app/src/CHANGELOG.txt").read_text(encoding="utf-8"))
    assert cl.replace_readme_section(readme, cl.readme_section(entries)) == readme
