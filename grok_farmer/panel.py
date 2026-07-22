"""Grokidding — Web Panel Server.

FastAPI backend + WebSocket for real-time log streaming.
Serves a single-file dashboard at /.
"""
import asyncio
import io
import json
import re
import sqlite3
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

# ── Project paths ──
PROJECT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ── Farming state ──
class FarmState:
    """Thread-safe farming session state."""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.stop_requested = False
        self.total = 0
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.current_step = "idle"
        self.current_email = ""
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.logs: list[str] = []
        self._ws_clients: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def reset(self, count: int):
        with self.lock:
            self.running = True
            self.stop_requested = False
            self.total = count
            self.completed = 0
            self.successful = 0
            self.failed = 0
            self.current_step = "initializing"
            self.current_email = ""
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.finished_at = None
            self.logs.clear()

    def finish(self):
        with self.lock:
            self.running = False
            self.stop_requested = False
            self.finished_at = datetime.now(timezone.utc).isoformat()
            self.current_step = "idle"

    def add_log(self, line: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = f"[{ts}] {line}"
        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]
        # Broadcast to WebSocket clients
        self._try_broadcast_log(entry)

    def broadcast_progress(self):
        """Broadcast current farm state to all WebSocket clients."""
        self._try_broadcast_progress()

    def broadcast_quota(self):
        """Fetch fresh quota and broadcast to all WebSocket clients."""
        try:
            data = _fetch_quota_sync()
            now = time.time()
            with _quota_lock:
                _quota_cache["data"] = data
                _quota_cache["ts"] = now
            if self._loop and self._ws_clients:
                msg = json.dumps({"type": "quota", "data": data})
                asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)
        except Exception:
            pass

    def _try_broadcast_log(self, entry: str):
        if self._loop and self._ws_clients:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._broadcast(json.dumps({"type": "log", "line": entry})), self._loop
                )
            except Exception:
                pass

    def _try_broadcast_progress(self):
        if self._loop and self._ws_clients:
            try:
                data = json.dumps({"type": "progress", "data": self.snapshot()})
                asyncio.run_coroutine_threadsafe(
                    self._broadcast(data), self._loop
                )
            except Exception:
                pass

    async def _broadcast(self, msg: str):
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "running": self.running,
                "total": self.total,
                "completed": self.completed,
                "successful": self.successful,
                "failed": self.failed,
                "current_step": self.current_step,
                "current_email": self.current_email,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "progress": round(self.completed / self.total * 100, 1) if self.total > 0 else 0,
            }


state = FarmState()

# Quota cache
_quota_cache = {"data": None, "ts": 0.0}
_quota_lock = threading.Lock()
QUOTA_CACHE_TTL = 30  # seconds


def _fetch_quota_sync() -> dict:
    """Blocking quota check — run in thread to avoid blocking event loop."""
    connections = _get_all_grok_connections()
    total_limit = 0
    total_remaining = 0
    total_used = 0
    accounts = []

    for conn in connections:
        if not conn["token"]:
            accounts.append({"name": conn["name"], "email": conn["email"], "status": "no_token", "limit": 0, "remaining": 0, "used": 0})
            continue

        try:
            body = json.dumps({"model": "grok-4.5", "input": "ping", "max_output_tokens": 1}).encode()
            req = urllib.request.Request(
                "https://cli-chat-proxy.grok.com/v1/responses",
                data=body, method="POST",
            )
            req.add_header("Authorization", f"Bearer {conn['token']}")
            for k, v in GROK_CLI_HEADERS.items():
                req.add_header(k, v)
            req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=10)
            limit = int(resp.headers.get("x-ratelimit-limit-tokens", "1000000"))
            remaining = int(resp.headers.get("x-ratelimit-remaining-tokens", "0"))
            used = limit - remaining
            total_limit += limit
            total_remaining += remaining
            total_used += used
            accounts.append({"name": conn["name"], "email": conn["email"], "status": "active", "limit": limit, "remaining": remaining, "used": used})
        except urllib.error.HTTPError as e:
            if e.code == 429:
                err_body = e.read().decode("utf-8", "replace")
                usage, limit = 0, 1000000
                m = re.search(r"queries \(actual/limit\):\s*(\d+)/(\d+)", err_body)
                if m:
                    usage, limit = int(m.group(1)), int(m.group(2))
                else:
                    m = re.search(r"tokens \(actual/limit\):\s*(\d+)/(\d+)", err_body)
                    if m:
                        usage, limit = int(m.group(1)), int(m.group(2))
                remaining = max(0, limit - usage)
                total_limit += limit
                total_remaining += remaining
                total_used += usage
                accounts.append({"name": conn["name"], "email": conn["email"], "status": "expired", "limit": limit, "remaining": remaining, "used": usage})
            else:
                accounts.append({"name": conn["name"], "email": conn["email"], "status": "error", "limit": 0, "remaining": 0, "used": 0})
        except Exception:
            accounts.append({"name": conn["name"], "email": conn["email"], "status": "error", "limit": 0, "remaining": 0, "used": 0})

    return {
        "total_accounts": len(connections),
        "total_limit": total_limit,
        "total_remaining": total_remaining,
        "total_used": total_used,
        "accounts": accounts,
    }

