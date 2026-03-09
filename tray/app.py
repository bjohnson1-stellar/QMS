"""
QMS System Tray App — Start/stop/restart the Waitress server from the system tray.
"""

import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pystray
from PIL import Image

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_ICON_PATH = _PACKAGE_DIR / "frontend" / "static" / "branding" / "Stellar_40th_Logo_Rev1_Circle_BlueGraphite.png"
_DEFAULT_PORT = 5000
_HEALTH_INTERVAL = 10  # seconds


class TrayApp:
    def __init__(self, port: int = _DEFAULT_PORT):
        self.port = port
        self.hostname = socket.gethostname()
        self._process: subprocess.Popen | None = None
        self._external = False  # True if a server we didn't start is on the port
        self._stop_health = threading.Event()
        self._icon: pystray.Icon | None = None

    # ── Status ──────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _port_in_use(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", self.port)) == 0

    def _status_text(self) -> str:
        if self.running:
            return f"SIS QMS — Running (:{self.port})"
        if self._external:
            return f"SIS QMS — External (:{self.port})"
        return "SIS QMS — Stopped"

    # ── Actions ─────────────────────────────────────────────────────

    def start_server(self):
        if self.running:
            return
        if self._port_in_use():
            self._external = True
            self._notify("Port in use", f"Port {self.port} is already in use by another process.")
            self._refresh_menu()
            return
        self._external = False
        self._process = subprocess.Popen(
            [sys.executable, "-m", "qms", "serve", "--port", str(self.port)],
            cwd=str(_PACKAGE_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._refresh_menu()

    def stop_server(self):
        if not self.running:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=3)
        self._process = None
        self._external = False
        self._refresh_menu()

    def restart_server(self):
        self.stop_server()
        time.sleep(0.5)
        self.start_server()

    def open_browser(self):
        import webbrowser
        webbrowser.open(f"http://{self.hostname}:{self.port}")

    def quit(self):
        self._stop_health.set()
        if self.running:
            self.stop_server()
        if self._icon:
            self._icon.stop()

    # ── Menu ────────────────────────────────────────────────────────

    def _build_menu(self) -> pystray.Menu:
        is_running = self.running or self._external
        is_ours = self.running and not self._external
        return pystray.Menu(
            pystray.MenuItem(self._status_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start Server", lambda: self.start_server(), enabled=not is_running),
            pystray.MenuItem("Stop Server", lambda: self.stop_server(), enabled=is_ours),
            pystray.MenuItem("Restart Server", lambda: self.restart_server(), enabled=is_ours),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open in Browser", lambda: self.open_browser(), enabled=is_running),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.quit()),
        )

    def _refresh_menu(self):
        if self._icon:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()

    def _notify(self, title: str, message: str):
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass  # notifications not supported on all platforms

    # ── Health check ────────────────────────────────────────────────

    def _health_loop(self):
        while not self._stop_health.is_set():
            self._stop_health.wait(_HEALTH_INTERVAL)
            if self._stop_health.is_set():
                break
            port_up = self._port_in_use()
            if self.running and not port_up:
                # Our process died
                self._process = None
                self._notify("Server stopped", "The QMS server process has exited unexpectedly.")
                self._refresh_menu()
            elif not self.running and not self._external and port_up:
                # Something else grabbed the port
                self._external = True
                self._refresh_menu()
            elif self._external and not port_up:
                self._external = False
                self._refresh_menu()

    # ── Run ─────────────────────────────────────────────────────────

    def run(self):
        image = Image.open(_ICON_PATH) if _ICON_PATH.exists() else _default_icon()
        self._icon = pystray.Icon(
            name="qms-tray",
            icon=image,
            title="SIS QMS",
            menu=self._build_menu(),
        )
        # Detect if server is already running
        if self._port_in_use():
            self._external = True
            self._refresh_menu()

        health_thread = threading.Thread(target=self._health_loop, daemon=True)
        health_thread.start()
        self._icon.run()  # blocks until quit


def _default_icon() -> Image.Image:
    """Fallback 64x64 blue circle icon if branding image is missing."""
    from PIL import ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(44, 62, 80, 255))
    return img


def main(port: int = _DEFAULT_PORT):
    app = TrayApp(port=port)
    app.run()
