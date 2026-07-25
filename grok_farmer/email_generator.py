"""Email generator and OTP polling via generator.email.

Replaces IMAP-based email reading. Uses browser to open generator.email
inbox and scrape OTP codes from incoming emails.

Usage:
    from .email_generator import GeneratorEmailReader

    reader = GeneratorEmailReader(browser_instance)
    otp = reader.wait_for_otp(timeout=180, target_email="xxx@domain.com")
"""

import random
import re
import string
import subprocess
import time
from typing import Optional


# Fallback domains if scraping fails
DEFAULT_DOMAINS = ["ferd.live", "gudri.com", "cihuy.net"]

# Known bad domains (blocked by platforms)
DOMAINS_BLOCKLIST = [
    "alightmotion.id", "angiiidayyy.click", "banri.xyz",
    "binancepools.cloud", "brenlova.com", "clousy.site",
    "embege.xyz", "herilev.top", "hitbtcpool.cloud",
    "kantclass.com", "mailvip.net", "mos-kwa.ru",
    "nanopools.info", "ndut.pro", "nodem.app",
    "p-aac.top", "rawr.foo", "suntuy.com",
    "vectorbrasil.app", "zumnime.me",
]


def get_available_domains() -> list[str]:
    """Scrape available email domains from generator.email.

    Falls back to DEFAULT_DOMAINS if scraping fails.
    """
    try:
        result = subprocess.run(
            ["curl", "-s", "https://generator.email", "--max-time", "15"],
            capture_output=True, text=True, timeout=20
        )
        html = result.stdout
        # Extract domains from quoted strings in the page
        domains = re.findall(r'"([a-z0-9.-]+\.[a-z]{2,})"', html)
        # Filter: only real email domains (skip CDN/analytics/w3c)
        skip = {
            "google-analytics.com", "googlesyndication.com",
            "googletagmanager.com", "jsdelivr.net", "w3.org",
            "googleapis.com", "gstatic.com",
        }
        domains = sorted(set(
            d for d in domains
            if d not in skip and d not in DOMAINS_BLOCKLIST and "." in d
        ))
        if domains:
            return domains
    except Exception:
        pass
    return DEFAULT_DOMAINS


def random_email(domains: list[str] = None) -> tuple[str, str, str]:
    """Generate random email address for generator.email.

    Returns: (full_email, user, domain)
    """
    if domains is None:
        domains = get_available_domains()
    user = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = random.choice(domains)
    return f"{user}@{domain}", user, domain


def extract_xai_code(text: str) -> Optional[str]:
    """Extract xAI OTP code from email text.

    xAI sends codes in format: XXX-XXX (e.g., V96-2ET)
    We strip the dash and return 6 chars.
    """
    # Pattern: XXX-XXX (3 chars, dash, 3 chars)
    dash_codes = re.findall(r"\b([A-Z0-9]{3}-[A-Z0-9]{3})\b", text)
    if dash_codes:
        return dash_codes[0].replace("-", "")

    # Fallback: 6-char alphanumeric
    alpha = re.findall(r"\b([A-Z0-9]{6})\b", text)
    if alpha:
        # Filter year-like codes
        year_codes = {"202020", "202120", "202220", "202320", "202420", "202520", "202620"}
        for c in alpha:
            if c not in year_codes:
                return c

    return None


class GeneratorEmailReader:
    """Read OTP codes from generator.email via browser.

    Compatible interface with IMAPOtpReader.wait_for_otp().
    Opens generator.email inbox in a new browser tab and polls for codes.
    """

    def __init__(self, browser):
        """
        Args:
            browser: DrissionPage ChromiumPage instance (signup browser)
        """
        self._browser = browser
        self._domains = None

    def get_domains(self) -> list[str]:
        """Get available domains (cached)."""
        if self._domains is None:
            self._domains = get_available_domains()
        return self._domains

    def generate_email(self) -> tuple[str, str, str]:
        """Generate random email using generator.email domains.

        Returns: (full_email, user, domain)
        """
        return random_email(self.get_domains())

    def wait_for_otp(self, timeout: int = 180, poll_interval: float = 3.0,
                     target_email: str = "", **kwargs) -> Optional[str]:
        """Poll generator.email inbox for xAI OTP code.

        Opens generator.email/{email} in a new tab, polls for emails.

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
        email_tab = self._browser.new_tab(inbox_url)
        time.sleep(4)

        start = time.time()
        check_count = 0
        seen_codes = set()

        while time.time() - start < timeout:
            check_count += 1
            try:
                # Check if tab is still alive
                try:
                    _ = email_tab.title
                except Exception:
                    print(f"  [otp] Tab closed, reopening...")
                    email_tab = self._browser.new_tab(inbox_url)
                    time.sleep(4)

                # Get page HTML
                try:
                    page_html = email_tab.html
                except Exception:
                    page_html = ""

                # Look for xAI email indicators
                page_lower = page_html.lower()
                has_xai = any(kw in page_lower for kw in [
                    "xai", "spacexai", "x.ai", "confirmation code",
                    "grok", "verify your email"
                ])

                if has_xai:
                    print(f"  [otp] xAI email detected, extracting code...")

                    # Try to click email rows to read body
                    try:
                        items = email_tab.eles("css:#email-table a.list-group-item")
                        if not items:
                            items = email_tab.eles("css:a.list-group-item")

                        for item in items:
                            try:
                                item_text = item.text if hasattr(item, "text") else ""
                            except Exception:
                                continue

                            item_lower = item_text.lower()
                            if any(kw in item_lower for kw in [
                                "xai", "spacexai", "confirmation", "verify", "grok"
                            ]):
                                print(f"  [otp] Clicking: {item_text[:60]}")
                                item.click()
                                time.sleep(3)

                                # Get body text
                                try:
                                    body_text = email_tab.html
                                except Exception:
                                    body_text = ""

                                code = extract_xai_code(body_text)
                                if code and code not in seen_codes:
                                    print(f"  [otp] Found code: {code}")
                                    self._safe_close_tab(email_tab)
                                    return code
                                elif code:
                                    seen_codes.add(code)

                                # Go back to inbox
                                try:
                                    email_tab.get(inbox_url)
                                    time.sleep(2)
                                except Exception:
                                    pass
                                break
                    except Exception as e:
                        print(f"  [otp] Click error: {e}")

                    # Fallback: try to extract from full page
                    code = extract_xai_code(page_html)
                    if code and code not in seen_codes:
                        print(f"  [otp] Found code from page: {code}")
                        self._safe_close_tab(email_tab)
                        return code

                # Periodic status
                if check_count % 10 == 0:
                    elapsed = int(time.time() - start)
                    print(f"  [otp] Still waiting... ({elapsed}s)")

            except Exception as e:
                if check_count <= 3:
                    print(f"  [otp] Check error: {e}")

            # Refresh inbox
            try:
                email_tab.refresh()
                time.sleep(poll_interval)
            except Exception:
                try:
                    email_tab.get(inbox_url)
                    time.sleep(poll_interval)
                except Exception:
                    pass

        # Timeout
        self._safe_close_tab(email_tab)
        print(f"  [otp] TIMEOUT after {timeout}s")
        return None

    def _safe_close_tab(self, tab):
        """Close tab without raising exceptions."""
        try:
            tab.close()
        except Exception:
            pass