# ── App ──
app = FastAPI(title="Grokidding Panel")


class FarmRequest(BaseModel):
    count: int = 1
    proxy: bool = True
    dry_run: bool = False



# ── 9Router Integration ──

ROUTER_DB = Path("C:/Users/Rafi/AppData/Roaming/9router/db/data.sqlite")


def _load_accounts() -> list[dict]:
    """Load grok accounts from 9Router SQLite database."""
    if not ROUTER_DB.exists():
        return []
    try:
        import sqlite3 as _sql
        db = _sql.connect(f"file:{ROUTER_DB}?immutable=1", uri=True)
        db.row_factory = _sql.Row
        rows = db.execute("""
            SELECT id, name, email, isActive, data, provider, authType,
                   priority, createdAt, updatedAt
            FROM providerConnections
            WHERE provider LIKE '%grok%' AND isActive=1
            ORDER BY createdAt DESC
        """).fetchall()
        accounts = []
        for row in rows:
            data = json.loads(row["data"]) if row["data"] else {}
            # Determine status
            error_code = data.get("errorCode")
            test_status = data.get("testStatus", "unknown")
            is_active = bool(row["isActive"])

            if error_code == 429:
                status = "exhausted"
            elif error_code:
                status = "error"
            elif test_status == "success":
                status = "active"
            elif test_status == "unavailable":
                status = "unavailable"
            else:
                status = "unknown"

            accounts.append({
                "id": row["id"],
                "email": row["email"] or data.get("email", "?"),
                "name": row["name"] or "?",
                "active": is_active,
                "status": status,
                "error_code": error_code,
                "last_error": data.get("lastError", ""),
                "last_error_at": data.get("lastErrorAt", ""),
                "model_lock": [k.replace("modelLock_", "") for k in data if k.startswith("modelLock_")],
                "backoff_level": data.get("backoffLevel", 0),
                "auth_type": row["authType"] or "?",
                "created_at": row["createdAt"] or "",
                "updated_at": row["updatedAt"] or "",
            })
        db.close()
        return accounts
    except Exception as e:
        return [{"error": str(e)}]


def _delete_router_account(account_id: str) -> bool:
    """Delete (deactivate) an account from 9Router SQLite."""
    try:
        import sqlite3 as _sql
        db = _sql.connect(str(ROUTER_DB))
        cur = db.execute(
            "UPDATE providerConnections SET isActive=0 WHERE id=? AND provider LIKE '%grok%'",
            (account_id,)
        )
        db.commit()
        deleted = cur.rowcount > 0
        db.close()
        return deleted
    except Exception:
        return False


