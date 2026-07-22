"""Proxy rotation — multi-type proxy pool + ADB airplane mode fallback.

Supported proxy types:
  - socks5://user:pass@host:port  (SOCKS5 with auth — needs local forwarder for Chrome)
  - socks5://host:port            (SOCKS5 no auth — direct)
  - socks4://host:port            (SOCKS4 — direct)
  - http://user:pass@host:port    (HTTP proxy — direct)
  - http://host:port              (HTTP no auth — direct)
  - https://user:pass@host:port   (HTTPS proxy — direct)
"""
import random
import re
import subprocess
import time
from typing import Optional


# Supported proxy URL patterns
PROXY_SCHEMES = ("socks5://", "socks4://", "http://", "https://")


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


class ProxyRotator:
    def __init__(self, pool: list, mode: str = "socks5", adb_config: Optional[dict] = None):
        self.pool = pool
        self.mode = mode
        self.adb_config = adb_config or {}
        self._index = 0

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

    def rotate_adb(self) -> str:
        """Toggle airplane mode via ADB to get new IP. Returns new IP estimate."""
        adb = self.adb_config.get("adb_path", "adb")
        serial = self.adb_config.get("device_serial", "")

        cmd_base = [adb]
        if serial:
            cmd_base += ["-s", serial]

        subprocess.run(cmd_base + ["shell", "cmd", "connectivity", "airplane-mode", "enable"],
                       capture_output=True, timeout=10)
        time.sleep(3)

        subprocess.run(cmd_base + ["shell", "cmd", "connectivity", "airplane-mode", "disable"],
                       capture_output=True, timeout=10)
        time.sleep(5)

        return "IP rotated via ADB"

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
