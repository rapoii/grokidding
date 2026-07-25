"""Grokidding TUI — OpenCode-style interactive terminal interface.

Split layout: sidebar + main content + command input.
No tabs, no buttons — just type commands.
"""

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    DataTable, Footer, Header, Input, Label,
    ProgressBar, RichLog, Static,
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
    candidates = [home / "AppData" / "Roaming" / "9router" / "db" / "data.sqlite"]
    for c in candidates:
        if c.exists():
            return c
    return Path()


def load_accounts() -> list[dict]:
    router_db = _get_router_db()
    if not router_db.exists():
        return []
    try:
        import sqlite3
        db = sqlite3.connect(f"file:{router_db}?immutable=1", uri=True)
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT id, name, email, isActive, data, provider,
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
            else:
                status = "unknown"
            accounts.append({
                "id": row["id"],
                "name": row["name"] or "?",
                "email": row["email"] or data.get("email", "?"),
                "status": status,
                "created": (row["createdAt"] or "")[:16],
            })
        db.close()
        return accounts
    except Exception:
        return []


# ── Farm State ──
class FarmState:
    def __init__(self):
        self.running = False
        self.stop_requested = False
        self.total = 0
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.current_email = ""
        self.logs: list[str] = []

    def reset(self, total: int):
        self.running = True
        self.stop_requested = False
        self.total = total
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.current_email = ""
        self.logs = []

    def add_log(self, line: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = f"[dim]{ts}[/] {line}"
        self.logs.append(entry)
        if len(self.logs) > 500:
            self.logs = self.logs[-300:]

    def finish(self):
        self.running = False
        self.stop_requested = False


farm = FarmState()


# ── Farm Thread ──
def _run_farm(count: int, use_proxy: bool):
    import sys
    from io import StringIO
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    try:
        from .config import load_config
        from .email_generator import GeneratorEmailReader, get_available_domains
        from .proxy import ProxyRotator
        from .turnstile import TurnstileSolver
        from .__main__ import run_single_account

        cfg = load_config()
        domains = get_available_domains()
        farm.add_log(f"[green]Loaded {len(domains)} email domains[/green]")

        proxy_rotator = ProxyRotator([])
        if use_proxy:
            pool = cfg.get("proxy", {}).get("pool", [])
            if pool:
                proxy_rotator = ProxyRotator(pool)
                farm.add_log(f"[cyan]Proxy: {len(pool)} proxies[/cyan]")

        solver = TurnstileSolver(cfg)

        for i in range(count):
            if farm.stop_requested:
                farm.add_log("[yellow]Stopped by user[/yellow]")
                break
            farm.add_log(f"[bold]--- Account {i+1}/{count} ---[/bold]")
            try:
                email_reader = GeneratorEmailReader(solver._browser) if solver._browser else None
                result = run_single_account(
                    cfg=cfg, solver=solver, proxy_rotator=proxy_rotator,
                    email_reader=email_reader, pusher=None,
                    dry_run=False, email_mode='generator',
                )
            except Exception as e:
                result = {"success": False, "error": str(e), "email": "?"}

            farm.completed += 1
            if result.get("success"):
                farm.successful += 1
                farm.add_log(f"[green]SUCCESS:[/] {result.get('email', '?')}")
            else:
                farm.failed += 1
                farm.add_log(f"[red]FAILED:[/] {result.get('email', '?')} — {result.get('error', '?')[:80]}")

        farm.add_log(f"[bold]Done: {farm.successful}/{farm.total} successful[/bold]")
        farm.finish()
    except Exception as e:
        farm.add_log(f"[red]FATAL: {e}[/red]")
        farm.finish()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# ── Sidebar Widget ──
class Sidebar(Static):
    total = reactive(0)
    active = reactive(0)
    exhausted = reactive(0)
    errored = reactive(0)

    def render(self) -> str:
        running = "[green]● RUNNING[/]" if farm.running else "[dim]● IDLE[/]"
        return (
            f"[bold]GROKKIDDING[/]\n"
            f"[dim]by rapoi[/dim]\n"
            f"[link=https://github.com/rapoii]github.com/rapoii[/link]\n"
            f"{running}\n\n"
            f"[bold]Accounts[/]\n"
            f"  Total:      {self.total}\n"
            f"  [green]Active:[/]    {self.active}\n"
            f"  [yellow]Exhausted:[/] {self.exhausted}\n"
            f"  [red]Error:[/]     {self.errored}\n\n"
            f"[bold]Commands[/]\n"
            f"  farm <n>    Start farming\n"
            f"  stop        Stop farming\n"
            f"  accounts    Show accounts\n"
            f"  delete <id> Delete account\n"
            f"  renew [n]   Renew expired\n"
            f"  proxy       Toggle proxy\n"
            f"  settings    Edit config\n"
            f"  refresh     Refresh data\n"
            f"  help        Show help\n"
            f"  quit        Exit\n"
        )


# ── Main TUI ──
class GrokiddingTUI(App):
    TITLE = "Grokidding"
    SUB_TITLE = "by rapoi — Grok/xAI Farmer → 9Router"

    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 30;
        min-width: 25;
        height: 100%;
        background: $surface;
        padding: 1 2;
        border-right: tall $primary;
    }

    #main {
        width: 1fr;
        height: 100%;
    }

    #log-area {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
        background: $surface;
    }

    #input-area {
        height: 3;
        dock: bottom;
        padding: 0 1;
        background: $surface-darken-1;
    }

    #cmd-input {
        height: 3;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.cfg = _load_config()

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Sidebar(id="stats")
            with Vertical(id="main"):
                yield RichLog(id="log-area", markup=True, wrap=True, auto_scroll=True)
                with Container(id="input-area"):
                    yield Input(placeholder="Type a command... (help for list)", id="cmd-input")

    def on_mount(self) -> None:
        self._refresh_stats()
        self._log("[bold]Grokidding[/] [dim]by rapoi[/dim] — [link=https://github.com/rapoii]github.com/rapoii[/link]")
        self._log("Type [cyan]help[/] for commands.")
        self._log(f"Config: proxy={self.cfg.get('proxy',{}).get('mode','off')}, email=generator.email")
        self._log("")
        self.query_one("#cmd-input", Input).focus()
        # Auto-refresh stats every 10s
        self.set_interval(10, self._refresh_stats)
        # Auto-refresh logs every 1s
        self.set_interval(1, self._update_logs)

    def _log(self, text: str):
        log = self.query_one("#log-area", RichLog)
        log.write(text)

    def _update_logs(self):
        """Push new farm logs to the RichLog."""
        if not farm.logs:
            return
        log = self.query_one("#log-area", RichLog)
        # Only write logs we haven't written yet
        current_count = getattr(self, "_last_log_count", 0)
        if len(farm.logs) > current_count:
            for entry in farm.logs[current_count:]:
                log.write(entry)
            self._last_log_count = len(farm.logs)

    def _refresh_stats(self):
        accounts = load_accounts()
        stats = self.query_one("#stats", Sidebar)
        stats.total = len(accounts)
        stats.active = sum(1 for a in accounts if a["status"] == "active")
        stats.exhausted = sum(1 for a in accounts if a["status"] == "exhausted")
        stats.errored = sum(1 for a in accounts if a["status"] in ("error", "unknown"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        input_widget = self.query_one("#cmd-input", Input)
        input_widget.value = ""

        if not cmd:
            return

        parts = cmd.split()
        action = parts[0].lower()
        args = parts[1:]

        handler = getattr(self, f"_cmd_{action}", None)
        if handler:
            handler(args)
        else:
            self._log(f"[red]Unknown command:[/] {action}. Type [cyan]help[/] for list.")

    def _cmd_help(self, args):
        self._log("[bold]Commands:[/]")
        self._log("  [cyan]farm <n>[/]         — Start farming n accounts (default: 1)")
        self._log("  [cyan]stop[/]             — Stop current farming")
        self._log("  [cyan]accounts[/]         — List all accounts")
        self._log("  [cyan]delete <id/name>[/] — Delete account by ID or name")
        self._log("  [cyan]renew [n][/]         — Renew expired accounts (0=auto)")
        self._log("  [cyan]proxy[/]            — Show/toggle proxy mode")
        self._log("  [cyan]proxy socks5[/]     — Set proxy mode to socks5")
        self._log("  [cyan]proxy off[/]        — Disable proxy")
        self._log("  [cyan]proxy test[/]       — Test proxy connections")
        self._log("  [cyan]settings[/]         — Show current settings")
        self._log("  [cyan]refresh[/]          — Refresh account data")
        self._log("  [cyan]clear[/]            — Clear log area")
        self._log("  [cyan]quit[/]             — Exit Grokidding")
        self._log("")

    def _cmd_farm(self, args):
        if farm.running:
            self._log("[yellow]Farming already in progress! Use 'stop' first.[/yellow]")
            return
        count = int(args[0]) if args else 1
        if count < 1 or count > 100:
            self._log("[red]Count must be 1-100[/red]")
            return

        farm.reset(count)
        proxy_mode = self.cfg.get("proxy", {}).get("mode", "off")
        use_proxy = proxy_mode == "socks5"

        self._log(f"[green]Starting farm: {count} account(s), proxy={proxy_mode}[/green]")
        thread = threading.Thread(target=_run_farm, args=(count, use_proxy), daemon=True)
        thread.start()
        self._last_log_count = 0  # reset log counter

    def _cmd_stop(self, args):
        if farm.running:
            farm.stop_requested = True
            self._log("[yellow]Stop requested...[/yellow]")
        else:
            self._log("[dim]No farming in progress.[/]")

    def _cmd_accounts(self, args):
        accounts = load_accounts()
        if not accounts:
            self._log("[dim]No accounts found.[/]")
            return
        self._log(f"[bold]Accounts ({len(accounts)}):[/]")
        for a in accounts:
            color = {"active": "green", "exhausted": "yellow", "error": "red"}.get(a["status"], "dim")
            self._log(f"  [{color}]{a['status']:10}[/] {a['name']:25} {a['email']}")

    def _cmd_delete(self, args):
        if not args:
            self._log("[red]Usage: delete <name-or-id>[/red]")
            return
        target = " ".join(args)
        accounts = load_accounts()
        match = [a for a in accounts if target in a["name"] or target in a["id"][:8]]
        if not match:
            self._log(f"[red]No account matching '{target}'[/red]")
            return
        db_path = _get_router_db()
        if not db_path.exists():
            self._log("[red]9Router DB not found[/red]")
            return
        import sqlite3
        db = sqlite3.connect(str(db_path))
        for a in match:
            db.execute("DELETE FROM providerConnections WHERE id = ?", (a["id"],))
            self._log(f"[red]Deleted:[/] {a['name']} ({a['email']})")
        db.commit()
        db.close()
        self._refresh_stats()

    def _cmd_renew(self, args):
        accounts = load_accounts()
        expired = [a for a in accounts if a["status"] in ("expired", "exhausted")]
        if not expired:
            self._log("[yellow]No expired accounts found.[/yellow]")
            return
        count = int(args[0]) if args else len(expired)
        actual = min(count, len(expired))
        self._log(f"[yellow]Renewing {actual} expired accounts...[/yellow]")

        # Delete expired
        db_path = _get_router_db()
        if db_path.exists():
            import sqlite3
            db = sqlite3.connect(str(db_path))
            for a in expired[:actual]:
                db.execute("DELETE FROM providerConnections WHERE id = ?", (a["id"],))
                self._log(f"  Deleted: {a['name']}")
            db.commit()
            db.close()

        # Start farming replacements
        self._cmd_farm([str(actual)])

    def _cmd_proxy(self, args):
        if not args:
            mode = self.cfg.get("proxy", {}).get("mode", "off")
            pool = self.cfg.get("proxy", {}).get("pool", [])
            self._log(f"[bold]Proxy:[/] mode={mode}, pool={len(pool)} proxies")
            return
        action = args[0].lower()
        if action in ("off", "socks5", "adb"):
            self.cfg.setdefault("proxy", {})["mode"] = action
            _save_config(self.cfg)
            self._log(f"[green]Proxy mode set to: {action}[/green]")
        elif action == "test":
            self._log("[dim]Testing proxies...[/]")
            pool = self.cfg.get("proxy", {}).get("pool", [])
            if not pool:
                self._log("[yellow]No proxies in pool.[/yellow]")
                return
            thread = threading.Thread(target=self._test_proxies, args=(pool,), daemon=True)
            thread.start()
        else:
            self._log(f"[red]Unknown proxy action: {action}[/red]")

    def _test_proxies(self, pool):
        import socks, socket, re
        for p in pool:
            port = p.split(":")[-1]
            try:
                m = re.match(r"socks5://([^:]+):([^@]+)@([^:]+):(\d+)", p)
                if not m:
                    self._log(f"  Port {port}: cannot parse")
                    continue
                user, pwd, host, port_num = m.groups()
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, host, int(port_num), username=user, password=pwd)
                s.settimeout(10)
                s.connect(("httpbin.org", 80))
                s.sendall(b"GET /ip HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n")
                resp = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    resp += chunk
                s.close()
                ip = "unknown"
                body = resp.decode()
                if '"origin"' in body:
                    ip = body.split('"origin": "')[1].split('"')[0]
                self._log(f"  Port {port}: [green]OK[/] -> {ip}")
            except Exception as e:
                self._log(f"  Port {port}: [red]FAIL[/] — {str(e)[:50]}")
            time.sleep(0.3)

    def _cmd_settings(self, args):
        cfg = _load_config()
        self._log("[bold]Current Settings:[/]")
        self._log(f"  9Router URL:  {cfg.get('ninrouter',{}).get('base_url','?')}")
        self._log(f"  Proxy mode:   {cfg.get('proxy',{}).get('mode','off')}")
        self._log(f"  Proxy pool:   {len(cfg.get('proxy',{}).get('pool',[]))} proxies")
        self._log(f"  Email mode:   {cfg.get('email',{}).get('mode','generator')}")
        self._log(f"  Turnstile:    max_retries={cfg.get('turnstile',{}).get('max_retries',15)}")
        self._log(f"  Password len: {cfg.get('signup',{}).get('password_length',16)}")
        self._log("")

    def _cmd_refresh(self, args):
        self._refresh_stats()
        self._log("[green]Refreshed.[/green]")

    def _cmd_clear(self, args):
        log = self.query_one("#log-area", RichLog)
        log.clear()

    def _cmd_quit(self, args):
        if farm.running:
            farm.stop_requested = True
        self.exit()


if __name__ == "__main__":
    app = GrokiddingTUI()
    app.run()