def _read_logs(limit: int = 200) -> list[str]:
    d = PROJECT_DIR / "data" / "logs"
    if not d.exists():
        return []
    lines = []
    for f in sorted(d.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            lines.extend(f.read_text(encoding="utf-8").splitlines())
        except Exception:
            pass
    return lines[-limit:]


# ── API Endpoints ──

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/settings")
async def get_settings():
    """Return current config.json (sensitive values masked)."""
    try:
        cfg_path = PROJECT_DIR / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        # Mask sensitive values
        safe = json.loads(json.dumps(cfg))  # deep copy
        if safe.get("ninrouter", {}).get("password"):
            safe["ninrouter"]["password"] = "***"
        if safe.get("email", {}).get("password"):
            safe["email"]["password"] = "***"
        # Mask proxy credentials in pool URLs
        masked_pool = []
        for url in safe.get("proxy", {}).get("pool", []):
            masked_pool.append(_mask_proxy_url(url))
        if "proxy" in safe and "pool" in safe["proxy"]:
            safe["proxy"]["pool_display"] = masked_pool
        return JSONResponse(safe)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def _mask_proxy_url(url: str) -> str:
    """Mask password in proxy URLs (socks5/http/https/socks4://user:pass@host:port)."""
    import re as _re
    return _re.sub(r"://([^:]+):([^@]+)@", lambda m: f"://{m.group(1)}:***@", url)


@app.post("/api/settings")
async def update_settings(req: Request):
    """Update config.json with partial data. Sensitive fields skipped if value is '***'."""
    try:
        cfg_path = PROJECT_DIR / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        body = await req.json()

        # Deep merge without overwriting with '***'
        def merge(target, source):
            for k, v in source.items():
                if isinstance(v, dict) and isinstance(target.get(k), dict):
                    merge(target[k], v)
                elif v != "***":  # skip masked values
                    target[k] = v

        merge(cfg, body)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/proxy/test")
async def test_proxy(req: Request):
    """Test proxy connectivity by fetching httpbin through the proxy."""
    body = await req.json()
    proxy_url = body.get("proxy", "")
    test_type = body.get("type", "socks5")

    # ADB test
    if test_type == "adb":
        adb_path = body.get("adb_path", "adb")
        serial = body.get("serial", "")
        try:
            import subprocess
            cmd = [adb_path]
            if serial:
                cmd += ["-s", serial]
            cmd += ["devices"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if serial and serial in r.stdout:
                # Get IP
                cmd_ip = [adb_path]
                if serial:
                    cmd_ip += ["-s", serial]
                cmd_ip += ["shell", "ip", "route", "get", "1.1.1.1"]
                ip_r = subprocess.run(cmd_ip, capture_output=True, text=True, timeout=10)
                ip = "?"
                if ip_r.returncode == 0:
                    parts = ip_r.stdout.strip().split()
                    if "src" in parts:
                        idx = parts.index("src")
                        if idx + 1 < len(parts):
                            ip = parts[idx + 1]
                return JSONResponse({"ok": True, "device": f"{serial} (IP: {ip})"})
            return JSONResponse({"ok": False, "error": f"Device {serial} not found. Available: {r.stdout.strip()}"})
        except FileNotFoundError:
            return JSONResponse({"ok": False, "error": f"ADB not found at: {adb_path}"})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)[:200]})

    # SOCKS5 proxy test
    # Proxy test (supports socks5/socks4/http/https)
    if not proxy_url:
        return JSONResponse({"ok": False, "error": "No proxy URL provided"})
    # Detect proxy type
    from .proxy import get_proxy_type
    proxy_type = get_proxy_type(proxy_url)
    if proxy_type == "unknown":
        return JSONResponse({"ok": False, "error": "Invalid proxy format. Supported: socks5://, socks4://, http://, https://"})

    try:
        import requests
        proxies = {"http": proxy_url, "https": proxy_url}
        r = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=15)
        if r.status_code == 200:
            ip = r.json().get("origin", "unknown")
            return JSONResponse({"ok": True, "ip": ip, "type": proxy_type})
        return JSONResponse({"ok": False, "error": f"HTTP {r.status_code}: {r.text[:100]}"})
    except ImportError:
        # Fallback to PySocks for SOCKS proxies
        try:
            import re as _re
            import socks
            import socket
            m = _re.match(r"socks[45]://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)", proxy_url)
            if not m:
                return JSONResponse({"ok": False, "error": "Cannot parse proxy URL"})
            user, pwd, host, port = m.group(1) or "", m.group(2) or "", m.group(3), int(m.group(4))
            s = socks.socksocket()
            sock_type = socks.SOCKS5 if proxy_type == "socks5" else socks.SOCKS4
            s.set_proxy(sock_type, host, port, username=user or None, password=pwd or None)
            s.settimeout(10)
            s.connect(("httpbin.org", 80))
            s.sendall(b"GET /ip HTTP/1.1\r\nHost: httpbin.org\r\n\r\n")
            resp = s.recv(4096).decode()
            s.close()
            if "200 OK" in resp:
                import json as _json
                ip = _json.loads(resp.split("\r\n\r\n", 1)[1]).get("origin", "unknown")
                return JSONResponse({"ok": True, "ip": ip, "type": proxy_type})
            return JSONResponse({"ok": False, "error": f"HTTP {resp[:100]}"})
        except ImportError:
            return JSONResponse({"ok": False, "error": "Install 'requests' or 'PySocks' to test proxies"})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)[:200]})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:200]})


@app.get("/api/accounts")
async def get_accounts():
    return JSONResponse(_load_accounts())


