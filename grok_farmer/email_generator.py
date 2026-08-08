"""Email generator and OTP polling via generator.email — bandwidth optimized.

Uses WebSocket real-time notifications instead of full-page refresh polling.
Blocks Google Ads at CDP level to reduce data transfer by ~99.7%.

Flow:
1. Open generator.email in browser tab (ONCE, with ads blocked)
2. Copy the auto-generated email address from the page
3. Use that email for xAI signup
4. Connect WebSocket and listen for incoming OTP emails (no page refresh!)
5. When email arrives, fetch ONLY the email content via AJAX (~2KB vs 493KB)
"""

import re
import os
import time
import json
import threading
from typing import Optional


# Domains to block at CDP level (ads, tracking, analytics)
BLOCKED_DOMAINS = [
    "pagead2.googlesyndication.com",
    "googleads.g.doubleclick.net",
    "fundingchoicesmessages.google.com",
    "ep1.adtrafficquality.google",
    "ep2.adtrafficquality.google",
    "www.google.co.id/pagead",
    "www.google.com/pagead",
    "www.google.com/ccm",
    "www.google.com/rmkt",
    "analytics.google.com",
    "www.googletagmanager.com",
    "t.co",
    "analytics.twitter.com",
    "static.ads-twitter.com",
    "stapecdn.com",
    "websdk.appsflyersdk.com",
    "wa.appsflyersdk.com",
    "wa.onelink.me",
    "static.cloudflareinsights.com",
    "sgtm-prod-985009374134.us-central1.run.app",
    # generator.email non-essential assets
    "qrcode.js",
    "share-qr.js",
    "ga-events.js",
]


def apply_ad_blocking(browser):
    """Apply CDP-level ad blocking to a DrissionPage browser instance.

    Blocks ad/tracking domains via Network.setBlockedURLs.
    This affects ALL tabs opened on this browser instance.
    """
    try:
        # Build URL patterns for CDP blocking
        url_patterns = []
        for domain in BLOCKED_DOMAINS:
            url_patterns.append(f"*://{domain}/*")
            url_patterns.append(f"*://*.{domain}/*")

        # CDP command to block URLs
        browser.run_cdp("Network.enable")
        browser.run_cdp(
            "Network.setBlockedURLs",
            urls=url_patterns,
        )
        return True
    except Exception as e:
        print(f"  [adblock] CDP block failed (non-fatal): {e}")
        return False


def _run_js_safe(tab, js_code, timeout_sec=10, default=None):
    """Run JavaScript in a DrissionPage tab with hard timeout.

    DrissionPage's run_js() can hang indefinitely in CDP layer.
    This wrapper prevents the farmer from freezing.
    """
    result = [default]
    error = [None]

    def _worker():
        try:
            result[0] = tab.run_js(js_code)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)
    if t.is_alive():
        return default  # Hung — move on
    if error[0] is not None:
        raise error[0]
    return result[0]


