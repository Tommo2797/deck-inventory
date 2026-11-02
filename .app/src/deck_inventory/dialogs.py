"""Finestre di dialogo native (tkinter), in italiano. Non usate nei test."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

TITLE = "Deck Inventory"

_LINK_PROMPT = (
    "Incolla il link del tuo binder PUBBLICO su Piltover Archive.\n"
    "Sul sito: apri il binder → \"Make Public\" → \"Share\"."
)


def _root() -> tk.Tk:
    root = tk.Tk()
    root.title(TITLE)
    root.resizable(False, False)
    return root


def _bring_to_front(win: tk.Misc) -> None:
    win.lift()
    win.attributes("-topmost", True)
    win.after(300, lambda: win.attributes("-topmost", False))
    win.focus_force()


def _center(win: tk.Misc) -> None:
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = (win.winfo_screenwidth() - w) // 2
    y = (win.winfo_screenheight() - h) // 3
    win.geometry(f"+{x}+{y}")


def ask_link(error: str | None = None) -> str | None:
    """Chiede il link del binder. Restituisce il testo inserito, o None se annullato."""
    root = _root()
    result: dict[str, str | None] = {"value": None}

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=_LINK_PROMPT, justify="left").pack(anchor="w")
    if error:
        tk.Label(frame, text=error, fg="#b3261e", justify="left", wraplength=480).pack(anchor="w", pady=(8, 0))
    entry = ttk.Entry(frame, width=70)
    entry.pack(fill="x", pady=(10, 12))

    def ok(_event=None):
        result["value"] = entry.get()
        root.destroy()

    def cancel(_event=None):
        result["value"] = None
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.pack(anchor="e")
    ttk.Button(buttons, text="Annulla", command=cancel).pack(side="right")
    ttk.Button(buttons, text="OK", command=ok, default="active").pack(side="right", padx=(0, 8))
    root.bind("<Return>", ok)
    root.bind("<Escape>", cancel)
    root.protocol("WM_DELETE_WINDOW", cancel)

    _center(root)
    _bring_to_front(root)
    entry.focus_set()
    root.mainloop()
    return result["value"]


class Progress:
    """Finestrella con barra indeterminata.

    Uso: `with Progress() as p: p.set("…"); p.run(funzione_lunga, ...)`.
    `run` esegue la funzione in un thread e intanto tiene viva la finestra;
    `set` si può chiamare anche da quel thread (il testo lo applica il thread
    principale, l'unico che tocca tkinter).
    """

    _POLL_S = 0.05

    def __init__(self) -> None:
        self._root: tk.Tk | None = None
        self._label: ttk.Label | None = None
        self._text = ""
        self._shown: str | None = None

    def __enter__(self) -> "Progress":
        root = _root()
        root.protocol("WM_DELETE_WINDOW", lambda: None)  # non chiudibile a metà lavoro
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        self._label = ttk.Label(frame, text="", width=50)
        self._label.pack(anchor="w")
        bar = ttk.Progressbar(frame, mode="indeterminate", length=360)
        bar.pack(fill="x", pady=(10, 0))
        bar.start(15)
        self._root = root
        _center(root)
        _bring_to_front(root)
        root.update()
        return self

    def _refresh(self) -> None:
        if self._root is None:
            return
        text = self._text
        if text != self._shown:
            self._label.configure(text=text)
            self._shown = text
        self._root.update()

    def set(self, text: str) -> None:
        self._text = text
        if threading.current_thread() is threading.main_thread():
            self._refresh()

    def run(self, func, *args):
        """Esegue func(*args) in un thread aggiornando la finestra; rilancia le sue eccezioni."""
        outcome: dict = {}

        def work() -> None:
            try:
                outcome["value"] = func(*args)
            except BaseException as exc:  # noqa: BLE001 - rilanciata nel thread principale
                outcome["error"] = exc

        worker = threading.Thread(target=work, name="deck-inventory-work", daemon=True)
        worker.start()
        while worker.is_alive():
            self._refresh()
            worker.join(self._POLL_S)
        self._refresh()
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def __exit__(self, *exc) -> bool:
        if self._root is not None:
            self._root.destroy()
            self._root = None
        return False


def _message(kind, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    _bring_to_front(root)
    kind(TITLE, message, parent=root)
    root.destroy()


def error(message: str) -> None:
    _message(messagebox.showerror, message)


def info(message: str) -> None:
    _message(messagebox.showinfo, message)