@app.get("/api/stats")
async def get_stats():
    accounts = _load_accounts()
    total = len(accounts)
    active = sum(1 for a in accounts if a.get("active") and a.get("status") == "active")
    exhausted = sum(1 for a in accounts if a.get("status") == "exhausted")
    errored = sum(1 for a in accounts if a.get("status") in ("error", "unavailable"))
    rate = round(active / total * 100, 1) if total > 0 else 0
    return JSONResponse({
        "total": total,
        "active": active,
        "exhausted": exhausted,
        "errored": errored,
        "rate": rate,
    })


@app.post("/api/farm")
async def start_farm(req: FarmRequest):
    if state.running:
        return JSONResponse({"error": "Farming already in progress"}, status_code=409)
    if req.count < 1 or req.count > 100:
        return JSONResponse({"error": "Count must be 1-100"}, status_code=400)

    state.reset(req.count)
    state.add_log(f"Starting farm: {req.count} account(s), proxy={'on' if req.proxy else 'off'}, dry_run={req.dry_run}")
    state.broadcast_progress()

    thread = threading.Thread(target=_run_farm, args=(req.count, req.proxy, req.dry_run), daemon=True)
    thread.start()

    return JSONResponse({"started": True, "count": req.count})


@app.post("/api/stop")
async def stop_farm():
    if not state.running:
        return JSONResponse({"error": "No farming in progress"}, status_code=400)
    state.stop_requested = True
    state.add_log("Stop requested - finishing current account...")
    return JSONResponse({"stopped": True})


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str):
    if _delete_router_account(account_id):
        return JSONResponse({"deleted": account_id})
    return JSONResponse({"error": "Not found or delete failed"}, status_code=404)


@app.get("/api/logs")
async def get_logs(limit: int = 200):
    file_logs = _read_logs(limit)
    with state.lock:
        panel_logs = state.logs[-100:]
    return JSONResponse({"logs": file_logs, "panel_logs": panel_logs})


@app.get("/api/status")
async def get_status():
    return JSONResponse(state.snapshot())


# ── Quota / Renew ──

GROK_CLI_HEADERS = {
    "User-Agent": "grok-shell/0.2.99 (linux; x86_64)",
    "x-grok-client-identifier": "grok-shell",
    "x-grok-client-version": "0.2.99",
}


def _get_router_db_path() -> str:
    from .config import load_config
    cfg = load_config()
    return cfg["ninrouter"].get("db_path", "")


def _check_single_connection(token: str) -> dict:
    """Test a single Grok CLI connection. Returns {status, usage, limit, error}."""
    try:
        req = urllib.request.Request(
            "https://cli-chat-proxy.grok.com/v1/responses",
            data=json.dumps({
                "model": "grok-4.5",
                "input": [{"role": "user", "content": "hi"}],
                "max_output_tokens": 1,
                "stream": False,
            }).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                **GROK_CLI_HEADERS,
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=20)
        resp.read()
        return {"status": "active", "usage": None, "limit": None, "error": None}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 429:
            # Parse usage from error message
            usage, limit = None, None
            # Try "queries (actual/limit)" first (free tier)
            if "queries (actual/limit):" in body:
                try:
                    part = body.split("queries (actual/limit):")[1].split(".")[0].strip()
                    actual, lim = part.split("/")
                    usage, limit = int(actual.strip()), int(lim.strip())
                except Exception:
                    pass
            elif "tokens (actual/limit):" in body:
                try:
                    part = body.split("tokens (actual/limit):")[1].split(".")[0].strip()
                    actual, lim = part.split("/")
                    usage, limit = int(actual.strip()), int(lim.strip())
                except Exception:
                    pass
            return {"status": "expired", "usage": usage, "limit": limit, "error": body[:200]}
        return {"status": "error", "usage": None, "limit": None, "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"status": "error", "usage": None, "limit": None, "error": str(e)[:200]}


def _get_all_grok_connections() -> list[dict]:
    """Read all grok-cli connections from 9Router SQLite, enriched with local account data."""
    db_path = _get_router_db_path()
    if not db_path or not Path(db_path).exists():
        return []
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, name, email, isActive, data FROM providerConnections WHERE provider = 'grok-cli'"
    ).fetchall()
    db.close()

    # Build lookup from local account files (match by connection ID)
    from .config import load_config as _lc
    _cfg = _lc()
    local_accounts = {}
    accounts_dir = Path(_cfg.get("output", {}).get("accounts_dir", "data/accounts/"))
    if accounts_dir.exists():
        for f in accounts_dir.glob("*.json"):
            try:
                acct = json.loads(f.read_text(encoding="utf-8"))
                push = acct.get("steps", {}).get("push", {}).get("connection", {})
                if push.get("id"):
                    local_accounts[push["id"]] = {
                        "email": acct.get("email", ""),
                        "password": acct.get("password", ""),
                        "file": str(f),
                    }
            except Exception:
                continue

    result = []
    for r in rows:
        d = json.loads(r["data"]) if r["data"] else {}
        conn_id = r["id"]
        local = local_accounts.get(conn_id, {})
        result.append({
            "id": conn_id,
            "name": r["name"] or "",
            "email": r["email"] or d.get("providerSpecificData", {}).get("email", "") or local.get("email", ""),
            "password": local.get("password", ""),
            "isActive": bool(r["isActive"]),
            "token": d.get("accessToken", ""),
        })
    return result


