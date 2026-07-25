"""Email generator and OTP polling via generator.email.

Uses browser to generate fresh email addresses directly from generator.email
(not hardcoded domains — those expire/break).

Flow:
1. Open generator.email in browser tab
2. Copy the auto-generated email address from the page
3. Use that email for xAI signup
4. Poll the same tab for incoming OTP emails
"""

import re
import time
from typing import Optional


def generate_email_from_browser(browser, max_attempts: int = 10) -> str:
    """Generate a fresh email address from generator.email via browser.

    Opens generator.email, clicks "Generate new e-mail" until we get
    a supported domain (not generator.email or blocked domains).

    Args:
        browser: DrissionPage ChromiumPage instance
        max_attempts: Max times to click "Generate new e-mail"

    Returns:
        full_email string

    Raises:
        RuntimeError if failed after max_attempts
    """
    UNSUPPORTED_DOMAINS = {"generator.email", "dharmadi.com"}

    tab = browser.new_tab("https://generator.email")
    time.sleep(5)

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

        # Read email from input fields
        try:
            email_input = tab.ele("css:input[aria-label*='username'], input[placeholder*='username']", timeout=3)
            domain_input = tab.ele("css:input[aria-label*='domain'], input[placeholder*='domain']", timeout=3)
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
    """Read OTP codes from generator.email via browser.

    Opens generator.email inbox and polls for new xAI emails.
    """

    def __init__(self, browser):
        """
        Args:
            browser: DrissionPage ChromiumPage instance (signup browser)
        """
        self._browser = browser
        self._email_tab = None

    def wait_for_otp(self, timeout: int = 180, poll_interval: float = 3.0,
                     target_email: str = "", **kwargs) -> Optional[str]:
        """Poll generator.email inbox for xAI OTP code.

        Uses persistent tab with auto-reconnect. More verbose logging.
        """
        if not target_email:
            print("  [otp] ERROR: No target_email")
            return None

        inbox_url = f"https://generator.email/{target_email}"
        print(f"  [otp] Polling: {inbox_url}")

        # Open tab + collect pre-existing codes
        tab = None
        pre_codes = set()
        try:
            tab = self._browser.new_tab(inbox_url)
            time.sleep(5)
            pre_html = tab.html
            pre_codes = set(re.findall(r"([A-Z0-9]{3}-[A-Z0-9]{3})", pre_html))
            pre_codes.update(re.findall(r"([A-Z0-9]{6})", pre_html))
            year_set = {"202020", "202120", "202220", "202320", "202420", "202520", "202620"}
            pre_codes -= year_set
            print(f"  [otp] Pre-existing: {len(pre_codes)} codes")
        except Exception as e:
            print(f"  [otp] Init error: {e}")

        start = time.time()
        cycle = 0

        while time.time() - start < timeout:
            cycle += 1
            try:
                # Reconnect if tab dead
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

                # Get page HTML
                try:
                    page_html = tab.html
                except Exception as e:
                    print(f"  [otp] HTML read error: {str(e)[:40]}")
                    time.sleep(poll_interval)
                    continue

                # Check for xAI content in page
                has_xai = any(kw in page_html.lower() for kw in [
                    "xai", "spacexai", "x.ai", "confirmation code", "verify your email"
                ])

                if has_xai:
                    # Try clicking email items
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

                        # Skip pre-existing
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

                    # Fallback: extract from full page
                    code = extract_xai_code(page_html)
                    if code and code not in pre_codes:
                        print(f"  [otp] CODE (page): {code}")
                        self._safe_close_tab(tab)
                        return code

                # Status log every 5 cycles
                if cycle % 5 == 0:
                    elapsed = int(time.time() - start)
                    item_count = page_html.count("list-group-item") if page_html else 0
                    print(f"  [otp] ...{elapsed}s, {item_count} items, xai={has_xai}")

            except Exception as e:
                print(f"  [otp] Cycle {cycle} error: {str(e)[:60]}")

            # Refresh
            try:
                tab.get(inbox_url)
            except:
                pass
            time.sleep(poll_interval)

        self._safe_close_tab(tab)
        print(f"  [otp] TIMEOUT {timeout}s")
        return None

    def _safe_close(self):
        """Close email tab without raising."""
        try:
            if self._email_tab:
                self._email_tab.close()
        except Exception:
            pass

    def _safe_close_tab(self, tab):
        """Close a specific tab without raising."""
        try:
            if tab:
                tab.close()
        except Exception:
            pass
