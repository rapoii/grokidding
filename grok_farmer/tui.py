"""Grokidding TUI — Terminal User Interface powered by Textual.

Full-featured dashboard replacing the web panel:
- Dashboard with stats + start/stop farming
- Accounts table with real-time status
- Quota tracking with cache
- Renew expired accounts
- Live logs
- Settings editor (proxy, email, 9router)
"""

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label,
    ProgressBar, RadioSet, Select, Static, Switch,
    TabbedContent, TabPane, TextArea,
)

# ── Config ──
PROJECT_DIR = Path(__file__).parent.parent


def _load_config() -> dict:
    cfg_path = PROJECT_DIR / "config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def _save_config(cfg: dict):
    cfg_path = PROJECT_DIR / "config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_router_db() -> Path:
    cfg = _load_config()
    db_path = cfg.get("ninrouter", {}).get("db_path", "")
    if db_path and Path(db_path).exists():
        return Path(db_path)
    home = Path.home()
    candidates = [
        home / "AppData" / "Roaming" / "9router" / "db" / "data.sqlite",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path()


# ── Data Loaders ──

def load_accounts_from_router() -> list[dict]:
    router_db = _get_router_db()
    if not router_db.exists():
        return []
    try:
        import sqlite3
        db = sqlite3.connect(f"file:{router_db}?immutable=1", uri=True)
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT id, name, email, isActive, data, provider, authType,
                   createdAt, updatedAt
            FROM providerConnections
            WHERE provider LIKE '%grok%' AND isActive=1
            ORDER BY createdAt DESC
        """).fetchall()
        accounts = []
        for row in rows:
            data = json.loads(row["data"]) if row["data"] else {}
            error_code = data.get("errorCode")
            test_status = data.get("testStatus", "unknown")
            if error_code == 429:
                status = "exhausted"
            elif error_code:
                status = "error"
            elif test_status in ("success", "active"):
                status = "active"
            elif test_status == "unavailable":
                status = "unavailable"
            else:
                status = "unknown"
            accounts.append({
                "id": row["id"],
                "name": row["name"] or "?",
                "email": row["email"] or data.get("email", "?"),
                "active": bool(row["isActive"]),
                "status": status,
                "created_at": (row["createdAt"] or "")[:16],
            })
        db.close()
        return accounts
    except Exception:
        return []


# ── Farm State (shared between TUI and farm thread) ──

class FarmState:
    def __init__(self):
        self.running = False
        self.stop_requested = False
        self.total = 0
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.current_email = ""
        self.current_step = ""
        self.logs: list[str] = []

    def reset(self, total: int):
        self.running = True
        self.stop_requested = False
        self.total = total
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.current_email = ""
        self.current_step = ""
        self.logs = []

    def add_log(self, line: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = f"[{ts}] {line}"
        self.logs.append(entry)
        if len(self.logs) > 500:
            self.logs = self.logs[-300:]

    def finish(self):
        self.running = False
        self.stop_requested = False


farm_state = FarmState()


# ── Farm Thread ──

def _run_farm(count: int, use_proxy: bool):
    """Background thread that runs the farming loop."""
    import sys
    from io import StringIO

    old_stdout, old_stderr = sys.stdout, sys.stderr
    buf = StringIO()
    sys.stdout = buf
    sys.stderr = buf

    try:
        from .config import load_config
        from .email_generator import GeneratorEmailReader, get_available_domains
        from .proxy import ProxyRotator
        from .router_push import RouterPusher
        from .turnstile import TurnstileSolver
        from .__main__ import run_single_account

        cfg = load_config()
        ocfg = cfg.get("output", {})

        # Get available email domains
        domains = get_available_domains()
        farm_state.add_log(f"Loaded {len(domains)} email domains from generator.email")

        # Proxy
        proxy_rotator = ProxyRotator([])  # empty pool if no proxy
        if use_proxy:
            pool = cfg.get("proxy", {}).get("pool", [])
            if pool:
                proxy_rotator = ProxyRotator(pool)
                farm_state.add_log(f"Proxy: {len(pool)} proxies in pool")
            else:
                farm_state.add_log("WARNING: Proxy mode on but pool empty!")

        # Create solver (shared across accounts)
        solver = TurnstileSolver(cfg)

        for i in range(count):
            if farm_state.stop_requested:
                farm_state.add_log("Stop requested — stopping.")
                break

            farm_state.current_step = f"farming {i + 1}/{count}"
            farm_state.add_log(f"--- Account {i + 1}/{count} ---")

            proxy_url = proxy_rotator.next() if proxy_rotator.pool else ""

            try:
                # Create email reader using browser from solver
                # (solver._browser is set after first account)
                email_reader = GeneratorEmailReader(solver._browser) if solver._browser else None

                result = run_single_account(
                    cfg=cfg,
                    solver=solver,
                    proxy_rotator=proxy_rotator,
                    email_reader=email_reader,
                    pusher=None,  # pusher created inside run_single_account
                    dry_run=False,
                    email_mode='generator',
                )
            except Exception as e:
                result = {"success": False, "error": str(e), "email": "?"}

            farm_state.completed += 1

            if result.get("success"):
                farm_state.successful += 1
                farm_state.add_log(f"SUCCESS: {result.get('email', '?')}")
            else:
                farm_state.failed += 1
                farm_state.add_log(f"FAILED: {result.get('email', '?')} - {result.get('error', '?')}")

            farm_state.current_email = result.get("email", "")

        farm_state.add_log(f"Farm complete. {farm_state.successful}/{farm_state.total} successful.")
        farm_state.finish()

    except Exception as e:
        farm_state.add_log(f"FATAL ERROR: {e}")
        farm_state.finish()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# ── TUI Widgets ──

class StatsBar(Static):
    """Dashboard stats bar."""
    total = reactive(0)
    active = reactive(0)
    exhausted = reactive(0)
    errored = reactive(0)

    def render(self) -> str:
        return (
            f"[bold]Accounts:[/] {self.total}  "
            f"[green]Active:[/] {self.active}  "
            f"[yellow]Exhausted:[/] {self.exhausted}  "
            f"[red]Error:[/] {self.errored}"
        )


class LogViewer(Static):
    """Live log viewer."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_count = 0

    def render(self) -> str:
        logs = farm_state.logs[-50:]
        if not logs:
            return "[dim]No logs yet. Start farming to see output.[/]"
        return "\n".join(logs)


# ── Main TUI App ──

class GrokiddingTUI(App):
    """Grokidding Terminal User Interface."""

    TITLE = "Grokidding"
    SUB_TITLE = "Grok/xAI Account Farmer"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1 3;
        grid-rows: 1fr 5fr 1fr;
    }

    #stats-bar {
        height: 3;
        dock: top;
        background: $surface;
        padding: 0 2;
    }

    #main-content {
        height: 100%;
    }

    .tab-content {
        height: 100%;
        padding: 1 2;
    }

    #footer-bar {
        height: 3;
        dock: bottom;
        background: $surface;
        padding: 0 2;
    }

    LogViewer {
        height: 100%;
        border: solid $primary;
        padding: 1;
        overflow-y: auto;
    }

    DataTable {
        height: 100%;
    }

    .btn-row {
        height: 3;
        margin: 1 0;
    }

    .settings-group {
        margin: 1 0;
        padding: 1 2;
        border: solid $primary;
    }

    .settings-group Label {
        margin: 0 0 0 1;
    }

    Input {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "start_farm", "Farm"),
        Binding("s", "stop_farm", "Stop"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = _load_config()
        self._refresh_timer = None

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="dashboard"):
            # Dashboard
            with TabPane("Dashboard", id="dashboard"):
                with Vertical(classes="tab-content"):
                    yield StatsBar(id="stats-bar")
                    yield Label("Farm Settings", classes="section-title")
                    with Horizontal(classes="btn-row"):
                        yield Label("Count:")
                        yield Input(value="1", id="farm-count", type="integer")
                        yield Button("Start Farming", id="btn-farm", variant="success")
                        yield Button("Stop", id="btn-stop", variant="error")
                    yield Label("Live Logs", classes="section-title")
                    yield LogViewer(id="log-viewer")

            # Accounts
            with TabPane("Accounts", id="accounts"):
                with Vertical(classes="tab-content"):
                    with Horizontal(classes="btn-row"):
                        yield Button("Refresh", id="btn-refresh-accounts")
                        yield Button("Delete Selected", id="btn-delete-account", variant="error")
                    yield DataTable(id="accounts-table")

            # Renew
            with TabPane("Renew", id="renew"):
                with Vertical(classes="tab-content"):
                    yield Label("Renew expired accounts by deleting them and farming replacements.")
                    with Horizontal(classes="btn-row"):
                        yield Label("Count (0=auto):")
                        yield Input(value="0", id="renew-count", type="integer")
                        yield Button("Renew", id="btn-renew", variant="warning")
                    yield LogViewer(id="renew-log")

            # Logs
            with TabPane("Logs", id="logs"):
                with Vertical(classes="tab-content"):
                    yield LogViewer(id="full-log")

            # Settings
            with TabPane("Settings", id="settings"):
                with Vertical(classes="tab-content"):
                    with Vertical(classes="settings-group"):
                        yield Label("[bold]Email Generator[/]")
                        yield Label("Mode: generator.email (no IMAP)")
                        yield Label("[dim]OTP codes scraped from generator.email via browser[/]")

                    with Vertical(classes="settings-group"):
                        yield Label("[bold]Proxy[/]")
                        with Horizontal():
                            yield Label("Mode:")
                            yield Select(
                                [("Off", "off"), ("SOCKS5", "socks5"), ("ADB", "adb")],
                                value=self.cfg.get("proxy", {}).get("mode", "off"),
                                id="proxy-mode",
                            )
                        with Horizontal():
                            yield Label("Pool (one per line):")
                        yield TextArea(
                            "\n".join(self.cfg.get("proxy", {}).get("pool", [])),
                            id="proxy-pool",
                        )

                    with Vertical(classes="settings-group"):
                        yield Label("[bold]9Router[/]")
                        with Horizontal():
                            yield Label("Base URL:")
                            yield Input(
                                value=self.cfg.get("ninrouter", {}).get("base_url", "http://localhost:3000"),
                                id="router-url",
                            )
                        with Horizontal():
                            yield Label("DB Path:")
                            yield Input(
                                value=self.cfg.get("ninrouter", {}).get("db_path", ""),
                                id="router-db-path",
                                placeholder="Auto-detect",
                            )

                    with Horizontal(classes="btn-row"):
                        yield Button("Save Settings", id="btn-save-settings", variant="success")
                        yield Button("Test Proxy", id="btn-test-proxy")

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_stats()
        self._refresh_accounts_table()
        # Auto-refresh every 10s
        self._refresh_timer = self.set_interval(10, self._refresh_stats)

    def _refresh_stats(self):
        accounts = load_accounts_from_router()
        stats = self.query_one("#stats-bar", StatsBar)
        stats.total = len(accounts)
        stats.active = sum(1 for a in accounts if a["status"] == "active")
        stats.exhausted = sum(1 for a in accounts if a["status"] == "exhausted")
        stats.errored = sum(1 for a in accounts if a["status"] in ("error", "unavailable", "unknown"))

    def _refresh_accounts_table(self):
        table = self.query_one("#accounts-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Email", "Status", "Created")
        accounts = load_accounts_from_router()
        for a in accounts:
            status_style = {
                "active": "green",
                "exhausted": "yellow",
                "error": "red",
                "unavailable": "red",
            }.get(a["status"], "dim")
            table.add_row(
                a["name"],
                a["email"],
                f"[{status_style}]{a['status']}[/]",
                a["created_at"],
                key=a["id"],
            )


    def action_start_farm(self):
        if farm_state.running:
            self.notify("Farming already in progress!", severity="warning")
            return
        count_input = self.query_one("#farm-count", Input)
        count = int(count_input.value or "1")
        farm_state.reset(count)
        farm_state.add_log(f"Starting farm: {count} account(s)")

        proxy_mode = self.cfg.get("proxy", {}).get("mode", "off")
        use_proxy = proxy_mode == "socks5"

        thread = threading.Thread(target=_run_farm, args=(count, use_proxy), daemon=True)
        thread.start()

        self.notify(f"Farming {count} accounts started!", severity="information")

    def action_stop_farm(self):
        if farm_state.running:
            farm_state.stop_requested = True
            farm_state.add_log("Stop requested...")
            self.notify("Stop requested", severity="warning")
        else:
            self.notify("No farming in progress", severity="information")

    def action_refresh(self):
        self._refresh_stats()
        self._refresh_accounts_table()
        self.notify("Refreshed!", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-farm":
            self.action_start_farm()
        elif btn_id == "btn-stop":
            self.action_stop_farm()
        elif btn_id == "btn-refresh-accounts":
            self._refresh_accounts_table()

        elif btn_id == "btn-renew":
            self._do_renew()
        elif btn_id == "btn-save-settings":
            self._save_settings()
        elif btn_id == "btn-delete-account":
            self.notify("Select a row first (feature coming soon)", severity="warning")

    def _do_renew(self):
        count_input = self.query_one("#renew-count", Input)
        count = int(count_input.value or "0")

        accounts = load_accounts_from_router()
        expired = [a for a in accounts if a["status"] in ("expired", "exhausted")]

        if not expired:
            self.notify("No expired accounts found", severity="warning")
            return

        actual_count = count if count > 0 else len(expired)
        farm_state.add_log(f"[RENEW] Found {len(expired)} expired, renewing {actual_count}")

        # Delete expired
        db_path = _get_router_db()
        if db_path.exists():
            import sqlite3
            db = sqlite3.connect(str(db_path))
            for conn in expired[:actual_count]:
                db.execute("DELETE FROM providerConnections WHERE id = ?", (conn["id"],))
                farm_state.add_log(f"[RENEW] Deleted: {conn['name']}")
            db.commit()
            db.close()

        # Farm replacements
        farm_state.reset(actual_count)
        proxy_mode = self.cfg.get("proxy", {}).get("mode", "off")
        use_proxy = proxy_mode == "socks5"

        thread = threading.Thread(target=_run_farm, args=(actual_count, use_proxy), daemon=True)
        thread.start()

        self.notify(f"Renewing {actual_count} accounts...", severity="information")

    def _save_settings(self):
        cfg = _load_config()

        # Proxy
        proxy_mode = self.query_one("#proxy-mode", Select).value
        cfg.setdefault("proxy", {})["mode"] = proxy_mode

        pool_text = self.query_one("#proxy-pool", TextArea).text
        pool = [line.strip() for line in pool_text.strip().split("\n") if line.strip()]
        cfg["proxy"]["pool"] = pool

        # 9Router
        cfg.setdefault("ninrouter", {})["base_url"] = self.query_one("#router-url", Input).value
        db_path = self.query_one("#router-db-path", Input).value
        if db_path:
            cfg["ninrouter"]["db_path"] = db_path

        _save_config(cfg)
        self.cfg = cfg
        self.notify("Settings saved!", severity="information")

    # Log updater
    def on_timer(self) -> None:
        # Update log viewers
        log_text = "\n".join(farm_state.logs[-50:]) or "[dim]No logs yet.[/]"
        for viewer_id in ("#log-viewer", "#full-log", "#renew-log"):
            try:
                viewer = self.query_one(viewer_id, LogViewer)
                viewer.update(log_text)
            except Exception:
                pass


if __name__ == "__main__":
    app = GrokiddingTUI()
    app.run()