def _delete_xai_account(email: str, password: str) -> dict:
    """Delete an x.ai account via DrissionPage browser automation.
    Returns {"success": bool, "error": str|None}.
    """
    if not email or not password:
        return {"success": False, "error": "Missing email or password"}

    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
    except ImportError:
        return {"success": False, "error": "DrissionPage not installed"}

    page = None
    try:
        opts = ChromiumOptions()
        opts.set_argument("--window-size=1280,900")
        opts.set_argument("--disable-blink-features=AutomationControlled")
        page = ChromiumPage(opts)

        # Step 1: Sign in
        page.get("https://accounts.x.ai/sign-in")
        time.sleep(3)

        # Accept cookies if present
        try:
            accept_btn = page.ele("text:Accept all", timeout=3)
            if accept_btn:
                accept_btn.click(by_js=True)
                time.sleep(1)
        except Exception:
            pass

        # Click "Sign in with email"
        try:
            email_btn = page.ele("text:Sign in with email", timeout=5)
            if email_btn:
                email_btn.click(by_js=True)
                time.sleep(2)
        except Exception:
            pass

        # Fill email
        email_input = page.ele("tag:input@@type=email", timeout=5) or page.ele("tag:input@@placeholder=*email*", timeout=3)
        if not email_input:
            return {"success": False, "error": "Cannot find email input"}
        email_input.clear()
        email_input.input(email)
        time.sleep(0.5)

        # Click Continue/Sign in
        try:
            continue_btn = page.ele("text:Continue", timeout=3) or page.ele("text:Sign in", timeout=3)
            if continue_btn:
                continue_btn.click(by_js=True)
                time.sleep(3)
        except Exception:
            pass

        # Fill password
        pw_input = page.ele("tag:input@@type=password", timeout=5)
        if not pw_input:
            # Maybe already logged in or different flow
            page.get("https://accounts.x.ai/settings")
            time.sleep(3)
        else:
            pw_input.clear()
            pw_input.input(password)
            time.sleep(0.5)
            try:
                sign_btn = page.ele("text:Sign in", timeout=3) or page.ele("text:Continue", timeout=3)
                if sign_btn:
                    sign_btn.click(by_js=True)
                    time.sleep(5)
            except Exception:
                pass

        # Step 2: Navigate to settings
        page.get("https://accounts.x.ai/settings")
        time.sleep(3)

        # Step 3: Find and click Delete Account
        delete_btn = page.ele("text:Delete account", timeout=5) or page.ele("text:Delete Account", timeout=3)
        if not delete_btn:
            # Try grok.com settings
            page.get("https://grok.com/settings")
            time.sleep(3)
            delete_btn = page.ele("text:Delete account", timeout=5) or page.ele("text:Delete Account", timeout=3)

        if not delete_btn:
            return {"success": False, "error": "Cannot find Delete Account button"}

        delete_btn.click(by_js=True)
        time.sleep(2)

        # Step 4: Confirm deletion
        confirm_btn = (
            page.ele("text:Yes, delete", timeout=5) or
            page.ele("text:Confirm", timeout=3) or
            page.ele("text:Delete", timeout=3) or
            page.ele("tag:button@@text()*Delete", timeout=3)
        )
        if confirm_btn:
            confirm_btn.click(by_js=True)
            time.sleep(3)

        # Check if redirected to sign-out or login = success
        cur_url = page.url
        if "sign-in" in cur_url or "sign-up" in cur_url or "login" in cur_url or cur_url == "https://accounts.x.ai/":
            return {"success": True, "error": None}

        # Might have a confirmation page requiring text input
        try:
            confirm_input = page.ele("tag:input@@placeholder=*delete*", timeout=3) or page.ele("tag:input@@placeholder=*type*", timeout=3)
            if confirm_input:
                confirm_input.clear()
                confirm_input.input("delete")
                time.sleep(0.5)
                final_btn = page.ele("text:Delete", timeout=3)
                if final_btn:
                    final_btn.click(by_js=True)
                    time.sleep(3)
                    return {"success": True, "error": None}
        except Exception:
            pass

        return {"success": True, "error": None}  # Assume success if no error

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
    finally:
        if page:
            try:
                page.quit()
            except Exception:
                pass


