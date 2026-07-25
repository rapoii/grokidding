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

        Opens generator.email/{email} in a new tab, polls for emails.
        Only accepts codes from NEW emails (not pre-existing ones).

        Args:
            timeout: Max seconds to wait
            poll_interval: Seconds between refreshes
            target_email: Email address to check (required)

        Returns:
            OTP code string or None if timeout
        """
        if not target_email:
            print("  [otp] ERROR: No target_email provided")
            return None

        inbox_url = f"https://generator.email/{target_email}"
        print(f"  [otp] Opening inbox: {inbox_url}")

        # Open inbox in new tab
        self._email_tab = self._browser.new_tab(inbox_url)
        time.sleep(5)

        # Note: 'Email not supported' is a domain verification status, not a blocker

        # Collect pre-existing codes to skip them
        try:
            pre_html = self._email_tab.html
            pre_codes = set(re.findall(r'\b([A-Z0-9]{3}-[A-Z0-9]{3})\b', pre_html))
            pre_codes.update(re.findall(r'\b([A-Z0-9]{6})\b', pre_html))
            print(f"  [otp] Pre-existing codes to skip: {len(pre_codes)}")
        except Exception:
            pre_codes = set()

        start = time.time()
        check_count = 0

        while time.time() - start < timeout:
            check_count += 1
            try:
                # Check if tab is still alive
                try:
                    _ = self._email_tab.title
                except Exception:
                    print(f"  [otp] Tab closed, reopening...")
                    self._email_tab = self._browser.new_tab(inbox_url)
                    time.sleep(4)

                # Look for email items in inbox
                try:
                    items = self._email_tab.eles("css:#email-table a.list-group-item")
                    if not items:
                        items = self._email_tab.eles("css:a.list-group-item")
                except Exception:
                    items = []

                for item in items:
                    try:
                        item_text = item.text if hasattr(item, "text") else ""
                    except Exception:
                        continue

                    item_lower = item_text.lower()
                    is_xai = any(kw in item_lower for kw in [
                        "xai", "spacexai", "x.ai", "confirmation", "verify", "grok"
                    ])
                    if not is_xai:
                        continue

                    # Skip if this email's codes were already visible
                    item_codes = set(re.findall(r'\b([A-Z0-9]{3}-[A-Z0-9]{3})\b', item_text))
                    item_codes.update(re.findall(r'\b([A-Z0-9]{6})\b', item_text))
                    if item_codes and item_codes.issubset(pre_codes):
                        continue  # Pre-existing email, skip

                    # New xAI email found!
                    print(f"  [otp] New email: {item_text[:60]}")
                    item.click()
                    time.sleep(3)

                    try:
                        body_text = self._email_tab.html
                    except Exception:
                        body_text = ""

                    code = extract_xai_code(body_text)
                    if code and code not in pre_codes:
                        print(f"  [otp] Found code: {code}")
                        self._safe_close()
                        return code

                    # Go back to inbox
                    try:
                        self._email_tab.get(inbox_url)
                        time.sleep(2)
                    except Exception:
                        pass
                    break

                # Periodic status
                if check_count % 10 == 0:
                    elapsed = int(time.time() - start)
                    print(f"  [otp] Waiting for new xAI email... ({elapsed}s)")

            except Exception as e:
                if check_count <= 3:
                    print(f"  [otp] Check error: {e}")

            # Refresh inbox
            try:
                self._email_tab.refresh()
                time.sleep(poll_interval)
            except Exception:
                try:
                    self._email_tab.get(inbox_url)
                    time.sleep(poll_interval)
                except Exception:
                    pass

        # Timeout
        self._safe_close()
        print(f"  [otp] TIMEOUT after {timeout}s")
        return None

    def _safe_close(self):
        """Close email tab without raising."""
        try:
            if self._email_tab:
                self._email_tab.close()
        except Exception:
            pass
