"""Cloudflare Turnstile solver using DrissionPage + Chrome extension.

Based on: ReinerBRO/grok-register (385 stars, zero Turnstile issues)

Approach: shadow DOM traversal + JS injection for Turnstile.
Also handles device code approval flow.
"""
import os
import time
from typing import Optional, Tuple


class TurnstileSolver:
    def __init__(self, extension_path: str, max_retries: int = 15,
                 timeout: int = 60, debug: bool = False, headless: bool = False):
        self.extension_path = os.path.abspath(extension_path)
        self.max_retries = max_retries
        self.timeout = timeout
        self.debug = debug
        self.headless = headless
        self._browser = None
        self._proxy = None
        self._forwarder = None

    def set_proxy(self, proxy_url: str):
        """Set proxy for browser. Supports socks5/socks4/http/https."""
        self._proxy = proxy_url

    def _launch_browser(self):
        """Launch Chrome with turnstile extension and optional proxy."""
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            raise ImportError("DrissionPage required. Install: pip install DrissionPage")

        opts = ChromiumOptions()
        opts.add_extension(self.extension_path)
        opts.set_argument("--disable-blink-features=AutomationControlled")
        opts.set_argument("--no-first-run")
        opts.set_argument("--no-default-browser-check")

        if self.headless:
            opts.headless(True)

        # Proxy support — SOCKS5 with auth needs local forwarder, others direct
        if self._proxy:
            from .proxy import needs_forwarder
            if needs_forwarder(self._proxy):
                # SOCKS5 with auth — use local forwarder (Chrome limitation)
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
                # HTTP/HTTPS/SOCKS4/SOCKS5-no-auth — pass directly to Chrome
                opts.set_argument(f"--proxy-server={self._proxy}")
                if self.debug:
                    print(f"  [turnstile] Proxy direct: {self._proxy}")

        self._browser = ChromiumPage(opts)
        if self.debug:
            print("  [turnstile] Browser launched with turnstile extension")
        return self._browser

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
                challenge_iframe = challenge_wrapper.shadow_root.ele("tag:iframe")

                if self.debug and attempt == 0:
                    print(f"  [turnstile] Found iframe in shadow DOM!")

                # Inject JS patch into iframe
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

                # Click checkbox in shadow DOM
                challenge_iframe_body = challenge_iframe.ele("tag:body").shadow_root
                challenge_button = challenge_iframe_body.ele("tag:input")
                challenge_button.click()

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
        """Close browser."""
        try:
            if self._browser:
                self._browser.quit()
        except Exception:
            pass
        self._browser = None