def _delete_connection(conn_id: str) -> bool:
    """Delete a connection from 9Router SQLite."""
    db_path = _get_router_db_path()
    if not db_path or not Path(db_path).exists():
        return False
    db = sqlite3.connect(db_path)
    db.execute("DELETE FROM providerConnections WHERE id = ?", (conn_id,))
    db.commit()
    db.close()
    return True


class RenewRequest(BaseModel):
    count: int = 0  # 0 = auto (match expired count)
    proxy: bool = True


@app.get("/api/check-quota")
async def check_quota():
    """Check quota status of all grok-cli connections in 9Router."""
    connections = _get_all_grok_connections()
    if not connections:
        return JSONResponse({"error": "No grok-cli connections found or DB not accessible"}, status_code=404)

    results = []
    expired_count = 0
    active_count = 0

    for conn in connections:
        if not conn["token"]:
            results.append({**conn, "quota": {"status": "no_token", "usage": None, "limit": None, "error": "No access token"}})
            continue

        quota = _check_single_connection(conn["token"])
        if quota["status"] == "expired":
            expired_count += 1
        elif quota["status"] == "active":
            active_count += 1

        results.append({
            "id": conn["id"],
            "name": conn["name"],
            "email": conn["email"],
            "isActive": conn["isActive"],
            "quota": quota,
        })

    return JSONResponse({
        "total": len(connections),
        "active": active_count,
        "expired": expired_count,
        "connections": results,
    })


@app.post("/api/renew")
async def renew_accounts(req: RenewRequest):
    """Delete expired accounts and farm replacements."""
    if state.running:
        return JSONResponse({"error": "Farming already in progress"}, status_code=409)

    # Step 1: Check quota to find expired
    connections = _get_all_grok_connections()
    expired = []
    for conn in connections:
        if not conn["token"]:
            continue
        quota = _check_single_connection(conn["token"])
        if quota["status"] == "expired":
            expired.append(conn)

    if not expired:
        return JSONResponse({"error": "No expired accounts found"}, status_code=400)

    count = req.count if req.count > 0 else len(expired)

    # Step 2: Delete expired connections from 9Router + x.ai
    deleted_router = []
    deleted_xai = []
    for conn in expired[:count]:
        name = conn["name"] or conn["id"][:12]

        # Delete from x.ai first (browser automation)
        if conn.get("email") and conn.get("password"):
            state.add_log(f"[RENEW] Deleting x.ai account: {conn['email']}...")
            result = _delete_xai_account(conn["email"], conn["password"])
            if result["success"]:
                deleted_xai.append(conn["email"])
                state.add_log(f"[RENEW] x.ai account deleted: {conn['email']}")
            else:
                state.add_log(f"[RENEW] x.ai delete failed for {conn['email']}: {result['error']}")
        else:
            state.add_log(f"[RENEW] No credentials for {name}, skipping x.ai delete")

        # Delete from 9Router
        if _delete_connection(conn["id"]):
            deleted_router.append(name)

    state.add_log(f"[RENEW] Deleted {len(deleted_router)} from 9Router: {', '.join(deleted_router)}")
    if deleted_xai:
        state.add_log(f"[RENEW] Deleted {len(deleted_xai)} from x.ai: {', '.join(deleted_xai)}")

    # Step 3: Farm replacements
    state.reset(count)
    state.add_log(f"[RENEW] Farming {count} replacement account(s)...")

    thread = threading.Thread(target=_run_farm, args=(count, req.proxy, False), daemon=True)
    thread.start()

    return JSONResponse({
        "started": True,
        "deleted_router": deleted_router,
        "deleted_xai": deleted_xai,
        "farming_count": count,
    })


# ── Quota & Request Logging ──

import collections
import threading as _threading

_request_log: collections.deque = collections.deque(maxlen=200)
_request_log_lock = _threading.Lock()

GROK_CLI_HEADERS = {
    "User-Agent": "grok-shell/0.2.99 (linux; x86_64)",
    "x-grok-client-identifier": "grok-shell",
    "x-grok-client-version": "0.2.99",
}


