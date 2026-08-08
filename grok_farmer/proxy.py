"""Proxy rotation — multi-type proxy pool + ADB airplane mode.

Supported proxy types:
  - socks5://user:pass@host:port  (SOCKS5 with auth — needs local forwarder for Chrome)
  - socks5://host:port            (SOCKS5 no auth — direct)
  - socks4://host:port            (SOCKS4 — direct)
  - http://user:pass@host:port    (HTTP proxy — direct)
  - http://host:port              (HTTP no auth — direct)
  - https://user:pass@host:port   (HTTPS proxy — direct)

ADB airplane mode supports:
  - Android 9+: cmd connectivity airplane-mode (fast, ~6s)
  - Android 7-8 Vivo Funtouch: Control Center UI tap (~9s)
  - Auto-detection, retry logic, state verification
"""
import os
import random
import re
import subprocess
import time
from typing import Optional


# Supported proxy URL patterns
PROXY_SCHEMES = ("socks5://", "socks4://", "http://", "https://")

# Vivo Control Center coordinates (720x1440, Mode Pesawat in first position)
VIVO_CC = {
    "swipe_x": 360,
    "swipe_from_y": 1439,
    "swipe_to_y": 300,
    "swipe_duration": 100,
    "tap_x": 220,
    "tap_y": 1115,
}


def get_proxy_type(url: str) -> str:
    """Return proxy type from URL scheme. E.g. 'socks5', 'http', etc."""
    for scheme in PROXY_SCHEMES:
        if url.startswith(scheme):
            return scheme.rstrip("://")
    return "unknown"


def needs_forwarder(url: str) -> bool:
    """Check if proxy needs a local SOCKS5 forwarder (Chrome can't do socks5+auth)."""
    if not url.startswith("socks5://"):
        return False
    # Has auth credentials? → needs forwarder
    return bool(re.match(r"socks5://[^:]+:[^@]+@", url))


