"""Avvio: python -m deck_inventory <cartella del progetto>"""

import sys
from pathlib import Path

from deck_inventory import main as main_flow


def main(argv: list[str], ui=None) -> int:
    if ui is None:
        from deck_inventory import dialogs as ui
    return 0 if main_flow.run(Path(argv[1]), ui) is not None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