def _get_best_token() -> tuple[str, str]:
    """Pick the connection with most remaining quota. Returns (token, conn_name)."""
    connections = _get_all_grok_connections()
    best_token, best_name, best_remaining = "", "", -1
    for conn in connections:
        if not conn["token"]:
            continue
        # Quick check: use ratelimit header from a lightweight probe
        try:
            body = json.dumps({"model": "grok-4.5", "input": "ping", "max_output_tokens": 1}).encode()
            req = urllib.request.Request(
                "https://cli-chat-proxy.grok.com/v1/responses",
                data=body, method="POST",
            )
            req.add_header("Authorization", f"Bearer {conn['token']}")
            for k, v in GROK_CLI_HEADERS.items():
                req.add_header(k, v)
            req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=10)
            remaining = int(resp.headers.get("x-ratelimit-remaining-tokens", "0"))
            if remaining > best_remaining:
                best_remaining = remaining
                best_token = conn["token"]
                best_name = conn["name"]
        except urllib.error.HTTPError as e:
            # 429 = exhausted, skip
            if e.code == 429:
                continue
        except Exception:
            continue
    return best_token, best_name


@app.get("/api/quota")
async def get_quota(force: bool = False):
    """Return aggregated quota — cached for 30s, non-blocking."""
    now = time.time()
    with _quota_lock:
        if not force and _quota_cache["data"] and (now - _quota_cache["ts"]) < QUOTA_CACHE_TTL:
            cached = dict(_quota_cache["data"])
            cached["cached"] = True
            return JSONResponse(cached)

    # Run blocking Grok API calls in thread pool
    data = await asyncio.to_thread(_fetch_quota_sync)
    data["cached"] = False
    data["ts"] = now

    with _quota_lock:
        _quota_cache["data"] = data
        _quota_cache["ts"] = now

    return JSONResponse(data)


@app.get("/api/request-log")
async def get_request_log(limit: int = 50):
    """Return recent proxied request logs."""
    with _request_log_lock:
        logs = list(_request_log)[-limit:]
    return JSONResponse({"logs": logs, "total": len(logs)})


@app.post("/v1/responses")
async def proxy_grok_responses(request: Request):
    """Proxy endpoint for Grok CLI — forwards to cli-chat-proxy.grok.com and logs token usage.
    Use this as the base URL in your Grok CLI config to get real-time request logging.
    """
    # Pick best available token
    token, conn_name = _get_best_token()
    if not token:
        return JSONResponse({"error": "No available grok-cli connections (all 429 or error)"}, status_code=503)

    # Read request body
    body = await request.body()
    try:
        req_json = json.loads(body) if body else {}
    except Exception:
        req_json = {}

    model = req_json.get("model", "grok-4.5")
    input_text = ""
    if isinstance(req_json.get("input"), str):
        input_text = req_json["input"][:100]
    elif isinstance(req_json.get("input"), list):
        for item in req_json["input"]:
            if isinstance(item, dict) and item.get("content"):
                input_text = str(item["content"])[:100]
                break

    # Forward to Grok CLI
    start_time = time.time()
    try:
        proxy_req = urllib.request.Request(
            "https://cli-chat-proxy.grok.com/v1/responses",
            data=body, method="POST",
        )
        proxy_req.add_header("Authorization", f"Bearer {token}")
        for k, v in GROK_CLI_HEADERS.items():
            proxy_req.add_header(k, v)
        proxy_req.add_header("Content-Type", "application/json")

        proxy_resp = urllib.request.urlopen(proxy_req, timeout=60)
        resp_body = proxy_resp.read()
        elapsed = round(time.time() - start_time, 2)

        # Parse usage from response
        try:
            resp_json = json.loads(resp_body)
            usage = resp_json.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cached_tokens = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
            reasoning_tokens = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            status = resp_json.get("status", "completed")
        except Exception:
            input_tokens = output_tokens = cached_tokens = reasoning_tokens = total_tokens = 0
            status = "unknown"

        # Get remaining quota from headers
        remaining = int(proxy_resp.headers.get("x-ratelimit-remaining-tokens", "0"))
        limit = int(proxy_resp.headers.get("x-ratelimit-limit-tokens", "1000000"))

        # Log request
        log_entry = {
            "time": time.strftime("%H:%M:%S"),
            "conn": conn_name,
            "model": model,
            "input_preview": input_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": total_tokens,
            "remaining": remaining,
            "limit": limit,
            "elapsed": elapsed,
            "status": status,
        }
        with _request_log_lock:
            _request_log.append(log_entry)

        # Broadcast to WebSocket clients
        ws_msg = json.dumps({"type": "request_log", "data": log_entry})
        for ws_client in list(state._ws_clients):
            try:
                await ws_client.send_text(ws_msg)
            except Exception:
                pass

        # Return response
        return Response(
            content=resp_body,
            status_code=proxy_resp.status,
            headers={"Content-Type": "application/json"},
        )

    except urllib.error.HTTPError as e:
        elapsed = round(time.time() - start_time, 2)
        err_body = e.read().decode("utf-8", "replace")

        log_entry = {
            "time": time.strftime("%H:%M:%S"),
            "conn": conn_name,
            "model": model,
            "input_preview": input_text,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "remaining": 0,
            "limit": 0,
            "elapsed": elapsed,
            "status": f"error_{e.code}",
        }
        with _request_log_lock:
            _request_log.append(log_entry)

        return Response(content=err_body, status_code=e.code, headers={"Content-Type": "application/json"})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state._ws_clients.add(ws)
    if not state._loop:
        state._loop = asyncio.get_running_loop()
    try:
        # Send recent logs on connect
        with state.lock:
            recent = state.logs[-50:]
        for line in recent:
            await ws.send_text(json.dumps({"type": "log", "line": line}))
        # Keep connection alive
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state._ws_clients.discard(ws)


