"""Schedule helper for Grokidding Token Refresher — Windows Task Scheduler + Startup shortcut.

Why not pure Task Scheduler LOGON trigger?
  - LOGON / ONSTART triggers via Register-ScheduledTask / schtasks /sc ONLOGON
    require elevation on this machine (Access is denied as normal user).
  - HOURLY trigger via schtasks DOES work as normal user (tested).
So we hybrid:
  - Periodic refresh: schtasks HOURLY /MO 4  -> "Grokidding Token Refresher"
  - Auto-start at logon: Startup folder shortcut -> same batch

Batch wrapper is required so the scheduled process gets PYTHONPATH pointing
to the project root, otherwise `pythonw -m grok_farmer...` fails when cwd is
System32 (Task Scheduler default). Batch is generated dynamically.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

TASK_NAME = "Grokidding Token Refresher"
PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"
BATCH_PATH = PROJECT_DIR / "grok-auto-refresh.bat"
STARTUP_DIR = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
SHORTCUT_PATH = STARTUP_DIR / "Grokidding Token Refresher.lnk"

# Hide console window flag
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _pythonw() -> str:
    # 1. Check current running python environment
    cur_py = Path(sys.executable)
    cur_pyw = Path(sys.executable.replace("python.exe", "pythonw.exe"))
    if cur_pyw.exists():
        return str(cur_pyw)
    if cur_py.exists():
        return str(cur_py)

    # 2. Look for pythonw in PATH
    which_pyw = shutil.which("pythonw")
    if which_pyw:
        return which_pyw

    # 3. Fallback to python in PATH
    which_py = shutil.which("python")
    if which_py:
        return which_py

    return sys.executable


def _ensure_batch() -> Path:
    pyw = _pythonw()
    content = (
        "@echo off\r\n"
        f'set "PROJECT_DIR={PROJECT_DIR}"\r\n'
        "set \"PYTHONPATH=%PROJECT_DIR%\"\r\n"
        f'"{pyw}" -m grok_farmer.auto_refresh_runner\r\n'
    )
    try:
        BATCH_PATH.write_text(content, encoding="utf-8")
    except Exception:
        pass
    return BATCH_PATH


def _run_list(args: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        args,
        capture_output=True,
        text=True,
        creationflags=_CREATE_NO_WINDOW,
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def _ps(cmd: str) -> tuple[int, str]:
    return _run_list(["powershell.exe", "-NoProfile", "-Command", cmd])


def task_exists() -> bool:
    rc, out = _run_list(["schtasks", "/query", "/tn", TASK_NAME])
    return rc == 0 and TASK_NAME.lower() in out.lower()


def get_task_status() -> str:
    rc, out = _run_list(["schtasks", "/query", "/tn", TASK_NAME, "/v", "/fo", "LIST"])
    if rc != 0:
        return "NOT_FOUND"
    for line in out.splitlines():
        if line.strip().lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    for line in out.splitlines():
        if "scheduled task state" in line.lower():
            return line.split(":", 1)[1].strip()
    return "UNKNOWN"


def _create_hourly_task() -> tuple[bool, str]:
    _ensure_batch()
    # List form avoids cmd.exe quoting pitfalls with spaces in path (shell=True breaks it)
    # /tr value must itself be quoted because BATCH_PATH contains spaces
    rc, out = _run_list(
        ["schtasks", "/create", "/tn", TASK_NAME, "/tr", f'"{BATCH_PATH}"', "/sc", "HOURLY", "/mo", "4", "/f"]
    )
    return rc == 0, out


def _delete_hourly_task() -> tuple[bool, str]:
    rc, out = _run_list(["schtasks", "/delete", "/tn", TASK_NAME, "/f"])
    if rc != 0 and "cannot find" in out.lower():
        return True, out
    return rc == 0, out


def enable_task() -> tuple[bool, str]:
    rc, out = _run_list(["schtasks", "/change", "/tn", TASK_NAME, "/enable"])
    return rc == 0, out


def disable_task() -> tuple[bool, str]:
    rc, out = _run_list(["schtasks", "/change", "/tn", TASK_NAME, "/disable"])
    return rc == 0, out


def _ensure_startup_shortcut() -> tuple[bool, str]:
    _ensure_batch()
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    ps = (
        f"$WshShell = New-Object -comObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{SHORTCUT_PATH}'); "
        f"$Shortcut.TargetPath = '{BATCH_PATH}'; "
        f"$Shortcut.WorkingDirectory = '{PROJECT_DIR}'; "
        f"$Shortcut.Description = 'Grokidding auto token refresher'; "
        f"$Shortcut.Save(); "
        f"if (Test-Path '{SHORTCUT_PATH}') {{ Write-Output 'SHORTCUT_OK' }} else {{ Write-Output 'SHORTCUT_FAIL'; exit 1 }}"
    )
    rc, out = _ps(ps)
    return rc == 0 and "SHORTCUT_OK" in out, out


def _remove_startup_shortcut() -> tuple[bool, str]:
    try:
        if SHORTCUT_PATH.exists():
            SHORTCUT_PATH.unlink()
            return True, "SHORTCUT_REMOVED"
        return True, "SHORTCUT_NOT_FOUND"
    except Exception as e:
        return False, str(e)


def create_task() -> tuple[bool, str]:
    """Create both hourly schtasks + startup shortcut."""
    _ensure_batch()
    ok1, out1 = _create_hourly_task()
    if not ok1:
        return False, f"schtasks create failed: {out1}"
    ok2, out2 = _ensure_startup_shortcut()
    if not ok2:
        return False, f"hourly OK but shortcut failed: {out2}"
    return True, "CREATED (hourly + startup)"


def delete_task() -> tuple[bool, str]:
    rc1, out1 = _delete_hourly_task()
    rc2, out2 = _remove_startup_shortcut()
    return rc1 and rc2, f"{out1} | {out2}"


def ensure_task(enabled: bool) -> tuple[bool, str]:
    """Ensure hourly task + startup shortcut match desired enabled state.

    enabled=True  -> create schtasks HOURLY/4 + Startup shortcut (persists after panel closed & reboot)
    enabled=False -> COMPLETELY DELETE both, so it truly disappears from Task Scheduler / Task Manager Startup
    """
    _ensure_batch()
    if enabled:
        if not task_exists():
            ok, out = create_task()
            if not ok:
                return False, out
            return True, out
        ok_e, out_e = enable_task()
        ok_s, out_s = _ensure_startup_shortcut()
        if not ok_e:
            return False, f"enable failed: {out_e}"
        if not ok_s:
            return False, f"hourly enabled but shortcut failed: {out_s}"
        return True, "ENABLED"
    else:
        # OFF must DELETE, not just disable — so it vanishes from Task Scheduler & Task Manager > Startup
        if task_exists() or shortcut_exists():
            ok, out = delete_task()
            if not ok:
                return False, f"delete failed: {out}"
            return True, f"DELETED | {out}"
        return True, "ALREADY_DELETED"


def run_now() -> tuple[bool, str]:
    rc, out = _run_list(["schtasks", "/run", "/tn", TASK_NAME])
    return rc == 0, out


def shortcut_exists() -> bool:
    return SHORTCUT_PATH.exists()
