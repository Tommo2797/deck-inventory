"""Cattura i payload di un binder pubblico per i test.

Uso (dalla radice del progetto, con le variabili d'ambiente di sviluppo):
    uv run --project .app/src python .app/src/tools/capture_binder.py <link> <out.json>

Scrive in <out.json> una lista JSON di stringhe: il testo RSC di ogni pagina del
binder, esattamente come lo restituisce `binder.fetch_payloads` e come lo
consuma `binder.parse_payloads`.

Ricognizione del 2026-10-31 (dettagli in testa a deck_inventory/binder.py):
- Le carte non arrivano da POST "server action": l'unica POST alla URL del
  binder è `getUserPricingPrefs`. I dati sono nell'HTML renderizzato dal server
  (stream RSC `self.__next_f.push`): `initialOwnership` (tutto il binder,
  id variante -> quantità) + le varianti della pagina con `card.name`.
- Da sloggati la griglia mostra tutto il catalogo (1.434 varianti, anche con
  quantità 0), 48 per pagina. Con i parametri URL `qtyMin=1&limit=100&page=N`
  il server restituisce solo le possedute, 100 per pagina (limite massimo).
- Il caricamento completo si ottiene visitando le pagine 1..totalPages
  (campo `pagination.totalPages` della prima pagina).
"""

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from deck_inventory import binder, browsers  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Uso: capture_binder.py <link> <out.json>")
    link, out = sys.argv[1], Path(sys.argv[2])
    launch = browsers.resolve(SRC.parent / "runtime", print)
    payloads = binder.fetch_payloads(link, launch)
    out.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
    print(f"{len(payloads)} pagine, {out.stat().st_size} byte -> {out}")


if __name__ == "__main__":
    main()