# ── Farming Worker ──

class _StdoutCapture(io.TextIOBase):
    """Captures print() output into FarmState logs."""

    def write(self, s):
        if not s.strip():
            return len(s)
        # Buffer newlines
        if hasattr(self, '_buf'):
            self._buf += s
        else:
            self._buf = s
        if '\n' in self._buf:
            parts = self._buf.split('\n')
            for part in parts[:-1]:
                stripped = part.rstrip()
                if stripped:
                    state.add_log(stripped)
            self._buf = parts[-1]
        return len(s)

    def flush(self):
        pass


def _run_farm(count: int, use_proxy: bool, dry_run: bool):
    """Background thread that runs the farming loop."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    capture = _StdoutCapture()
    sys.stdout = capture
    sys.stderr = capture

    try:
        from .config import load_config
        from .email_reader import IMAPOtpReader
        from .proxy import ProxyRotator
        from .router_push import RouterPusher
        from .turnstile import TurnstileSolver
        from .__main__ import run_single_account

        cfg = load_config()
        ecfg = cfg["email"]

        proxy_rotator = ProxyRotator(
            pool=[] if not use_proxy else cfg["proxy"]["pool"],
            mode=cfg["proxy"].get("mode", "socks5"),
            adb_config=cfg["proxy"].get("adb"),
        )

        email_reader = IMAPOtpReader(
            ecfg["imap_host"], ecfg["imap_port"], ecfg["email"], ecfg["password"]
        )
        email_reader.connect()

        pusher = RouterPusher(
            cfg["ninrouter"]["base_url"], cfg["ninrouter"]["password"],
            cfg["ninrouter"].get("db_path"), debug=True,
        )
        pusher.login()

        tcfg = cfg["turnstile"]
        solver = TurnstileSolver(
            extension_path=tcfg.get("extension_path", "turnstile_patch/"),
            max_retries=tcfg.get("max_retries", 15),
            timeout=tcfg.get("timeout", 60), debug=True,
        )

        for i in range(count):
            state.current_step = f"farming {i + 1}/{count}"
            state.completed = i
            state.add_log(f"--- Account {i + 1}/{count} ---")
            state.broadcast_progress()

            if state.stop_requested:
                state.add_log(f"Stopped by user after {i} accounts.")
                state.broadcast_progress()
                break

            result = run_single_account(
                cfg, solver, proxy_rotator, email_reader, pusher, dry_run
            )

            if result.get("success"):
                state.successful += 1
                state.add_log(f"SUCCESS: {result.get('email', '?')}")
            else:
                state.failed += 1
                state.add_log(f"FAILED: {result.get('email', '?')} - {result.get('error', '?')}")

            state.current_email = result.get("email", "")
            state.broadcast_progress()

            if i < count - 1:
                solver.close()
                time.sleep(5)

        email_reader.disconnect()
        solver.close()

    except Exception as e:
        state.add_log(f"FATAL: {e}")
        traceback.print_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        state.finish()
        state.add_log("Farm run complete.")
        state.broadcast_progress()
        # Refresh quota after farming
        state.add_log("Checking quota...")
        state.broadcast_quota()


# ── Server Runner ──

def run_panel(host: str = "0.0.0.0", port: int = 8080):
    """Start the panel server."""
    print(f"\n{'=' * 50}")
    print(f"  GROKKIDDING PANEL")
    print(f"  http://localhost:{port}")
    print(f"{'=' * 50}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")