def _run_adb(args: list, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run ADB command and return result."""
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def _detect_adb_method(adb_path: str, serial: str) -> str:
    """Detect which airplane mode method works on this device.

    Returns: 'cmd_connectivity' | 'vivo_cc' | 'unknown'
    Cached per session — call once, reuse.
    """
    cmd_base = [adb_path]
    if serial:
        cmd_base += ["-s", serial]

    # Try cmd connectivity first (Android 9+)
    proc = _run_adb(cmd_base + ["shell", "cmd", "connectivity", "airplane-mode"])
    if proc.returncode == 0:
        stdout = (proc.stdout or "").strip()
        if stdout in ("enabled", "disabled"):
            return "cmd_connectivity"
        if "No shell command" in stdout:
            pass  # Fall through to UI automation

    # Assume Vivo Funtouch (Android 7-8) — use Control Center UI tap
    return "vivo_cc"


def _get_airplane_state(adb_path: str, serial: str) -> Optional[bool]:
    """Read airplane mode state. Returns True=on, False=off, None=error."""
    cmd_base = [adb_path]
    if serial:
        cmd_base += ["-s", serial]
    proc = _run_adb(cmd_base + ["shell", "settings", "get", "global", "airplane_mode_on"])
    if proc.returncode == 0:
        val = (proc.stdout or "").strip()
        if val == "1":
            return True
        if val == "0":
            return False
    return None


class ProxyRotator:
    def __init__(self, pool: list, mode: str = "socks5", adb_config: Optional[dict] = None):
        self.pool = pool
        self.mode = mode
        self.adb_config = adb_config or {}
        self._index = 0
        self._adb_method: Optional[str] = None  # cached detection result

    @property
    def adb_enabled(self) -> bool:
        return bool(self.adb_config.get("enabled"))

    @property
    def adb_path(self) -> str:
        return self.adb_config.get("adb_path", "adb")

    @property
    def adb_serial(self) -> str:
        return self.adb_config.get("device_serial", "")

    def next(self) -> str:
        """Return next proxy from pool."""
        if not self.pool:
            return ""
        proxy = self.pool[self._index % len(self.pool)]
        self._index += 1
        return proxy

    def random(self) -> str:
        """Return random proxy from pool."""
        if not self.pool:
            return ""
        return random.choice(self.pool)

    def rotate_adb(self, verify_ip: bool = False) -> dict:
        """Toggle airplane mode via ADB to get new IP.

        Auto-detects method: cmd connectivity (Android 9+) or
        Vivo Control Center UI tap (Android 7-8 Funtouch).

        Returns: {"ok": bool, "method": str, "ip": str|None, "error": str|None}
        """
        adb = self.adb_path
        serial = self.adb_serial

        # Verify ADB is accessible
        proc = _run_adb([adb, "devices"], timeout=5)
        if proc.returncode != 0:
            return {"ok": False, "method": "none", "ip": None,
                    "error": f"ADB not found: {adb}"}

        # Detect method (cached)
        if self._adb_method is None:
            self._adb_method = _detect_adb_method(adb, serial)

        method = self._adb_method

        # Get IP before rotation
        ip_before = None
        if verify_ip:
            ip_before = self._get_public_ip()

        # Execute rotation
        if method == "cmd_connectivity":
            ok = self._rotate_cmd_connectivity(adb, serial)
        elif method == "vivo_cc":
            ok = self._rotate_vivo_cc(adb, serial)
        else:
            return {"ok": False, "method": method, "ip": None,
                    "error": f"Unknown method: {method}"}

        if not ok:
            return {"ok": False, "method": method, "ip": None,
                    "error": "Airplane mode toggle failed after retries"}

        # Get IP after rotation
        ip_after = None
        if verify_ip:
            time.sleep(1)  # wait for reconnect
            ip_after = self._get_public_ip()

        return {"ok": True, "method": method, "ip": ip_after,
                "ip_before": ip_before, "error": None}

    def _rotate_cmd_connectivity(self, adb: str, serial: str) -> bool:
        """Toggle via cmd connectivity (Android 9+)."""
        cmd_base = [adb]
        if serial:
            cmd_base += ["-s", serial]

        for attempt in range(3):
            _run_adb(cmd_base + ["shell", "cmd", "connectivity", "airplane-mode", "enable"],
                     timeout=10)
            time.sleep(2)
            _run_adb(cmd_base + ["shell", "cmd", "connectivity", "airplane-mode", "disable"],
                     timeout=10)
            time.sleep(3)

            state = _get_airplane_state(adb, serial)
            if state is False:
                return True  # airplane off = success

        return False

    def _rotate_vivo_cc(self, adb: str, serial: str) -> bool:
        """Toggle via Vivo Control Center UI tap (Android 7-8 Funtouch).

        Uses single combined shell call for speed (~9s total).
        WAKEUP → HOME → swipe CC → tap ON → close → swipe CC → tap OFF → close
        """
        cmd_base = [adb]
        if serial:
            cmd_base += ["-s", serial]

        cc = VIVO_CC
        swipe_tap_close = (
            f"input swipe {cc['swipe_x']} {cc['swipe_from_y']} "
            f"{cc['swipe_x']} {cc['swipe_to_y']} {cc['swipe_duration']} && "
            f"input tap {cc['tap_x']} {cc['tap_y']} && "
            f"input keyevent 4"
        )

        for attempt in range(3):
            # Single combined shell call: WAKEUP → HOME → ON → OFF
            full_cmd = (
                "input keyevent KEYCODE_WAKEUP && "
                "input keyevent 3 && "  # HOME — REQUIRED or swipe opens Recent Apps
                f"{swipe_tap_close} && "
                f"{swipe_tap_close}"
            )

            proc = _run_adb(cmd_base + ["shell", full_cmd], timeout=30)
            if proc.returncode != 0:
                continue

            time.sleep(0.5)
            state = _get_airplane_state(adb, serial)
            if state is False:
                return True  # airplane off = success

            # Cleanup: close any leftover CC
            _run_adb(cmd_base + ["shell", "input keyevent 4"], timeout=5)
            time.sleep(0.5)

        return False

    def _get_public_ip(self) -> Optional[str]:
        """Get current public IP via api.ipify.org."""
        try:
            from curl_cffi import requests as curl_requests
            s = curl_requests.Session()
            r = s.get("https://api.ipify.org", timeout=10)
            if r.status_code == 200:
                return r.text.strip()
        except Exception:
            pass
        try:
            import urllib.request
            with urllib.request.urlopen("https://api.ipify.org", timeout=10) as r:
                return r.read().decode().strip()
        except Exception:
            pass
        return None

    def get_curl_args(self, proxy: str) -> list:
        """Return curl-compatible proxy args. Works for all proxy types."""
        if not proxy:
            return []
        return ["--proxy", proxy]

    def get_requests_proxies(self, proxy: str) -> dict:
        """Return requests-compatible proxy dict. Works for all proxy types."""
        if not proxy:
            return {}
        return {"http": proxy, "https": proxy}
