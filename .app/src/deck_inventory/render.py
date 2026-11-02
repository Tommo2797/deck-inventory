"""Pagina HTML dei risultati: un unico file autosufficiente, CSS inline, niente JS."""

from datetime import datetime
from html import escape

from deck_inventory.inventory import Row, Section

_CSS = """
:root {
  --bg: #fafaf7; --fg: #1d1d1b; --muted: #6b6b66; --line: #e2e1da;
  --card: #ffffff; --accent: #2f5fb3; --ok: #2e7d32; --bad: #b3261e;
  --warn-bg: #fff6e0; --warn-line: #e6c36a; --head: #f1f0ea;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161615; --fg: #e8e6df; --muted: #9a988f; --line: #33322e;
    --card: #1f1f1d; --accent: #8fb1ee; --ok: #7cc47f; --bad: #f08a80;
    --warn-bg: #2f2814; --warn-line: #7a6326; --head: #262623;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
main { max-width: 900px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 1.8rem; margin: 0 0 4px; }
h2 { font-size: 1.35rem; margin: 40px 0 8px; padding-bottom: 4px; border-bottom: 2px solid var(--line); }
h3 { font-size: 1.1rem; margin: 28px 0 4px; }
a { color: var(--accent); overflow-wrap: anywhere; }
.meta { color: var(--muted); margin: 0; }
.summary { margin: 4px 0 12px; }
.warnings {
  background: var(--warn-bg); border: 1px solid var(--warn-line); border-radius: 8px;
  padding: 10px 16px; margin: 20px 0 0;
}
.warnings strong { display: block; margin-bottom: 4px; }
.warnings ul { margin: 0; padding-left: 20px; }
.scroll { overflow-x: auto; background: var(--card); border: 1px solid var(--line); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: 5px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
td.name { white-space: normal; }
th { background: var(--head); font-weight: 600; font-size: 0.9rem; }
tr:last-child td { border-bottom: none; }
.num { text-align: right; }
.ok { color: var(--ok); }
.missing { color: var(--bad); font-weight: 600; }
ul.shopping { padding-left: 20px; columns: 2 260px; }
footer { margin-top: 48px; color: var(--muted); font-size: 0.85rem; }
"""


def page_filename(dt: datetime) -> str:
    return f"Inventory {dt:%Y-%m-%d %H.%M}.html"


def _summary(s: Section) -> str:
    return (
        f'<p class="summary">Servono {s.need} copie, ne hai {s.have}, ne mancano {s.missing} '
        f"({s.incomplete} carte diverse incomplete).</p>"
    )


def _missing_cell(r: Row) -> str:
    if r.missing == 0:
        return '<td class="num ok">✓</td>'
    return f'<td class="num missing">{r.missing}</td>'


def _table(rows: list[Row], with_decks: bool) -> str:
    head = ['<th class="num">Servono/Hai</th>', "<th>Carta</th>", '<th class="num">Mancano</th>',
            '<th class="num">Mazzo</th>', '<th class="num">Side</th>']
    if with_decks:
        head.append('<th class="num">N. mazzi</th>')
    body = []
    for r in rows:
        cells = [
            f'<td class="num">{r.need}/{r.have}</td>',
            f'<td class="name">{escape(r.name)}</td>',
            _missing_cell(r),
            f'<td class="num">{r.main}</td>',
            f'<td class="num">{r.side}</td>',
        ]
        if with_decks:
            cells.append(f'<td class="num">{r.n_decks}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="scroll"><table><thead><tr>' + "".join(head) + "</tr></thead><tbody>"
        + "\n".join(body) + "</tbody></table></div>"
    )


def _shopping(total: Section) -> str:
    rows = sorted((r for r in total.rows if r.missing > 0), key=lambda r: (-r.missing, r.name.lower()))
    if not rows:
        return "<p>Hai tutte le carte che servono.</p>"
    items = "\n".join(f"<li>{r.missing}x {escape(r.name)} ({r.need}/{r.have})</li>" for r in rows)
    return f'<ul class="shopping">{items}</ul>'


def render_page(
    total: Section,
    per_deck: list[Section],
    warnings: list[str],
    link: str,
    generated_at: datetime,
    version: str,
) -> str:
    parts = [
        "<!doctype html>",
        '<html lang="it"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Deck Inventory {generated_at:%d/%m/%Y %H:%M}</title>",
        f"<style>{_CSS}</style></head><body><main>",
        "<header><h1>Deck Inventory</h1>",
        f'<p class="meta">Aggiornato il {generated_at:%d/%m/%Y %H:%M} · '
        f"{len(per_deck)} mazzi · versione {escape(version)}</p>",
        f'<p class="meta">Binder: <a href="{escape(link)}">{escape(link)}</a></p></header>',
    ]
    if warnings:
        items = "\n".join(f"<li>{escape(w)}</li>" for w in warnings)
        parts.append(f'<section class="warnings"><strong>Avvisi</strong><ul>{items}</ul></section>')
    parts += [
        "<h2>Tutti i mazzi insieme</h2>",
        _summary(total),
        _table(total.rows, with_decks=True),
        "<h2>Solo le carte mancanti</h2>",
        _shopping(total),
        "<h2>Split per mazzo</h2>",
    ]
    for s in per_deck:
        parts += [f"<h3>{escape(s.title)}</h3>", _summary(s), _table(s.rows, with_decks=False)]
    parts.append(f"<footer>Deck Inventory {escape(version)}</footer></main></body></html>")
    return "\n".join(parts) + "\n"