def generate_email_from_browser(browser, max_attempts: int = 10) -> str:
    """Generate a fresh email address from generator.email via browser.

    Opens generator.email, clicks "Generate new e-mail" until we get
    a supported domain (not generator.email or blocked domains).
    """
    UNSUPPORTED_DOMAINS = {"generator.email", "dharmadi.com"}

    tab = browser.new_tab("https://generator.email")
    # Wait for SPA to fully render (extension loading can delay DOM)
    for _wait in range(20):
        time.sleep(1)
        if tab.ele("css:input[id='userName']", timeout=0.5):
            break
    else:
        print("  [email] WARNING: inputs never appeared after 20s")

    # Always click "Generate new e-mail" to get a FRESH email (not cached)
    for _ in range(3):
        try:
            gen_btn = tab.ele("text:Generate new e-mail", timeout=3)
            if gen_btn:
                gen_btn.click()
                time.sleep(2)
        except Exception:
            pass

    for attempt in range(max_attempts):
        email = None

        # Read email from input fields — multiple selector strategies
        try:
            email_input = (
                tab.ele("css:input[id='userName']", timeout=2)
                or tab.ele("css:input[aria-label*='username']", timeout=1)
                or tab.ele("css:input[placeholder*='username']", timeout=1)
            )
            domain_input = (
                tab.ele("css:input[id='domainName2']", timeout=2)
                or tab.ele("css:input[aria-label*='domain']", timeout=1)
                or tab.ele("css:input[placeholder*='domain']", timeout=1)
            )
            if email_input and domain_input:
                user = email_input.attr("value") or ""
                domain = domain_input.attr("value") or ""
                if user and domain:
                    email = f"{user}@{domain}"
        except Exception:
            pass

        # Fallback: extract from visible text
        if not email:
            try:
                page_text = tab.ele("css:body").text if tab.ele("css:body", timeout=2) else ""
                emails_found = re.findall(r'([a-z0-9]{6,20}@[a-z0-9.-]+\.[a-z]{2,})', page_text)
                if emails_found:
                    email = emails_found[0]
            except Exception:
                pass

        if email:
            domain = email.split("@", 1)[1]
            if domain in UNSUPPORTED_DOMAINS:
                print(f"  [email] Domain {domain} unsupported, regenerating... (attempt {attempt+1})")
            else:
                print(f"  [email] Generated: {email} (attempt {attempt+1})")
                tab.close()
                return email
        else:
            print(f"  [email] Could not read email, regenerating... (attempt {attempt+1})")

        # Click "Generate new e-mail" to get a different email
        try:
            gen_btn = tab.ele("text:Generate new e-mail", timeout=3)
            if gen_btn:
                gen_btn.click()
                time.sleep(3)
            else:
                # Fallback: try the button by CSS
                gen_btn = tab.ele("css:button:has-text('Generate')", timeout=3)
                if gen_btn:
                    gen_btn.click()
                    time.sleep(3)
        except Exception:
            pass

    tab.close()
    raise RuntimeError(f"Failed to generate supported email after {max_attempts} attempts")


def extract_xai_code(text: str) -> Optional[str]:
    """Extract xAI OTP code from email text.

    xAI sends codes in format: XXX-XXX (e.g., V96-2ET)
    We strip the dash and return 6 chars.
    """
    # Pattern: XXX-XXX (3 chars, dash, 3 chars) — uppercase alphanumeric
    dash_codes = re.findall(r'\b([A-Z0-9]{3}-[A-Z0-9]{3})\b', text)
    if dash_codes:
        return dash_codes[0].replace("-", "")

    # Fallback: 6-char alphanumeric (no dash)
    alpha = re.findall(r'\b([A-Z0-9]{6})\b', text)
    if alpha:
        year_codes = {"202020", "202120", "202220", "202320", "202420", "202520", "202620"}
        for c in alpha:
            if c not in year_codes:
                return c

    return None


