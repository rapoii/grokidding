"""Cloudflare Turnstile solver using DrissionPage + Chrome extension.

Based on: ReinerBRO/grok-register (385 stars, zero Turnstile issues)

Approach: shadow DOM traversal + JS injection for Turnstile.
Also handles device code approval flow.
"""
import os
import time
import threading
from typing import Optional, Tuple


class TurnstileSolver:
    def __init__(self, extension_path, max_retries: int = 15,
                 timeout: int = 60, debug: bool = False, anti_detect=None,
                 debug_port: int = 9222):
        # Accept either a config dict or extension path string
        if isinstance(extension_path, dict):
            cfg = extension_path
            ext = cfg.get("extension_path", "turnstile_patch/")
            max_retries = cfg.get("max_retries", max_retries)
            timeout = cfg.get("timeout", timeout)
        else:
            ext = extension_path
        self.extension_path = os.path.abspath(ext)
        self.max_retries = max_retries
        self.timeout = timeout
        self.debug = debug
        self._anti_detect = anti_detect  # AntiDetect instance (optional)
        self.debug_port = debug_port  # Chrome remote debugging port

        self._browser = None
        self._proxy = None
        self._forwarder = None

    def set_proxy(self, proxy_url: str):
        """Set proxy for browser. Supports socks5/socks4/http/https."""
        self._proxy = proxy_url

    def _launch_browser(self):
        """Launch Chrome with turnstile extension and optional proxy.

        Retries once on BrowserConnectError after killing lingering Chrome.
        """
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            raise ImportError("DrissionPage required. Install: pip install DrissionPage")

        # Pre-cleanup: always kill stale Chrome on debug port before launching
        self._kill_chrome_on_port(self.debug_port)
        time.sleep(3)  # Extra wait for port to fully release on Windows

        for attempt in range(3):
            opts = ChromiumOptions()
            opts.add_extension(self.extension_path)
            opts.set_local_port(self.debug_port)  # Unique port per worker

            # Anti-detection: use comprehensive args if available, else minimal
            if self._anti_detect:
                for arg in self._anti_detect.get_chrome_args():
                    opts.set_argument(arg)
            else:
                opts.set_argument("--disable-blink-features=AutomationControlled")
                opts.set_argument("--no-first-run")
                opts.set_argument("--no-default-browser-check")

            # Proxy support — SOCKS5 with auth needs local forwarder, others direct
            if self._proxy:
                from .proxy import needs_forwarder
                if needs_forwarder(self._proxy):
                    import re as _re
                    m = _re.match(r"socks5://([^:]+):([^@]+)@([^:]+):(\d+)", self._proxy)
                    if m:
                        user, pwd, host, port = m.group(1), m.group(2), m.group(3), int(m.group(4))
                        local_port = self._start_socks5_forwarder(host, port, user, pwd)
                        if local_port:
                            opts.set_argument(f"--proxy-server=socks5://127.0.0.1:{local_port}")
                            if self.debug:
                                print(f"  [turnstile] SOCKS5 proxy via local forwarder: 127.0.0.1:{local_port}")
                else:
                    opts.set_argument(f"--proxy-server={self._proxy}")
                    if self.debug:
                        print(f"  [turnstile] Proxy direct: {self._proxy}")

            try:
                self._browser = ChromiumPage(opts)

                # Apply anti-detection CDP settings (timezone, locale, UA, viewport)
                if self._anti_detect:
                    self._anti_detect.apply_to_browser(self._browser)

                # Apply CDP-level ad blocking (saves ~400KB per page load)
                from .email_generator import apply_ad_blocking
                apply_ad_blocking(self._browser)

                if self.debug:
                    print("  [turnstile] Browser launched with turnstile extension + ad blocking")
                return self._browser
            except Exception as e:
                err_str = str(e)
                if "BrowserConnectError" in err_str or "browser connection fails" in err_str.lower():
                    if self.debug:
                        print(f"  [turnstile] Port conflict (attempt {attempt+1}/2), killing Chrome...")
                    self._kill_chrome_on_port(self.debug_port)
                    time.sleep(2)
                    continue  # retry
                raise  # other errors: re-raise

        raise RuntimeError("Failed to launch browser after port cleanup retry")

    def _start_socks5_forwarder(self, remote_host, remote_port, user, pwd) -> Optional[int]:
        """Start local SOCKS5 forwarder. Chrome → no-auth → forwarder → auth → remote."""
        import socket as _sock
        import threading as _thr
        import struct as _st
        import select as _sel

        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        local_port = s.getsockname()[1]
        s.close()

        def _fwd(client, remote):
            client.settimeout(60)
            remote.settimeout(60)
            try:
                while True:
                    r, _, _ = _sel.select([client, remote], [], [], 30)
                    if not r: break
                    for sock in r:
                        data = sock.recv(8192)
                        if not data: return
                        (remote if sock is client else client).sendall(data)
            except: pass
            finally:
                try: client.close()
                except: pass
                try: remote.close()
                except: pass

        def _handle(client):
            try:
                client.settimeout(10)
                data = client.recv(256)
                if not data or data[0] != 0x05:
                    client.close(); return
                # Accept no-auth from Chrome
                client.sendall(b'\x05\x00')
                req = client.recv(256)
                if not req or req[0] != 0x05:
                    client.close(); return
                # Connect to remote SOCKS5 with auth
                remote = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                remote.settimeout(10)
                remote.connect((remote_host, remote_port))
                remote.sendall(b'\x05\x01\x02')
                resp = remote.recv(256)
                if not resp or len(resp) < 2 or resp[1] != 0x02:
                    client.sendall(b'\x05\x01\x00\x01' + b'\x00' * 6)
                    client.close(); remote.close(); return
                auth_msg = b'\x01' + bytes([len(user)]) + user.encode() + bytes([len(pwd)]) + pwd.encode()
                remote.sendall(auth_msg)
                resp = remote.recv(256)
                if not resp or len(resp) < 2 or resp[1] != 0x00:
                    client.sendall(b'\x05\x01\x00\x01' + b'\x00' * 6)
                    client.close(); remote.close(); return
                remote.sendall(req)
                resp = remote.recv(256)
                if not resp or len(resp) < 2 or resp[1] != 0x00:
                    client.sendall(b'\x05\x01\x00\x01' + b'\x00' * 6)
                    client.close(); remote.close(); return
                client.sendall(resp)
                _fwd(client, remote)
            except:
                try: client.close()
                except: pass

        def _accept():
            try:
                srv = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                srv.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                srv.bind(('127.0.0.1', local_port))
                srv.listen(20)
                srv.settimeout(600)
                while True:
                    try:
                        c, _ = srv.accept()
                        _thr.Thread(target=_handle, args=(c,), daemon=True).start()
                    except _sock.timeout: break
                srv.close()
            except: pass

        _thr.Thread(target=_accept, daemon=True).start()
        time.sleep(0.2)
        self._forwarder = local_port
        return local_port

    def solve_turnstile(self, url: Optional[str] = None) -> Tuple[Optional[str], dict]:
        """Solve Turnstile on current page. Uses ReinerBRO shadow DOM approach."""
        if not self._browser:
            self._launch_browser()

        page = self._browser

        if url:
            if self.debug:
                print(f"  [turnstile] Navigating to {url}")
            page.get(url)
            time.sleep(3)

        # Inject anti-detection fingerprint BEFORE Turnstile detection
        if self._anti_detect:
            self._anti_detect.inject_fingerprint(page)
            time.sleep(0.5)

        # Try turnstile.reset() first
        try:
            page.run_js("try { turnstile.reset() } catch(e) { }")
            time.sleep(2)
        except Exception:
            pass

        # Main loop: shadow DOM approach
        for attempt in range(self.max_retries):
            try:
                # Check if already solved via getResponse()
                try:
                    token = page.run_js(
                        "try { return turnstile.getResponse() } catch(e) { return null }"
                    )
                    if token and len(token) > 10:
                        if self.debug:
                            print(f"  [turnstile] SOLVED (attempt {attempt+1})! token={token[:30]}...")
                        return token, self._get_cookies(page)
                except Exception:
                    pass

                # Find cf-turnstile-response input
                challenge_solution = page.ele("@name=cf-turnstile-response", timeout=2)
                if not challenge_solution:
                    if self.debug and attempt < 3:
                        print(f"  [turnstile] No cf-turnstile-response yet (attempt {attempt+1})")
                    time.sleep(2)
                    continue

                # Shadow DOM traversal
                challenge_wrapper = challenge_solution.parent()
                shadow = challenge_wrapper.shadow_root
                
                # Wait for iframe to be ready (DrissionPage ChromiumFrame needs time)
                # Wrapped in thread-timeout because ChromiumFrame.ele() can hang in CDP layer
                challenge_iframe = None
                for iframe_wait in range(5):
                    try:
                        def _get_iframe():
                            f = shadow.ele("tag:iframe", timeout=3)
                            if f:
                                _ = f._target_id  # Probe: confirms CDP attached
                            return f
                        challenge_iframe = self._run_with_timeout(_get_iframe, timeout_sec=8, default=None)
                        if challenge_iframe:
                            break
                    except Exception:
                        challenge_iframe = None
                    time.sleep(1)
                
                if not challenge_iframe:
                    if self.debug:
                        print(f"  [turnstile] Iframe not ready/hung (attempt {attempt+1}), retrying...")
                    time.sleep(2)
                    continue

                if self.debug and attempt == 0:
                    print(f"  [turnstile] Found iframe in shadow DOM!")

                # Inject JS patch into iframe (wrapped for DrissionPage quirks)
                try:
                    challenge_iframe.run_js(
                        "window.dtp = 1;"
                        "function getRandomInt(min, max) {"
                        "  return Math.floor(Math.random() * (max - min + 1)) + min;"
                        "}"
                        "let screenX = getRandomInt(800, 1200);"
                        "let screenY = getRandomInt(400, 600);"
                        "Object.defineProperty(MouseEvent.prototype, 'screenX', { value: screenX });"
                        "Object.defineProperty(MouseEvent.prototype, 'screenY', { value: screenY });"
                    )
                except AttributeError:
                    # DrissionPage ChromiumFrame _frame_id bug — skip JS injection, just click
                    if self.debug:
                        print(f"  [turnstile] JS injection skipped (frame bug), trying click directly...")

                # Click checkbox in shadow DOM (wrapped in timeout — can hang in CDP)
                try:
                    def _click_checkbox():
                        body = challenge_iframe.ele("tag:body").shadow_root
                        btn = body.ele("tag:input")
                        btn.click()
                        return True
                    clicked = self._run_with_timeout(_click_checkbox, timeout_sec=12, default=False)
                    if not clicked:
                        raise AttributeError("timeout")
                except (AttributeError, Exception):
                    # Fallback: try clicking via page JS
                    if self.debug:
                        print(f"  [turnstile] Direct click failed, trying JS click fallback...")
                    try:
                        page.run_js("""
                            var iframes = document.querySelectorAll('iframe');
                            for (var i = 0; i < iframes.length; i++) {
                                try {
                                    var doc = iframes[i].contentDocument;
                                    if (doc) {
                                        var inputs = doc.querySelectorAll('input[type=checkbox]');
                                        if (inputs.length > 0) { inputs[0].click(); break; }
                                    }
                                } catch(e) {}
                            }
                        """)
                    except Exception:
                        pass

                if self.debug:
                    print(f"  [turnstile] Clicked checkbox (attempt {attempt+1})")

                time.sleep(3)

                # Check if solved
                try:
                    token = page.run_js(
                        "try { return turnstile.getResponse() } catch(e) { return null }"
                    )
                    if token and len(token) > 10:
                        if self.debug:
                            print(f"  [turnstile] SOLVED after click (attempt {attempt+1})!")
                        return token, self._get_cookies(page)
                except Exception:
                    pass

                # Also check hidden input
                try:
                    hidden = page.ele("@name=cf-turnstile-response", timeout=1)
                    if hidden:
                        val = hidden.attr("value")
                        if val and len(val) > 10:
                            if self.debug:
                                print(f"  [turnstile] SOLVED via hidden input (attempt {attempt+1})!")
                            return val, self._get_cookies(page)
                except Exception:
                    pass

            except Exception as e:
                if self.debug and attempt < 3:
                    print(f"  [turnstile] Error attempt {attempt+1}: {e}")

            time.sleep(2)

        if self.debug:
            print(f"  [turnstile] FAILED after {self.max_retries} attempts")

        return None, self._get_cookies(page)

    def _get_cookies(self, page) -> dict:
        """Extract cookies from page."""
        cookies = {}
        try:
            raw = page.cookies()
            if isinstance(raw, list):
                for c in raw:
                    if isinstance(c, dict):
                        cookies[c.get("name", "")] = c.get("value", "")
                    else:
                        cookies[getattr(c, "name", "")] = getattr(c, "value", "")
            elif isinstance(raw, dict):
                cookies = raw
        except Exception:
            pass
        return cookies

    def approve_device_code(self, verification_url: str, user_code: str) -> bool:
        """Open device code approval page and click Continue + Allow.

        Uses JS click fallback to avoid "element has no location" errors.
        """
        if not self._browser:
            self._launch_browser()

        page = self._browser
        full_url = f"{verification_url}?user_code={user_code}"

        if self.debug:
            print(f"  [device_approve] Opening {full_url}")

        page.get(full_url)
        time.sleep(3)

        # Handle cookie consent
        try:
            accept_btn = page.ele("text:Accept All Cookies", timeout=3)
            if accept_btn:
                accept_btn.click()
                time.sleep(1)
                if self.debug:
                    print(f"  [device_approve] Accepted cookies")
        except Exception:
            pass

        # Click Continue (use JS click for reliability)
        try:
            result = page.run_js(
                "const btns = document.querySelectorAll('button');"
                "for (const b of btns) {"
                "  if (b.textContent.trim() === 'Continue') {"
                "    b.click();"
                "    return 'continue_clicked';"
                "  }"
                "}"
                "return null;"
            )
            if result:
                if self.debug:
                    print(f"  [device_approve] Clicked Continue (JS)")
            else:
                # Fallback: element click
                continue_btn = page.ele("text:Continue", timeout=5)
                if continue_btn:
                    continue_btn.click()
                    if self.debug:
                        print(f"  [device_approve] Clicked Continue (element)")
            time.sleep(3)
        except Exception as e:
            if self.debug:
                print(f"  [device_approve] Continue error: {e}")
            return False

        # Wait for and click Allow button
        for attempt in range(8):
            try:
                # Try JS click first (avoids "no location" error)
                result = page.run_js(
                    "const btns = document.querySelectorAll('button');"
                    "for (const b of btns) {"
                    "  const t = b.textContent.trim().toLowerCase();"
                    "  if (t === 'allow' || t === 'authorize' || t === 'approve') {"
                    "    b.click();"
                    "    return t;"
                    "  }"
                    "}"
                    "return null;"
                )
                if result:
                    time.sleep(2)
                    if self.debug:
                        print(f"  [device_approve] Clicked '{result}' (JS, attempt {attempt+1})")
                    return True

                # Fallback: element click
                for btn_text in ["Allow", "Authorize", "Approve"]:
                    allow_btn = page.ele(f"text:{btn_text}", timeout=1)
                    if allow_btn:
                        allow_btn.click()
                        time.sleep(2)
                        if self.debug:
                            print(f"  [device_approve] Clicked {btn_text} (element, attempt {attempt+1})")
                        return True

            except Exception as e:
                if self.debug and attempt == 0:
                    print(f"  [device_approve] Attempt {attempt+1}: {e}")

            time.sleep(2)

        if self.debug:
            # Debug: dump page info
            try:
                title = page.title
                url = page.url
                print(f"  [device_approve] FAILED. Page: {title} @ {url}")
            except Exception:
                print(f"  [device_approve] FAILED. Could not read page info.")

        return False

    def close(self):
        """Close browser and force-kill lingering Chrome on debug port."""
        try:
            if self._browser:
                self._browser.quit()
        except Exception:
            pass
        self._browser = None
        # Aggressive cleanup: kill + wait + verify
        self._kill_chrome_on_port(self.debug_port)
        time.sleep(1)
        # Double-check port is free
        self._kill_chrome_on_port(self.debug_port)
        time.sleep(2)

    @staticmethod
    def _run_with_timeout(func, timeout_sec=10, default=None):
        """Run func() in a thread with hard timeout. Returns default on timeout.
        
        DrissionPage's ChromiumFrame.ele() can hang indefinitely in CDP layer.
        This wrapper prevents the entire farmer from freezing.
        """
        result = [default]
        error = [None]

        def _worker():
            try:
                result[0] = func()
            except Exception as e:
                error[0] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=timeout_sec)
        if t.is_alive():
            # Thread still running = hung. We can't kill it, but we can move on.
            return default
        if error[0] is not None:
            raise error[0]
        return result[0]

    @staticmethod
    def _kill_chrome_on_port(port: int):
        """Kill Chrome processes listening on the given debug port."""
        import subprocess
        try:
            # Find PIDs listening on port via netstat
            proc = subprocess.run(
                ["cmd", "/c", f"netstat -ano | findstr :{port} | findstr LISTENING"],
                capture_output=True, text=True, timeout=5
            )
            pids = set()
            for line in (proc.stdout or "").strip().splitlines():
                parts = line.split()
                if parts and parts[-1].isdigit():
                    pids.add(parts[-1])
            for pid in pids:
                subprocess.run(
                    ["cmd", "/c", f"taskkill /F /PID {pid}"],
                    capture_output=True, timeout=5
                )
            if pids:
                time.sleep(2)  # Let port fully release
        except Exception:
            pass
