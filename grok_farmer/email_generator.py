"""Email generator and OTP polling via generator.email — bandwidth optimized.

Polls inbox using fetch() (AJAX) instead of full-page reload.
Blocks ad/tracking domains at CDP level to reduce data transfer.

Flow:
1. Open generator.email in browser tab (with ads blocked)
2. Copy the auto-generated email address from the page
3. Use that email for xAI signup
4. Poll inbox via fetch() — downloads only HTML text (~50KB vs ~500KB per reload)
5. When xAI email arrives, extract OTP code
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
        url_patterns = []
        for domain in BLOCKED_DOMAINS:
            url_patterns.append(f"*://{domain}/*")
            url_patterns.append(f"*://*.{domain}/*")

        browser.run_cdp("Network.enable")
        browser.run_cdp("Network.setBlockedURLs", urls=url_patterns)
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
    # xAI silently drops OTP or rejects signup for domains containing these
    BLOCKED_DOMAIN_PATTERNS = ["gmail", "googlemail", "outlook", "hotmail", "yahoo",
                               "getmails", "mailfirefly", "tempmail", "10minutemail"]

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
            domain_lower = domain.lower()
            if domain in UNSUPPORTED_DOMAINS:
                print(f"  [email] Domain {domain} unsupported, regenerating... (attempt {attempt+1})")
            elif any(pat in domain_lower for pat in BLOCKED_DOMAIN_PATTERNS):
                print(f"  [email] Domain {domain} matches blocked pattern, regenerating... (attempt {attempt+1})")
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
    """Read OTP codes from generator.email via page-refresh polling.

    Polls the inbox page using tab.get() (full page reload).
    CDP ad blocking is applied to the browser to reduce bandwidth.
    """

    def __init__(self, browser):
        self._browser = browser
        self._email_tab = None

    def wait_for_otp(self, timeout: int = 180, poll_interval: float = 3.0,
                     target_email: str = "", **kwargs) -> Optional[str]:
        """Wait for xAI OTP via page-refresh polling.

        Uses tab.get() to reload the inbox page each cycle.
        Set GROK_DUAL_COMPARE=1 to also run fetch() alongside for comparison.
        """
        if not target_email:
            print("  [otp] ERROR: No target_email")
            return None

        inbox_url = f"https://generator.email/{target_email}"
        dual = bool(os.environ.get("GROK_DUAL_COMPARE"))
        print(f"  [otp] Polling inbox: {target_email}" + (" (DUAL compare)" if dual else ""))

        year_set = {"202020", "202120", "202220", "202320", "202420", "202520", "202620"}

        tab = None
        pre_codes = set()
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

        if not tab:
            print("  [otp] Tab creation failed")
            return None

        start = time.time()

        while time.time() - start < timeout:
            elapsed = int(time.time() - start)

            try:
                # --- Method A: fetch() (lightweight, no re-render) ---
                if dual:
                    fetch_html = _run_js_safe(
                        tab,
                        f"""
                        (async function() {{
                            try {{
                                var resp = await fetch({json.dumps(inbox_url)}, {{
                                    headers: {{'X-Requested-With': 'XMLHttpRequest'}},
                                    credentials: 'same-origin'
                                }});
                                return await resp.text();
                            }} catch(e) {{
                                return 'ERROR:' + e.message;
                            }}
                        }})()
                        """,
                        timeout_sec=10,
                        default=None
                    )

                    fetch_len = len(fetch_html) if fetch_html else 0
                    fetch_has_xai = False
                    fetch_code = None
                    if fetch_html and not fetch_html.startswith("ERROR"):
                        fetch_lower = fetch_html.lower()
                        fetch_has_xai = any(kw in fetch_lower for kw in [
                            "xai", "spacexai", "x.ai", "confirmation", "verify"
                        ])
                        if fetch_has_xai:
                            fetch_code = extract_xai_code(fetch_html)
                            if fetch_code and fetch_code in pre_codes:
                                fetch_code = None

                    # --- Method B: tab.get() (full page reload) ---
                    tab.get(inbox_url)
                    time.sleep(2)
                    page_html = tab.html
                    page_len = len(page_html) if page_html else 0
                    page_has_xai = False
                    page_code = None
                    if page_html:
                        page_lower = page_html.lower()
                        page_has_xai = any(kw in page_lower for kw in [
                            "xai", "spacexai", "x.ai", "confirmation", "verify"
                        ])
                        if page_has_xai:
                            page_code = extract_xai_code(page_html)
                            if page_code and page_code in pre_codes:
                                page_code = None
                            # Try clicking into email if OTP not in list HTML
                            if not page_code:
                                items = re.findall(
                                    r'onclick=["\']loadInboxClientSide\(["\']([^"\']+)["\'])["\']',
                                    page_html
                                )
                                if not items:
                                    items = re.findall(
                                        r'href=["\']/([^"\']*(?:xai|spacexai|x\.ai|confirmation|verify)[^"\']*)["\']',
                                        page_html, re.IGNORECASE
                                    )
                                for item_link in items:
                                    email_url = f"https://generator.email/{item_link}"
                                    tab.get(email_url)
                                    time.sleep(2)
                                    email_html = tab.html
                                    if email_html:
                                        c = extract_xai_code(email_html)
                                        if c and c not in pre_codes:
                                            page_code = c
                                            break
                                    # Go back to inbox
                                    tab.get(inbox_url)
                                    time.sleep(1)

                    # Log comparison each cycle
                    print(f"  [otp-dual] {elapsed}s | fetch: {fetch_len}B xai={fetch_has_xai} code={fetch_code} | page: {page_len}B xai={page_has_xai} code={page_code}")

                    if page_code:
                        print(f"  [otp] PAGE wins! CODE: {page_code}")
                        self._safe_close_tab(tab)
                        return page_code
                    if fetch_code:
                        print(f"  [otp] FETCH wins! CODE: {fetch_code}")
                        self._safe_close_tab(tab)
                        return fetch_code

                else:
                    # --- Normal mode: tab.get() only ---
                    tab.get(inbox_url)
                    time.sleep(2)
                    page_html = tab.html

                    if page_html:
                        page_lower = page_html.lower()
                        has_xai = any(kw in page_lower for kw in [
                            "xai", "spacexai", "x.ai", "confirmation", "verify"
                        ])

                        if has_xai:
                            code = extract_xai_code(page_html)
                            if code and code not in pre_codes:
                                print(f"  [otp] CODE: {code}")
                                self._safe_close_tab(tab)
                                return code

                            # Try clicking into email
                            items = re.findall(
                                r'onclick=["\']loadInboxClientSide\(["\']([^"\']+)["\'])["\']',
                                page_html
                            )
                            if not items:
                                items = re.findall(
                                    r'href=["\']/([^"\']*(?:xai|spacexai|x\.ai|confirmation|verify)[^"\']*)["\']',
                                    page_html, re.IGNORECASE
                                )
                            for item_link in items:
                                email_url = f"https://generator.email/{item_link}"
                                tab.get(email_url)
                                time.sleep(2)
                                email_html = tab.html
                                if email_html:
                                    code = extract_xai_code(email_html)
                                    if code and code not in pre_codes:
                                        print(f"  [otp] CODE: {code}")
                                        self._safe_close_tab(tab)
                                        return code
                                tab.get(inbox_url)
                                time.sleep(1)

            except Exception as e:
                err_str = str(e)[:60]
                if "html" in err_str.lower() or "tab" in err_str.lower():
                    print(f"  [otp] Tab lost, reconnecting...")
                    try:
                        self._safe_close_tab(tab)
                        tab = self._browser.new_tab(inbox_url)
                        time.sleep(4)
                    except Exception:
                        pass
                else:
                    print(f"  [otp] Poll error: {err_str}")

            # Status log every 15s
            if elapsed > 0 and elapsed % 15 == 0:
                print(f"  [otp] ...{elapsed}s")

            current_interval = poll_interval if elapsed < 30 else min(poll_interval + 2, 5.0)
            time.sleep(current_interval)

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