class GeneratorEmailReader:
    """Read OTP codes from generator.email via WebSocket — bandwidth optimized.

    Instead of refreshing the full page every 3 seconds (493KB each time),
    opens the inbox ONCE and listens via WebSocket for real-time notifications.
    When an email arrives, fetches only that email's content (~2KB).
    """

    def __init__(self, browser):
        self._browser = browser
        self._email_tab = None

    def wait_for_otp(self, timeout: int = 180, poll_interval: float = 3.0,
                     target_email: str = "", **kwargs) -> Optional[str]:
        """Wait for xAI OTP — WebSocket mode (default) or legacy page-refresh polling.

        Set env GROK_NO_WSS=1 to force legacy polling (useful for debugging
        OTP delivery issues — rules out WebSocket layer).
        """
        if not target_email:
            print("  [otp] ERROR: No target_email")
            return None

        inbox_url = f"https://generator.email/{target_email}"

        # Default: legacy page-refresh polling (reliable).
        # WSS mode is opt-in via GROK_USE_WSS=1 (WSS doesn't fire onmessage
        # for incoming emails — confirmed broken via GROK_DUAL_OTP test).
        if os.environ.get("GROK_USE_WSS") and not os.environ.get("GROK_NO_WSS"):
            print(f"  [otp] GROK_USE_WSS=1 → WebSocket mode: {target_email}")
        elif os.environ.get("GROK_DUAL_OTP"):
            print(f"  [otp] GROK_DUAL_OTP=1 → dual mode (WSS + page refresh): {target_email}")
            return self._dual_poll_otp(timeout, poll_interval, target_email, inbox_url)
        else:
            print(f"  [otp] Legacy polling mode: {target_email}")
            return self._legacy_poll_otp(timeout, poll_interval, target_email, inbox_url)

        # Open inbox tab ONCE — no more full-page refreshes
        tab = None
        pre_codes = set()
        try:
            tab = self._browser.new_tab(inbox_url)
            time.sleep(5)  # Wait for page + WS to connect
            pre_html = tab.html
            pre_codes = set(re.findall(r"([A-Z0-9]{3}-[A-Z0-9]{3})", pre_html))
            pre_codes.update(re.findall(r"([A-Z0-9]{6})", pre_html))
            year_set = {"202020", "202120", "202220", "202320", "202420", "202520", "202620"}
            pre_codes -= year_set
            print(f"  [otp] Pre-existing: {len(pre_codes)} codes")
        except Exception as e:
            print(f"  [otp] Init error: {e}")

        if not tab:
            print("  [otp] Tab creation failed, falling back to legacy polling")
            return self._legacy_poll_otp(timeout, poll_interval, target_email, inbox_url)

        # Inject WebSocket listener
        ws_ok = self._inject_websocket_listener(tab, target_email)
        if not ws_ok:
            print("  [otp] WebSocket injection failed, falling back to legacy polling")
            self._safe_close_tab(tab)
            return self._legacy_poll_otp(timeout, poll_interval, target_email, inbox_url)

        print(f"  [otp] WebSocket connected, listening for emails...")

        # Poll for WebSocket messages (lightweight — just reading a JS variable)
        start = time.time()
        checked_links = set()

        while time.time() - start < timeout:
            try:
                # Read WebSocket messages from injected JS (with timeout protection)
                msgs_json = _run_js_safe(
                    tab,
                    "try { return JSON.stringify(window._otp_messages || []) } catch(e) { return '[]' }",
                    timeout_sec=5,
                    default='[]'
                )
                messages = json.loads(msgs_json) if msgs_json else []

                # Process new messages
                for msg in messages:
                    link = msg.get("link", "")
                    from_addr = msg.get("from", "")
                    subject = msg.get("subject", "")

                    # Skip already checked
                    if link in checked_links:
                        continue
                    checked_links.add(link)

                    # Check if this is an xAI email
                    combined = (from_addr + " " + subject).lower()
                    is_xai = any(kw in combined for kw in [
                        "xai", "spacexai", "x.ai", "confirmation", "verify"
                    ])

                    elapsed = int(time.time() - start)
                    print(f"  [otp] New email ({elapsed}s): from={from_addr[:30]} subj={subject[:40]}")

                    if not is_xai:
                        # Still check — subject might not contain keywords but body might
                        pass

                    # Fetch email content via AJAX (small — just the email body)
                    code = self._fetch_email_content_otp(tab, link, pre_codes)
                    if code:
                        print(f"  [otp] CODE: {code}")
                        self._safe_close_tab(tab)
                        return code

                # Status log every 10 cycles
                elapsed = int(time.time() - start)
                if elapsed > 0 and elapsed % 30 == 0 and elapsed > 0:
                    # Check WS connection status
                    ws_state = _run_js_safe(
                        tab,
                        "try { return (window._otp_ws ? window._otp_ws.readyState : -1) } catch(e) { return -1 }",
                        timeout_sec=5,
                        default=-1
                    )
                    state_names = {0: "connecting", 1: "online", 2: "closing", 3: "closed"}
                    ws_status = state_names.get(ws_state, f"unknown({ws_state})")
                    print(f"  [otp] ...{elapsed}s, {len(messages)} emails received, ws={ws_status}")

                    # Reconnect if WebSocket closed
                    if ws_state == 3:
                        print(f"  [otp] WebSocket closed, reconnecting...")
                        self._inject_websocket_listener(tab, target_email)

            except Exception as e:
                err_str = str(e)[:60]
                if "html" in err_str.lower() or "tab" in err_str.lower():
                    print(f"  [otp] Tab lost, reconnecting...")
                    try:
                        self._safe_close_tab(tab)
                        tab = self._browser.new_tab(inbox_url)
                        time.sleep(4)
                        self._inject_websocket_listener(tab, target_email)
                    except Exception:
                        pass
                else:
                    print(f"  [otp] Poll error: {err_str}")

            time.sleep(poll_interval)

        self._safe_close_tab(tab)
        print(f"  [otp] TIMEOUT {timeout}s")
        return None

    def _inject_websocket_listener(self, tab, email: str) -> bool:
        """Inject JavaScript WebSocket listener into the page.

        Stores incoming email notifications in window._otp_messages array.
        """
        try:
            js_code = f"""
            (function() {{
                if (window._otp_ws && window._otp_ws.readyState === 1) return true;
                window._otp_messages = window._otp_messages || [];
                var email = {json.dumps(email)};
                var wsUrl = 'wss://generator.email/notificon/ws?email=' + encodeURIComponent(email);
                try {{
                    if (window._otp_ws) {{
                        try {{ window._otp_ws.close(); }} catch(e) {{}}
                    }}
                    window._otp_ws = new WebSocket(wsUrl);
                    window._otp_ws.onmessage = function(event) {{
                        try {{
                            var msg = JSON.parse(event.data);
                            window._otp_messages.push(msg);
                        }} catch(e) {{}}
                    }};
                    window._otp_ws.onerror = function(e) {{}};
                    window._otp_ws.onclose = function(e) {{}};
                    return true;
                }} catch(e) {{
                    return false;
                }}
            }})()
            """
            tab.run_js(js_code)
            # Don't trust return value (DrissionPage may return None for truthy JS)
            # Wait briefly then check readyState directly (with timeout protection)
            time.sleep(2)
            ws_state = _run_js_safe(
                tab,
                "try { return window._otp_ws ? window._otp_ws.readyState : -1 } catch(e) { return -1 }",
                timeout_sec=5,
                default=-1
            )
            # readyState 0 = connecting (OK, WS created), 1 = open
            if ws_state is not None and ws_state in (0, 1):
                return True
            return False
        except Exception as e:
            print(f"  [otp] WS inject error: {e}")
            return False

    def _fetch_email_content_otp(self, tab, link: str, pre_codes: set) -> Optional[str]:
        """Fetch email content via AJAX and extract OTP code.

        Uses the site's built-in loadInboxClientSide() or direct fetch.
        Only downloads the email body (~2KB), not the full page (493KB).
        """
        if not link:
            return None

        try:
            # Method 1: Use site's built-in loadInboxClientSide (AJAX, updates DOM)
            # This fetches only the email content, not a full page reload
            js_fetch = f"""
            (async function() {{
                try {{
                    // Try loadInboxClientSide first (site's built-in AJAX)
                    if (typeof window.loadInboxClientSide === 'function') {{
                        window.loadInboxClientSide({json.dumps(link)});
                        // Wait for content to load
                        await new Promise(r => setTimeout(r, 2000));
                        var body = document.getElementById('mail-summary-body');
                        if (body && body.innerHTML.length > 50) {{
                            return body.innerHTML;
                        }}
                    }}

                    // Method 2: Direct fetch the email page
                    var url = '/' + {json.dumps(link)};
                    var resp = await fetch(url, {{
                        headers: {{'X-Requested-With': 'XMLHttpRequest'}}
                    }});
                    var html = await resp.text();
                    return html;
                }} catch(e) {{
                    return 'ERROR:' + e.message;
                }}
            }})()
            """
            content = _run_js_safe(tab, js_fetch, timeout_sec=15, default=None)
            if not content or content.startswith("ERROR:"):
                # Method 3: Navigate to the email URL directly (fallback, small page)
                email_url = f"https://generator.email/{link}"
                tab.get(email_url)
                time.sleep(2)
                content = tab.html

            if content:
                code = extract_xai_code(content)
                if code and code not in pre_codes:
                    return code

                # Try extracting from mess_bodiyy selector (site-specific)
                try:
                    body_text = _run_js_safe(
                        tab,
                        "try { var el = document.querySelector('.mess_bodiyy'); "
                        "return el ? el.textContent : '' } catch(e) { return '' }",
                        timeout_sec=5,
                        default=''
                    )
                    if body_text:
                        code = extract_xai_code(body_text)
                        if code and code not in pre_codes:
                            return code
                except Exception:
                    pass

        except Exception as e:
            print(f"  [otp] Fetch email error: {str(e)[:60]}")

        return None

    def _dual_poll_otp(self, timeout, poll_interval, target_email, inbox_url):
        """Diagnostic: run WSS + page refresh simultaneously, log which finds OTP first."""
        print(f"  [otp] Dual mode: WSS + page refresh for {target_email}")

        year_set = {"202020", "202120", "202220", "202320", "202420", "202520", "202620"}

        # Tab A: WSS listener (stays on inbox page, no refresh)
        tab_a = None
        pre_codes = set()
        try:
            tab_a = self._browser.new_tab(inbox_url)
            time.sleep(5)
            pre_html = tab_a.html
            pre_codes = set(re.findall(r"([A-Z0-9]{3}-[A-Z0-9]{3})", pre_html))
            pre_codes.update(re.findall(r"([A-Z0-9]{6})", pre_html))
            pre_codes -= year_set
            print(f"  [otp-dual] Pre-existing: {len(pre_codes)} codes")
        except Exception as e:
            print(f"  [otp-dual] Tab A init error: {e}")

        # Inject WSS on tab A
        ws_ok = self._inject_websocket_listener(tab_a, target_email) if tab_a else False
        print(f"  [otp-dual] WSS injected: {ws_ok}")

        # Tab C: page-refresh polling
        tab_c = None
        try:
            tab_c = self._browser.new_tab(inbox_url)
            time.sleep(3)
        except Exception as e:
            print(f"  [otp-dual] Tab C init error: {e}")

        start = time.time()
        last_wss_count = 0
        wss_found = None
        page_found = None

        while time.time() - start < timeout:
            elapsed = int(time.time() - start)

            # ── WSS check (tab A) ──
            if tab_a and not wss_found:
                try:
                    ws_state = _run_js_safe(tab_a, "try { return window._otp_ws ? window._otp_ws.readyState : -1 } catch(e) { return -1 }", timeout_sec=3, default=-1)
                    msgs_json = _run_js_safe(tab_a, "try { return JSON.stringify(window._otp_messages || []) } catch(e) { return '[]' }", timeout_sec=3, default='[]')
                    messages = json.loads(msgs_json) if msgs_json else []
                    wss_count = len(messages)

                    if wss_count > last_wss_count:
                        print(f"  [otp-dual] 🔵 WSS NEW MSG ({elapsed}s)! count={wss_count}")
                        for msg in messages[last_wss_count:]:
                            print(f"    WSS: {json.dumps(msg)[:300]}")
                        last_wss_count = wss_count

                        for msg in messages:
                            combined = json.dumps(msg)
                            code = extract_xai_code(combined)
                            if code and code not in pre_codes:
                                wss_found = code
                                print(f"  [otp-dual] ✅ WSS FOUND OTP: {code} ({elapsed}s)")

                    # Reconnect if closed
                    if ws_state == 3 and elapsed > 0 and elapsed % 30 == 0:
                        print(f"  [otp-dual] WSS closed, reconnecting...")
                        self._inject_websocket_listener(tab_a, target_email)

                except Exception as e:
                    pass

            # ── Page refresh check (tab C) ──
            if tab_c and not page_found:
                try:
                    page_html = tab_c.html
                    has_xai = any(kw in page_html.lower() for kw in ["xai", "spacexai", "x.ai", "confirmation", "verify"])

                    if has_xai:
                        items = tab_c.eles("css:a.list-group-item")
                        for item in items:
                            try:
                                itxt = item.text if hasattr(item, "text") else ""
                            except:
                                continue
                            if any(kw in itxt.lower() for kw in ["xai", "spacexai", "x.ai", "confirmation", "verify"]):
                                print(f"  [otp-dual] 🟢 PAGE found xAI email ({elapsed}s): {itxt[:50]}")
                                item.click()
                                time.sleep(2)
                                body = tab_c.html
                                code = extract_xai_code(body)
                                if code and code not in pre_codes:
                                    page_found = code
                                    print(f"  [otp-dual] ✅ PAGE FOUND OTP: {code} ({elapsed}s)")
                                break

                        if not page_found:
                            code = extract_xai_code(page_html)
                            if code and code not in pre_codes:
                                page_found = code
                                print(f"  [otp-dual] ✅ PAGE FOUND OTP (scan): {code} ({elapsed}s)")

                except Exception:
                    pass

                # Refresh tab C
                try:
                    tab_c.get(inbox_url)
                except:
                    pass

            # Status log every 15s
            if elapsed > 0 and elapsed % 15 == 0:
                ws_str = {0: "conn", 1: "online", 2: "closing", 3: "closed"}.get(ws_state if tab_a else -1, "?")
                print(f"  [otp-dual] ...{elapsed}s | WSS: msgs={last_wss_count}, ws={ws_str}, otp={wss_found or '-'} | PAGE: otp={page_found or '-'}")

            # Stop if either found
            if wss_found:
                print(f"  [otp-dual] 🏆 WSS wins! OTP={wss_found} at {elapsed}s")
                self._safe_close_tab(tab_a)
                self._safe_close_tab(tab_c)
                return wss_found
            if page_found:
                print(f"  [otp-dual] 🏆 PAGE wins! OTP={page_found} at {elapsed}s")
                self._safe_close_tab(tab_a)
                self._safe_close_tab(tab_c)
                return page_found

            time.sleep(poll_interval)

        self._safe_close_tab(tab_a)
        self._safe_close_tab(tab_c)
        print(f"  [otp-dual] TIMEOUT {timeout}s — WSS: {wss_found or 'none'}, PAGE: {page_found or 'none'}")
        return wss_found or page_found

    def _legacy_poll_otp(self, timeout, poll_interval, target_email, inbox_url):
        """Legacy fallback: full-page refresh polling (high bandwidth)."""
        print(f"  [otp] Legacy polling: {inbox_url}")
        tab = None
        pre_codes = set()
        year_set = {"202020", "202120", "202220", "202320", "202420", "202520", "202620"}

        try:
            tab = self._browser.new_tab(inbox_url)
            time.sleep(5)
            pre_html = tab.html
            pre_codes = set(re.findall(r"([A-Z0-9]{3}-[A-Z0-9]{3})", pre_html))
            pre_codes.update(re.findall(r"([A-Z0-9]{6})", pre_html))
            pre_codes -= year_set
            print(f"  [otp] Pre-existing: {len(pre_codes)} codes")
        except Exception as e:
            print(f"  [otp] Init error: {e}")

        start = time.time()
        cycle = 0

        while time.time() - start < timeout:
            cycle += 1
            try:
                try:
                    _ = tab.html[:100] if tab else None
                except Exception:
                    print(f"  [otp] Reconnecting tab...")
                    try:
                        tab = self._browser.new_tab(inbox_url)
                    except Exception as e2:
                        print(f"  [otp] Reconnect failed: {e2}")
                        time.sleep(poll_interval)
                        continue
                    time.sleep(4)

                try:
                    page_html = tab.html
                except Exception as e:
                    print(f"  [otp] HTML read error: {str(e)[:40]}")
                    time.sleep(poll_interval)
                    continue

                has_xai = any(kw in page_html.lower() for kw in [
                    "xai", "spacexai", "x.ai", "confirmation code", "verify your email"
                ])

                if has_xai:
                    try:
                        items = tab.eles("css:a.list-group-item")
                    except Exception:
                        items = []

                    for item in items:
                        try:
                            itxt = item.text if hasattr(item, "text") else ""
                        except:
                            continue

                        if not any(kw in itxt.lower() for kw in [
                            "xai", "spacexai", "x.ai", "confirmation", "verify"
                        ]):
                            continue

                        item_codes = set(re.findall(r"([A-Z0-9]{3}-[A-Z0-9]{3})", itxt))
                        item_codes.update(re.findall(r"([A-Z0-9]{6})", itxt))
                        item_codes -= year_set
                        if item_codes and item_codes.issubset(pre_codes):
                            continue

                        print(f"  [otp] New email: {itxt[:50]}")
                        item.click()
                        time.sleep(2)

                        try:
                            body = tab.html
                        except:
                            body = ""

                        code = extract_xai_code(body)
                        if code and code not in pre_codes:
                            print(f"  [otp] CODE: {code}")
                            self._safe_close_tab(tab)
                            return code
                        break

                    code = extract_xai_code(page_html)
                    if code and code not in pre_codes:
                        print(f"  [otp] CODE (page): {code}")
                        self._safe_close_tab(tab)
                        return code

                if cycle % 5 == 0:
                    elapsed = int(time.time() - start)
                    item_count = page_html.count("list-group-item") if page_html else 0
                    print(f"  [otp] ...{elapsed}s, {item_count} items, xai={has_xai}")

            except Exception as e:
                print(f"  [otp] Cycle {cycle} error: {str(e)[:60]}")

            try:
                tab.get(inbox_url)
            except:
                pass
            time.sleep(poll_interval)

        self._safe_close_tab(tab)
        print(f"  [otp] TIMEOUT {timeout}s")
        return None

    def _safe_close(self):
        try:
            if self._email_tab:
                self._email_tab.close()
        except Exception:
            pass

    def _safe_close_tab(self, tab):
        try:
            if tab:
                tab.close()
        except Exception:
            pass
