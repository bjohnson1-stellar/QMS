"""
QMS System Tray App — Start/stop/restart the Waitress server from the system tray.
"""

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pystray
from PIL import Image, ImageOps

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_ICON_PATH = _PACKAGE_DIR / "frontend" / "static" / "branding" / "SIS-QMS.png"
_LOG_PATH = _PACKAGE_DIR / "data" / "server.log"
_DEFAULT_PORT = 5000
_HEALTH_INTERVAL = 10  # seconds
_MAX_CRASH_RESTARTS = 3
_CRASH_RESET_SECONDS = 60


class TrayApp:
    def __init__(self, port: int = _DEFAULT_PORT):
        self.port = port
        self.hostname = socket.gethostname()
        self._process: subprocess.Popen | None = None
        self._log_fh = None  # file handle for server.log
        self._external = False  # True if a server we didn't start is on the port
        self._stop_health = threading.Event()
        self._icon: pystray.Icon | None = None
        self._auto_start = False
        # Crash tracking for auto-restart
        self._crash_count = 0
        self._last_crash_time = 0.0
        # Icon images (set in run())
        self._icon_running: Image.Image | None = None
        self._icon_stopped: Image.Image | None = None

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
        # Open log file for server output
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._log_fh = open(_LOG_PATH, "a", encoding="utf-8")
        self._process = subprocess.Popen(
            [sys.executable, "-m", "qms", "serve", "--port", str(self.port)],
            cwd=str(_PACKAGE_DIR),
            stdout=self._log_fh,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._refresh_menu()
        # Spawn thread to wait for port and send toast
        threading.Thread(target=self._wait_and_notify_ready, daemon=True).start()

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
        self._close_log()
        self._external = False
        self._refresh_menu()

    def restart_server(self):
        self.stop_server()
        time.sleep(0.5)
        self.start_server()

    def open_browser(self):
        import webbrowser
        webbrowser.open(f"http://{self.hostname}:{self.port}")

    def view_logs(self):
        if _LOG_PATH.exists():
            os.startfile(str(_LOG_PATH))
        else:
            self._notify("No logs", "Server log file does not exist yet.")

    def quit(self):
        self._stop_health.set()
        if self.running:
            self.stop_server()
        self._close_log()
        if self._icon:
            self._icon.stop()

    def _close_log(self):
        if self._log_fh and not self._log_fh.closed:
            self._log_fh.close()
        self._log_fh = None

    # ── Startup readiness notification ───────────────────────────────

    def _wait_and_notify_ready(self):
        """Poll port every 1s up to 30s, then toast when server is ready."""
        for _ in range(30):
            if not self.running:
                return
            if self._port_in_use():
                self._notify("SIS QMS", f"Server is ready on port {self.port}")
                self._refresh_menu()
                return
            time.sleep(1)

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
            pystray.MenuItem("View Logs", lambda: self.view_logs()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.quit()),
            # Hidden default item — double-click opens browser
            pystray.MenuItem("Open", lambda: self.open_browser(), default=True, visible=False),
        )

    def _refresh_menu(self):
        if self._icon:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()
            self._update_icon_color()

    def _update_icon_color(self):
        """Swap tray icon between color (running) and grayscale (stopped)."""
        if not self._icon:
            return
        is_running = self.running or self._external
        target = self._icon_running if is_running else self._icon_stopped
        if target and self._icon.icon is not target:
            self._icon.icon = target

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
                # Our process died — attempt auto-restart
                self._process = None
                self._close_log()
                self._refresh_menu()
                self._attempt_auto_restart()
            elif not self.running and not self._external and port_up:
                # Something else grabbed the port
                self._external = True
                self._refresh_menu()
            elif self._external and not port_up:
                self._external = False
                self._refresh_menu()

    def _attempt_auto_restart(self):
        """Auto-restart after crash, with consecutive-failure tracking."""
        now = time.time()
        if now - self._last_crash_time > _CRASH_RESET_SECONDS:
            self._crash_count = 0
        self._crash_count += 1
        self._last_crash_time = now

        if self._crash_count > _MAX_CRASH_RESTARTS:
            self._notify("Auto-restart disabled",
                         "Server crashed repeatedly. Restart manually from the menu.")
            return

        self._notify("Server crashed",
                     f"Restarting automatically (attempt {self._crash_count}/{_MAX_CRASH_RESTARTS})...")
        time.sleep(1)
        self.start_server()

    # ── Run ─────────────────────────────────────────────────────────

    def run(self):
        image = Image.open(_ICON_PATH) if _ICON_PATH.exists() else _default_icon()
        # Prepare running (color) and stopped (grayscale) icon variants
        self._icon_running = image.copy()
        gray = ImageOps.grayscale(image.convert("RGB"))
        self._icon_stopped = gray.convert("RGBA")
        # Copy alpha channel from original if it has one
        if image.mode == "RGBA":
            self._icon_stopped.putalpha(image.split()[3])

        self._icon = pystray.Icon(
            name="qms-tray",
            icon=self._icon_stopped,  # start gray, will update after start
            title="SIS QMS",
            menu=self._build_menu(),
        )
        # Detect if server is already running, or auto-start it
        if self._port_in_use():
            self._external = True
            self._refresh_menu()
        elif self._auto_start:
            self.start_server()

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


def main(port: int = _DEFAULT_PORT, auto_start: bool = False):
    app = TrayApp(port=port)
    if auto_start:
        app._auto_start = True
    app.run()
