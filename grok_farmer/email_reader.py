"""IMAP OTP reader for catch-all email domains (e.g. Migadu).

Polls INBOX for xAI verification emails and extracts OTP code.
OTP format from xAI: XXX-XXX (3 dash 3, alphanumeric, e.g. A9E-WJR)
"""
import imaplib
import email
import re
import time
from typing import Optional


OTP_PATTERN = re.compile(r"([A-Z0-9]{3}-[A-Z0-9]{3})")
OTP_PATTERN_NODASH = re.compile(r"([A-Z0-9]{6})")


class IMAPOtpReader:
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._conn = None

    def connect(self):
        self._conn = imaplib.IMAP4_SSL(self.host, self.port)
        self._conn.login(self.user, self.password)

    def disconnect(self):
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    def _search_recent(self, since_minutes: int = 5) -> list:
        """Search for recent emails. Checks ALL new emails, not just from x.ai."""
        self._conn.select("INBOX")
        # Search ALL recent emails (catch-all domain receives everything)
        criteria = '(UNSEEN)'
        status, data = self._conn.search(None, criteria)
        if status != "OK":
            return []
        msg_ids = data[0].split()
        return msg_ids

    def _extract_otp_from_email(self, msg_bytes: bytes) -> Optional[str]:
        """Parse email and extract OTP code."""
        msg = email.message_from_bytes(msg_bytes)

        # Try all parts (text/plain and text/html)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct in ("text/plain", "text/html"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode("utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="replace")

        # Also check Subject header for OTP
        subject = msg.get("Subject", "")
        
        # Try XXX-XXX format in body first
        match = OTP_PATTERN.search(body)
        if match:
            return match.group(1)

        # Try XXX-XXX in subject (x.ai puts it there)
        match = OTP_PATTERN.search(subject)
        if match:
            return match.group(1)

        # Try 6-char without dash
        match = OTP_PATTERN_NODASH.search(body)
        if match:
            return match.group(1)

        match = OTP_PATTERN_NODASH.search(subject)
        if match:
            return match.group(1)

        return None

    def wait_for_otp(self, timeout: int = 300, poll_interval: float = 5.0,
                     target_email: str = "") -> Optional[str]:
        """Poll INBOX until OTP arrives or timeout.

        Tracks already-checked message IDs to avoid re-processing.
        Does NOT mark emails as seen (avoids race condition with catch-all).

        Args:
            timeout: Max seconds to wait
            poll_interval: Seconds between checks
            target_email: If set, only match OTP emails TO this address

        Returns OTP string like 'A9E-WJR' or None if timeout.
        """
        deadline = time.time() + timeout
        checked_ids = set()

        while time.time() < deadline:
            try:
                self._conn.select("INBOX")
                # Search ALL emails (not just UNSEEN — avoids mark_all_seen race)
                status, data = self._conn.search(None, "ALL")
                if status != "OK" or not data[0]:
                    time.sleep(poll_interval)
                    continue

                msg_ids = data[0].split()
                for mid in msg_ids:
                    if mid in checked_ids:
                        continue
                    checked_ids.add(mid)

                    # Fetch headers first (faster than full RFC822)
                    status, fdata = self._conn.fetch(mid, "(BODY[HEADER.FIELDS (TO SUBJECT FROM)])")
                    if status != "OK" or not fdata or not fdata[0]:
                        continue

                    header_raw = fdata[0][1]
                    if isinstance(header_raw, bytes):
                        header_text = header_raw.decode("utf-8", errors="replace")
                    else:
                        header_text = header_raw

                    # Quick filter: must be from x.ai
                    if "x.ai" not in header_text.lower():
                        continue

                    # Filter by target email if specified
                    if target_email and target_email.lower() not in header_text.lower():
                        continue

                    # Check subject for OTP first (faster)
                    import re
                    otp_match = re.search(r"([A-Z0-9]{3}-[A-Z0-9]{3})", header_text)
                    if otp_match:
                        otp = otp_match.group(1)
                        return otp

                    # Fallback: fetch full body
                    status, fdata = self._conn.fetch(mid, "(RFC822)")
                    if status == "OK" and fdata and fdata[0]:
                        raw = fdata[0][1]
                        otp = self._extract_otp_from_email(raw)
                        if otp:
                            return otp

            except Exception as e:
                # Reconnect on error
                try:
                    self.connect()
                    self._conn.select("INBOX")
                except Exception:
                    pass

            time.sleep(poll_interval)

        return None
