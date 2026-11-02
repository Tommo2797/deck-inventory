import plistlib
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError

from deck_inventory import browsers
from deck_inventory.browsers import LaunchSpec, candidates, choose, default_browser_id, find_installed, launch
from deck_inventory.errors import BrowserUnavailableError


def test_default_chromium_wins():
    assert choose("com.brave.Browser", {"chrome": "/c", "brave": "/b"}) == LaunchSpec(None, "/b")


def test_safari_default_falls_back_to_chrome():
    assert choose("com.apple.Safari", {"chrome": "/c", "msedge": "/e"}).executable_path == "/c"


def test_edge_when_no_chrome():
    assert choose("FirefoxURL-308046B0AF4A39CB", {"msedge": "/e"}).executable_path == "/e"


def test_other_family_when_no_chrome_or_edge():
    assert choose(None, {"vivaldi": "/v"}).executable_path == "/v"


def test_windows_progid_prefix_case_insensitive():
    assert choose("bravehtml.ABC123", {"chrome": "/c", "brave": "/b"}).executable_path == "/b"


def test_nothing_installed():
    assert choose(None, {}) is None


def test_detection_does_not_raise():
    assert default_browser_id() is None or isinstance(default_browser_id(), str)
    assert isinstance(find_installed(), dict)


# --- Opera, ordine dei candidati ----------------------------------------------


def test_opera_not_supported():
    assert browsers._family("com.operasoftware.Opera") is None
    assert browsers._family("OperaStable") is None
    assert "opera" not in browsers._MAC_APPS and "opera" not in browsers._WIN_PATHS
    assert choose(None, {"opera": "/o"}) is None


def test_candidates_order_default_first_no_duplicates():
    installed = {"chrome": "/c", "msedge": "/e", "brave": "/b", "chromium": "/x"}
    assert [s.executable_path for s in candidates("com.brave.Browser", installed)] == ["/b", "/c", "/e", "/x"]
    assert [s.executable_path for s in candidates("com.google.Chrome", installed)] == ["/c", "/e", "/b", "/x"]


def test_default_browser_id_ignores_non_string_handler(tmp_path, monkeypatch):
    prefs = tmp_path / "Library/Preferences/com.apple.LaunchServices"
    prefs.mkdir(parents=True)
    with open(prefs / "com.apple.launchservices.secure.plist", "wb") as f:
        plistlib.dump({"LSHandlers": [{"LSHandlerURLScheme": "https", "LSHandlerRoleAll": 3}]}, f)
    monkeypatch.setattr(browsers.sys, "platform", "darwin")
    monkeypatch.setattr(browsers.Path, "home", classmethod(lambda cls: tmp_path))
    assert default_browser_id() is None


# --- avvio con ripiego --------------------------------------------------------


class FakeChromium:
    def __init__(self, bundled: Path, working: set):
        self.executable_path = str(bundled)
        self.working = working  # percorsi che partono; None = Chromium di Playwright
        self.tried: list = []

    def launch(self, headless=True, executable_path=None, channel=None):
        self.tried.append(executable_path)
        if executable_path in self.working:
            return f"browser:{executable_path}"
        raise PlaywrightError(f"cannot start {executable_path}\nmore")


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium


@pytest.fixture
def installs(monkeypatch):
    calls: list = []

    def fake_install(runtime_dir, progress):
        progress(browsers.DOWNLOAD_MESSAGE)
        calls.append(runtime_dir)

    monkeypatch.setattr(browsers, "install_bundled", fake_install)
    return calls


def test_launch_uses_first_working_installed(tmp_path, installs):
    ch = FakeChromium(tmp_path / "missing", {"/e"})
    got = launch(FakePlaywright(ch), tmp_path, lambda t: None, "com.google.Chrome", {"chrome": "/c", "msedge": "/e"})
    assert got == "browser:/e" and ch.tried == ["/c", "/e"] and installs == []


def test_launch_falls_back_to_present_bundled_without_install(tmp_path, installs):
    bundled = tmp_path / "chrome"
    bundled.write_text("x")
    ch = FakeChromium(bundled, {None})
    msgs: list = []
    got = launch(FakePlaywright(ch), tmp_path, msgs.append, None, {"chrome": "/c"})
    assert got == "browser:None" and ch.tried == ["/c", None]
    assert installs == [] and msgs == []


def test_launch_installs_bundled_when_missing(tmp_path, installs):
    ch = FakeChromium(tmp_path / "missing", {None})
    msgs: list = []
    got = launch(FakePlaywright(ch), tmp_path, msgs.append, None, {})
    assert got == "browser:None" and ch.tried == [None]
    assert installs == [tmp_path] and msgs == [browsers.DOWNLOAD_MESSAGE]


def test_launch_reinstalls_when_bundled_present_but_broken(tmp_path, installs):
    bundled = tmp_path / "chrome"
    bundled.write_text("x")
    ch = FakeChromium(bundled, set())
    with pytest.raises(BrowserUnavailableError) as err:
        launch(FakePlaywright(ch), tmp_path, lambda t: None, None, {"msedge": "/e"})
    assert ch.tried == ["/e", None, None] and installs == [tmp_path]
    assert "cannot start None" in err.value.message and "more" not in err.value.message


# --- download del Chromium di Playwright --------------------------------------


def test_install_success(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw, cmd=cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok")

    monkeypatch.setattr(browsers.subprocess, "run", fake_run)
    msgs: list = []
    browsers.install_bundled(tmp_path, msgs.append)
    assert seen["cmd"][-2:] == ["install", "chromium"] and seen["timeout"] == 30 * 60
    assert seen["stdout"] == subprocess.PIPE and msgs == [browsers.DOWNLOAD_MESSAGE]
    assert "alcune centinaia di MB" in msgs[0]
    assert not (tmp_path / "last-error.log").exists()


def test_install_failure_logs_tail_not_in_message(tmp_path, monkeypatch):
    out = "\n".join(f"riga {i}" for i in range(100))
    monkeypatch.setattr(
        browsers.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout=out)
    )
    with pytest.raises(BrowserUnavailableError) as err:
        browsers.install_bundled(tmp_path, lambda t: None)
    log = (tmp_path / "last-error.log").read_text(encoding="utf-8")
    assert "riga 99" in log and "riga 59" not in log and "riga 60" in log
    assert "riga" not in err.value.message and "last-error.log" in err.value.message


def test_install_timeout(tmp_path, monkeypatch):
    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"], output=b"scarico 40%")

    monkeypatch.setattr(browsers.subprocess, "run", fake_run)
    with pytest.raises(BrowserUnavailableError):
        browsers.install_bundled(tmp_path, lambda t: None)
    assert "scarico 40%" in (tmp_path / "last-error.log").read_text(encoding="utf-8")
