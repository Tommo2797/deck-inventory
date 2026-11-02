import webbrowser

import pytest

from deck_inventory import binder, browsers, main
from deck_inventory.errors import BinderNetworkError, SiteChangedError
from deck_inventory.main import run
from deck_inventory.settings import read_link

GOOD = "https://piltoverarchive.com/users/esempio/collection/00000000-0000-4000-8000-000000000000"


class FakeUI:
    def __init__(self, answers=()):
        self.answers = list(answers)
        self.asked: list[str | None] = []
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.progress: list[str] = []

    def ask_link(self, error=None):
        self.asked.append(error)
        return self.answers.pop(0) if self.answers else None

    def error(self, message):
        self.errors.append(message)

    def info(self, message):
        self.infos.append(message)

    def Progress(self):
        ui = self

        class _P:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def set(self, text):
                ui.progress.append(text)

            def run(self, func, *args):
                ui.progress.append("<run>")
                return func(*args)

        return _P()


@pytest.fixture
def fake_ui():
    return FakeUI()


def raise_(exc):
    def f(*a, **k):
        raise exc
    return f


def setup_project(path, link=GOOD):
    decks = path / "decks"
    decks.mkdir()
    (decks / "ornn aggro.txt").write_text("MainDeck:\n3 Defy\n", encoding="utf-8")
    if link is not None:
        (path / "settings.txt").write_text(f"binder = {link}\n", encoding="utf-8")


@pytest.fixture
def opened(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(binder, "fetch_collection", lambda *a: {"defy": 8})
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: calls.append(url) or True)
    return calls


def test_failure_keeps_previous_page(tmp_path, fake_ui, monkeypatch):
    (tmp_path / "Inventory old.html").write_text("x")
    setup_project(tmp_path)
    monkeypatch.setattr(binder, "fetch_collection", raise_(BinderNetworkError("rete")))
    assert run(tmp_path, fake_ui) is None
    assert (tmp_path / "Inventory old.html").exists() and fake_ui.errors == ["rete"]


def test_site_changed_message_passed_through(tmp_path, fake_ui, monkeypatch):
    setup_project(tmp_path)
    monkeypatch.setattr(binder, "fetch_collection", raise_(SiteChangedError("cambiato 1.0.0")))
    assert run(tmp_path, fake_ui) is None and fake_ui.errors == ["cambiato 1.0.0"]


def test_success_replaces_previous_page(tmp_path, fake_ui, opened):
    (tmp_path / "Inventory old.html").write_text("x")
    (tmp_path / "keep.html").write_text("x")
    setup_project(tmp_path)
    out = run(tmp_path, fake_ui)
    assert out.exists() and not (tmp_path / "Inventory old.html").exists()
    assert (tmp_path / "keep.html").exists()
    assert out.parent == tmp_path and out.name.startswith("Inventory ")
    assert "3/8" in out.read_text(encoding="utf-8")
    assert opened == [out.as_uri()] and fake_ui.errors == []
    assert fake_ui.progress[0] == "Leggo i mazzi…" and fake_ui.progress[-1] == "Creo la pagina…"


def test_missing_link_asks_and_saves(tmp_path, opened):
    setup_project(tmp_path, link=None)
    ui = FakeUI([GOOD])
    assert run(tmp_path, ui) is not None
    assert ui.asked == [None] and read_link(tmp_path) == GOOD


def test_bad_typed_link_asks_again_with_error(tmp_path, opened):
    setup_project(tmp_path, link=None)
    ui = FakeUI(["nonsense", GOOD + "?x=1"])
    assert run(tmp_path, ui) is not None
    assert ui.asked[0] is None and ui.asked[1].startswith("Link non valido")
    assert read_link(tmp_path) == GOOD


def test_invalid_stored_link_asks_with_error(tmp_path, opened):
    setup_project(tmp_path, link="https://example.com/x")
    ui = FakeUI([GOOD])
    assert run(tmp_path, ui) is not None
    assert ui.asked[0].startswith("Link non valido") and read_link(tmp_path) == GOOD


def test_cancel_link_stops(tmp_path, fake_ui, opened):
    setup_project(tmp_path, link=None)
    assert run(tmp_path, fake_ui) is None
    assert fake_ui.errors == [] and opened == []
    assert not list(tmp_path.glob("Inventory *.html"))


def test_no_decks_error(tmp_path, fake_ui, opened):
    (tmp_path / "settings.txt").write_text(f"binder = {GOOD}\n", encoding="utf-8")
    assert run(tmp_path, fake_ui) is None
    assert len(fake_ui.errors) == 1 and "mazz" in fake_ui.errors[0]


def test_unexpected_error_logged(tmp_path, fake_ui, monkeypatch):
    (tmp_path / "Inventory old.html").write_text("x")
    setup_project(tmp_path)
    monkeypatch.setattr(binder, "fetch_collection", raise_(RuntimeError("boom")))
    assert run(tmp_path, fake_ui) is None
    log = tmp_path / ".app" / "runtime" / "last-error.log"
    assert "RuntimeError: boom" in log.read_text(encoding="utf-8")
    assert len(fake_ui.errors) == 1 and "last-error.log" in fake_ui.errors[0]
    assert (tmp_path / "Inventory old.html").exists()


def test_main_module_exit_codes(monkeypatch, tmp_path):
    from deck_inventory import __main__ as entry
    ui = FakeUI()
    seen = []
    monkeypatch.setattr(main, "run", lambda p, u: seen.append((p, u)) or tmp_path)
    assert entry.main(["x", str(tmp_path)], ui) == 0
    assert seen == [(tmp_path, ui)]
    monkeypatch.setattr(main, "run", lambda p, u: None)
    assert entry.main(["x", str(tmp_path)], ui) == 1


def test_fetch_runs_in_progress_worker_with_fallback_launcher(tmp_path, fake_ui, monkeypatch):
    setup_project(tmp_path)
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: True)
    launched = []

    def fake_launch(playwright, runtime_dir, progress):
        progress("Scarico il browser…")
        launched.append((playwright, runtime_dir))
        return "browser"

    def fake_fetch(link, launcher):
        assert launcher("pw") == "browser"
        return {"defy": 8}

    monkeypatch.setattr(browsers, "launch", fake_launch)
    monkeypatch.setattr(binder, "fetch_collection", fake_fetch)
    assert run(tmp_path, fake_ui) is not None
    assert launched == [("pw", tmp_path / ".app" / "runtime")]
    assert fake_ui.progress[1:5] == [
        main.READING, "<run>", "Scarico il browser…", main.READING
    ]
