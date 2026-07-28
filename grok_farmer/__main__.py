"""Grokidding CLI — Main Entry Point.

Verified flow (MCP Playwright + DrissionPage):
  1. Navigate to accounts.x.ai/sign-up
  2. Accept cookies (if dialog)
  3. Click "Sign up with email"
  4. Fill email -> click "Sign up"
  5. Wait for OTP via IMAP
  6. Type OTP (6 chars, no dash) -> auto-submits
  7. Fill first name + last name + password
  8. Click "Complete sign up" -> redirects to grok.com
  9. OAuth device code flow
 10. Push token to 9Router

Key discoveries:
  - OTP auto-submits after 6 chars (input-otp library)
  - No "Confirm email" click needed
  - No login needed after signup (already logged in)
  - Device code page pre-fills code when user is authenticated
  - Real Chrome (DrissionPage) does NOT trigger Turnstile
"""
import argparse
import json
import os
import sys
import time
import traceback
import webbrowser
import threading
import msvcrt
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .email_reader import IMAPOtpReader
from .email_generator import GeneratorEmailReader, generate_email_from_browser
from .oauth import OAuthClient
from .proxy import ProxyRotator
from .router_push import RouterPusher
from .turnstile import TurnstileSolver
from .utils import generate_email, generate_password, generate_name, save_account, log_event

SIGNUP_URL = "https://accounts.x.ai/sign-up?redirect=grok-com&return_to=%2F"


# ─────────────────────────────────────────────
# DEBUG HELPERS
# ─────────────────────────────────────────────

def page_state(page, label=""):
    """Capture page state for debug."""
    try:
        url = page.url
        h1_el = page.ele("tag:h1", timeout=1)
        h1 = h1_el.text if h1_el else ""
        btns = len(page.eles("tag:button"))
        inps = len(page.eles("tag:input"))
        print(f"    [{label}] url={url[:80]}")
        print(f"    [{label}] h1={h1!r}, btns={btns}, inputs={inps}")
        return {"url": url, "h1": h1, "btns": btns, "inps": inps}
    except Exception as e:
        print(f"    [{label}] state error: {e}")
        return {}


def wait_for_h1(page, expected_text, timeout=15):
    """Wait until h1 contains expected_text."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            h1 = page.ele("tag:h1", timeout=1)
            if h1 and expected_text.lower() in (h1.text or "").lower():
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def click_button_js(page, text, label="btn"):
    """Click button by exact text via JS."""
    try:
        result = page.run_js(
            "const btns = document.querySelectorAll('button');"
            "for (const b of btns) {"
            f"  if (b.textContent.trim() === '{text}') {{ b.click(); return 'clicked'; }}"
            "}"
            "return 'not_found';"
        )
        print(f"    [{label}] '{text}': {result}")
        return result == "clicked"
    except Exception as e:
        print(f"    [{label}] error: {e}")
        return False


def click_button_containing(page, text, label="btn"):
    """Click button containing text (case-insensitive)."""
    try:
        result = page.run_js(
            "const btns = document.querySelectorAll('button');"
            "for (const b of btns) {"
            f"  if (b.textContent.trim().toLowerCase().includes('{text.lower()}')) {{ b.click(); return b.textContent.trim(); }}"
            "}"
            "return null;"
        )
        print(f"    [{label}] contains '{text}': {result}")
        return result is not None
    except Exception as e:
        print(f"    [{label}] error: {e}")
        return False


def fill_input_drissionpage(page, selector, value, label="fill"):
    """Fill input via DrissionPage .input() and verify."""
    try:
        el = page.ele(selector, timeout=3)
        if not el:
            print(f"    [{label}] not found: {selector}")
            return False
        el.click()
        time.sleep(0.2)
        el.clear()
        time.sleep(0.1)
        el.input(value)
        time.sleep(0.3)
        print(f"    [{label}] filled: {value[:30]}...")
        return True
    except Exception as e:
        print(f"    [{label}] error: {e}")
        return False


def fill_input_js(page, selector, value, label="fill"):
    """Fill input via JS nativeInputValueSetter."""
    try:
        js = (
            f"const inp = document.querySelector('{selector}');"
            "if (inp) {"
            "  const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;"
            f"  s.call(inp, '{value}');"
            "  inp.dispatchEvent(new Event('input', {bubbles: true}));"
            "  inp.dispatchEvent(new Event('change', {bubbles: true}));"
            f"  return inp.value;"
            "}"
            "return null;"
        )
        result = page.run_js(js)
        ok = result == value
        print(f"    [{label}] JS: match={ok}, got={str(result)[:30]}")
        return ok
    except Exception as e:
        print(f"    [{label}] JS error: {e}")
        return False


def submit_form_js(page, input_selector, label="submit"):
    """Submit form containing the input."""
    url_before = page.url
    try:
        page.run_js(
            f"const inp = document.querySelector('{input_selector}');"
            "if (inp && inp.form) { inp.form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})); }"
        )
        time.sleep(3)
        changed = url_before != page.url
        print(f"    [{label}] form submit: url_changed={changed}")
        return changed
    except Exception as e:
        print(f"    [{label}] error: {e}")
        return False


def dismiss_cookies(page):
    """Dismiss cookie dialog if present."""
    try:
        result = page.run_js(
            "const btns = document.querySelectorAll('button');"
            "for (const b of btns) {"
            "  const t = b.textContent.trim().toLowerCase();"
            "  if (t.includes('accept all cookies') || t === 'allow all' || t === 'reject all') {"
            "    b.click(); return t;"
            "  }"
            "}"
            "return 'none';"
        )
        if result != "none":
            print(f"    [cookies] dismissed: {result}")
            time.sleep(1)
    except Exception:
        pass


# ─────────────────────────────────────────────
# MAIN FLOW
# ─────────────────────────────────────────────

def run_single_account(cfg, solver, proxy_rotator, email_reader, pusher, dry_run=False, email_mode='imap'):
    ecfg = cfg["email"]
    scfg = cfg["signup"]
    ocfg = cfg["output"]

    # For IMAP mode, generate email now. For generator mode, generate after browser launch.
    if email_mode == 'generator':
        email = None  # will be generated after browser launch
        user_part, domain_part = "", ""
    else:
        email = generate_email(ecfg["domain"])
        user_part, domain_part = email.split("@", 1)
    password = generate_password(scfg.get("password_length", 16))
    first_name = generate_name()
    last_name = generate_name()  # separate random name for last
    proxy = proxy_rotator.next() if proxy_rotator.pool else ""

    result = {
        "email": email or "pending", "password": password,
        "first_name": first_name, "last_name": last_name,
        "proxy": proxy, "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": {}, "success": False,
    }

    # For generator mode, dry_run returns before browser launch — use placeholder
    if dry_run and email_mode == 'generator':
        result["steps"]["dry_run"] = {"generated": True, "mode": "generator"}
        result["success"] = True
        print(f"  [DRY RUN] mode=generator.email, name={first_name} {last_name}")
        return result
    elif dry_run:
        result["steps"]["dry_run"] = {"generated": True}
        result["success"] = True
        print(f"  [DRY RUN] email={email}, name={first_name} {last_name}")
        return result

    log_event(ocfg["logs_dir"], "START", {"email": email, "proxy": proxy[:40]})

    try:
        # ── INIT BROWSER ──
        if proxy:
            current_proxy = getattr(solver, '_proxy', None)
            if current_proxy != proxy:
                # New proxy — close and relaunch
                if solver._browser:
                    print("  [INIT] Closing browser for new proxy...")
                    solver.close()
                solver.set_proxy(proxy)
                print(f"  [INIT] Launching browser with proxy: {proxy[:35]}...")
            else:
                if not solver._browser:
                    solver.set_proxy(proxy)
                    print(f"  [INIT] Launching browser with proxy: {proxy[:35]}...")
        else:
            if not solver._browser:
                print("  [INIT] Launching browser (no proxy)...")

        if not solver._browser:
            solver._launch_browser()
        page = solver._browser

        # Generate email from browser + create reader (generator mode)
        if email_mode == "generator":
            email = generate_email_from_browser(solver._browser)
            user_part, domain_part = email.split("@", 1)
            result["email"] = email
            print(f"  [INIT] Generated email: {email}")
            email_reader = GeneratorEmailReader(solver._browser)
            print("  [INIT] GeneratorEmailReader ready")

        # Sign out any existing session (fresh start per account)
        try:
            page.get("https://accounts.x.ai/sign-out")
            time.sleep(2)
            print(f"  [INIT] Signed out existing session")
        except Exception:
            pass

        print(f"  [INIT] Browser ready")

        # ═══════════════════════════════════════
        # STEP 1: Navigate to signup page
        # ═══════════════════════════════════════
        print(f"\n  [1/10] Loading signup page...")
        page.get(SIGNUP_URL)
        time.sleep(3)
        st = page_state(page, "1")
        result["steps"]["1_load"] = {"h1": st.get("h1")}

        # ═══════════════════════════════════════
        # STEP 2: Accept cookies
        # ═══════════════════════════════════════
        print(f"  [2/10] Accepting cookies...")
        dismiss_cookies(page)
        result["steps"]["2_cookies"] = {"done": True}

        # ═══════════════════════════════════════
        # STEP 3: Click "Sign up with email"
        # ═══════════════════════════════════════
        print(f"  [3/10] Clicking 'Sign up with email'...")
        clicked = click_button_containing(page, "sign up with email", label="3")
        if not clicked:
            result["error"] = "Could not find 'Sign up with email' button"
            return result
        time.sleep(3)
        st = page_state(page, "3")
        result["steps"]["3_email_btn"] = {"h1": st.get("h1")}

        # Dismiss any secondary cookie dialog
        dismiss_cookies(page)

        # ═══════════════════════════════════════
        # STEP 4: Fill email
        # ═══════════════════════════════════════
        print(f"  [4/10] Filling email {email}...")
        filled = fill_input_drissionpage(page, "tag:input@type=email", email, label="4")
        if not filled:
            filled = fill_input_js(page, "input[type=email]", email, label="4-js")
        result["steps"]["4_email"] = {"filled": filled}
        if not filled:
            result["error"] = "Could not fill email"
            return result
        time.sleep(1)

        # ═══════════════════════════════════════
        # STEP 5: Click "Sign up" (submit email)
        # ═══════════════════════════════════════
        print(f"  [5/10] Clicking Sign up...")
        # Try multiple submission methods until page advances
        submitted = False
        for submit_attempt in range(5):
            # Method 1: JS click on "Sign up" button
            clicked = click_button_js(page, "Sign up", label=f"5-{submit_attempt}")
            time.sleep(2)

            # Check if page advanced to "Verify your email"
            h1_now = page.ele("tag:h1", timeout=1)
            h1_text = (h1_now.text or "").lower() if h1_now else ""
            if "verify" in h1_text:
                submitted = True
                break

            # Method 2: Enter key on email input
            try:
                email_el = page.ele("tag:input@type=email", timeout=1)
                if email_el:
                    email_el.input("\n")
                    time.sleep(2)
                    h1_now = page.ele("tag:h1", timeout=1)
                    h1_text = (h1_now.text or "").lower() if h1_now else ""
                    if "verify" in h1_text:
                        submitted = True
                        break
            except Exception:
                pass

            # Method 3: Form submit via JS
            submit_form_js(page, "input[type=email]", label=f"5-fb-{submit_attempt}")
            time.sleep(2)
            h1_now = page.ele("tag:h1", timeout=1)
            h1_text = (h1_now.text or "").lower() if h1_now else ""
            if "verify" in h1_text:
                submitted = True
                break

            print(f"    [5] Attempt {submit_attempt+1} failed, retrying...")

        st = page_state(page, "5")
        result["steps"]["5_signup"] = {"h1": st.get("h1"), "submitted": submitted}
        if not submitted:
            print(f"    [5] WARN: Could not advance to verify page after 5 attempts")

        # ═══════════════════════════════════════
        # STEP 6: Wait for OTP
        # ═══════════════════════════════════════
        if email_mode == 'generator':
            print(f"  [6/10] Waiting for OTP via generator.email for {email} (max 180s)...")
            otp = email_reader.wait_for_otp(timeout=180, poll_interval=3, target_email=email)
        else:
            email_reader._conn.select("INBOX")
            time.sleep(5)
            print(f"  [6/10] Waiting for OTP via IMAP for {email} (max 300s)...")
            otp = email_reader.wait_for_otp(timeout=300, poll_interval=5, target_email=email)
        if not otp:
            result["error"] = "OTP timeout (300s)"
            page_state(page, "6-timeout")
            return result
        otp_clean = otp.replace("-", "")
        print(f"  [6/10] OTP: {otp} -> {otp_clean}")
        result["steps"]["6_otp"] = {"raw": otp, "clean": otp_clean}

        # ═══════════════════════════════════════
        # STEP 7: Type OTP (auto-submits after 6 chars)
        # ═══════════════════════════════════════
        # Reconnect if page disconnected (generator.email tab may interfere)
        try:
            _ = page.url
        except Exception:
            print(f"    [7] Page disconnected, reconnecting...")
            try:
                page = solver._browser.latest_tab
            except Exception:
                page = solver._browser.get_tab(1)  # first tab
            print(f"    [7] Reconnected: {page.url[:60]}")

        # Wait until we're on the OTP verification page
        try:
            otp_page = wait_for_h1(page, "verify your email", timeout=10)
            if not otp_page:
                h1_now = page.ele("tag:h1", timeout=1)
                print(f"    [7] WARN: not on verify page, h1={h1_now.text if h1_now else '?'}")
        except Exception:
            print(f"    [7] WARN: page error during wait_for_h1, continuing...")
        print(f"  [7/10] Typing OTP {otp_clean}...")
        # Find OTP input — try specific selectors first, avoid email/password fields
        otp_el = None
        for otp_sel in [
            "tag:input@name=code",
            "@data-input-otp=true",
            "tag:input@maxlength=1",
            "tag:input@inputmode=numeric",
            "css:input[data-input-otp]",
            "css:input[autocomplete='one-time-code']",
        ]:
            try:
                el = page.ele(otp_sel, timeout=2)
                if el:
                    # Verify it's NOT an email/password field
                    ftype = el.attr("type") or ""
                    fname = el.attr("name") or ""
                    if ftype not in ("email", "password") and "email" not in fname.lower():
                        otp_el = el
                        print(f"    [7] Found OTP input: {otp_sel}")
                        break
            except Exception:
                pass
        if not otp_el:
            # Last resort: find any text input that's NOT email/password
            all_inputs = page.eles("tag:input", timeout=2)
            for inp in (all_inputs or []):
                ftype = inp.attr("type") or ""
                fname = inp.attr("name") or ""
                if ftype not in ("email", "password", "hidden") and "email" not in fname.lower():
                    otp_el = inp
                    print(f"    [7] Fallback OTP input: type={ftype}, name={fname}")
                    break
        if otp_el:
            otp_el.click()
            time.sleep(0.3)
            # Type character by character (input-otp library)
            for ch in otp_clean:
                otp_el.input(ch)
                time.sleep(0.15)
            time.sleep(1)
            # Press Enter to trigger submit (input-otp auto-submits on 6 chars,
            # but just in case)
            otp_el.input("\n")
            time.sleep(2)
            # Verify OTP was typed into correct field
            val = page.run_js(
                'const inputs = document.querySelectorAll("input");'
                'for (const inp of inputs) {'
                '  const t = inp.type || "";'
                '  const n = inp.name || "";'
                '  if (t !== "email" && t !== "password" && t !== "hidden" && !n.includes("email") && inp.value) {'
                '    return inp.value;'
                '  }'
                '}'
                'return "";'
            )
            print(f"    [7] input value: {val}")
            result["steps"]["7_otp_fill"] = {"value": val, "match": val == otp_clean}
        else:
            print(f"    [7] ERROR: No input found!")
            result["steps"]["7_otp_fill"] = {"error": "no input"}

        # Wait for auto-advance to "Complete your sign up"
        print(f"  [7/10] Waiting for profile page...")
        advanced = wait_for_h1(page, "complete your sign up", timeout=10)
        if not advanced:
            # Maybe already advanced
            st = page_state(page, "7-check")
            if "complete" in st.get("h1", "").lower():
                advanced = True
        print(f"    [7] advanced to profile page: {advanced}")
        result["steps"]["7_advanced"] = advanced

        # ═══════════════════════════════════════
        # STEP 8: Fill profile (first name, last name, password)
        # ═══════════════════════════════════════
        print(f"  [8/10] Filling profile...")
        st = page_state(page, "8")

        # Find and fill first name
        first_filled = False
        for sel in ["tag:input@name=givenName", "tag:input@name=firstName", "tag:input@placeholder*First"]:
            try:
                el = page.ele(sel, timeout=2)
                if el:
                    el.click()
                    el.clear()
                    el.input(first_name)
                    first_filled = True
                    print(f"    [8] first name: {first_name}")
                    break
            except Exception:
                pass

        # Find and fill last name
        last_filled = False
        for sel in ["tag:input@name=familyName", "tag:input@name=lastName", "tag:input@placeholder*Last"]:
            try:
                el = page.ele(sel, timeout=2)
                if el:
                    el.click()
                    el.clear()
                    el.input(last_name)
                    last_filled = True
                    print(f"    [8] last name: {last_name}")
                    break
            except Exception:
                pass

        # Fill password
        pwd_filled = False
        pwd_els = page.eles("tag:input@type=password")
        if not pwd_els:
            # Some sites use type=text for password fields
            pwd_els = page.eles("tag:input@name=password")
        for pi in pwd_els:
            try:
                pi.click()
                pi.clear()
                pi.input(password)
                pwd_filled = True
                print(f"    [8] password filled")
                break
            except Exception:
                pass

        result["steps"]["8_profile"] = {
            "first_name": first_filled,
            "last_name": last_filled,
            "password": pwd_filled,
        }

        # ═══════════════════════════════════════
        # STEP 9: Click "Complete sign up" (with Turnstile retry)
        # ═══════════════════════════════════════
        print(f"  [9/10] Clicking 'Complete sign up'...")
        redirected = False
        for ts_attempt in range(3):
            # Wait for Turnstile auto-solve (extension patches MouseEvent)
            # The turnstile_patch extension handles this automatically
            for _ts_wait in range(30):
                ts_val = page.run_js(
                    "try { return document.querySelector('input[name=cf-turnstile-response]')?.value || '' }"
                    " catch(e) { return '' }"
                )
                if ts_val and len(ts_val) > 10:
                    print(f"    [9] Turnstile auto-solved!")
                    break
                time.sleep(1)
            else:
                # Manual solve fallback
                try:
                    ts_el = page.ele("@name=cf-turnstile-response", timeout=2)
                    if ts_el:
                        print(f"    [9] Turnstile not auto-solved, trying manual...")
                        solver.solve_turnstile()
                        time.sleep(2)
                except Exception:
                    pass

            clicked = click_button_js(page, "Complete sign up", label=f"9-{ts_attempt}")
            if not clicked:
                submit_form_js(page, "input[type=password]", label=f"9-fb-{ts_attempt}")
            time.sleep(8)
            st = page_state(page, f"9-{ts_attempt}")

            # Check for common errors on the page
            try:
                page_text = page.run_js("return document.body?.innerText || ''")
                for err in ['too weak', 'already registered', 'invalid', 'try again', 'failed', 'blocked']:
                    if err.lower() in (page_text or '').lower():
                        print(f"    [9] PAGE ERROR: '{err}' detected!")
                        result["error"] = f"Page error: {err}"
            except Exception:
                pass

            try:
                current_url = page.url
            except Exception as nav_err:
                if "disconnected" in str(nav_err).lower():
                    print(f"    [9] Page disconnected — likely redirected to grok.com")
                    redirected = True
                    break
                raise

            if "grok.com" in current_url:
                redirected = True
                break

            # If redirected to Cloudflare or other non-xAI page, go back
            if "accounts.x.ai" not in current_url:
                print(f"    [9] Redirected to {current_url[:60]}, going back...")
                page.get(SIGNUP_URL)
                time.sleep(3)
                h1_now = page.ele("tag:h1", timeout=2)
                if h1_now and "complete" in (h1_now.text or "").lower():
                    continue
                else:
                    break

        try:
            final_url = page.url
        except Exception:
            final_url = "disconnected"
        print(f"    [9] redirected to grok.com: {redirected}")
        result["steps"]["9_complete"] = {"redirected": redirected, "url": final_url[:80]}

        if not redirected:
            try:
                err_url = page.url[:60]
            except Exception:
                err_url = "disconnected"
            result["error"] = f"Signup may have failed after 3 attempts. URL: {err_url}"
            # Don't return yet — try OAuth anyway


        # ═══════════════════════════════════════
        # STEP 10: OAuth device code flow
        # ═══════════════════════════════════════
        # 9Router device-code returns codeVerifier (PKCE). xAI poll needs it.
        # We poll xAI directly (9Router poll is broken).
        # Reconnect to browser if page was disconnected during step 9 redirect
        try:
            _ = page.url  # test connection
        except Exception:
            print(f" [10] Page disconnected after redirect, reconnecting...")
            try:
                page = solver._browser.get_tab()
                print(f" [10] Reconnected: {page.url[:60]}")
            except Exception:
                page = solver._browser
                print(f" [10] Using main browser object")

        router_url = pusher.base_url if pusher else ocfg.get("base_url", "http://localhost:20128")
        print(f"\n [10/10] OAuth device code flow...")
        # Re-login to 9Router (session may have expired during signup)
        if pusher:
            pusher.login()
        oauth_client = OAuthClient(
            router_url=router_url,
            router_password=ocfg.get("password", "rafi12345"),
            debug=True,
        )
        device_result = oauth_client.request_device_code()
        if "error" in device_result:
            result["error"] = f"Device code failed: {device_result['error']}"
            return result

        user_code = device_result.get("user_code")
        device_code = device_result.get("device_code")
        code_verifier = device_result.get("codeVerifier", "")
        interval = device_result.get("interval", 5)
        print(f" [10] device code: {user_code}")
        result["steps"]["10_device"] = {"user_code": user_code}

        # Start direct xAI poll BEFORE browser approval
        poll_result = {"token": None, "error": None}

        def _poll():
            try:
                poll_result["token"] = oauth_client.poll_token(
                    device_code, code_verifier=code_verifier,
                    interval=interval, timeout=180,
                )
            except Exception as e:
                poll_result["error"] = str(e)

        poll_thread = threading.Thread(target=_poll, daemon=True)
        poll_thread.start()
        print(f" [10] Token poll started (direct xAI)")

        # Navigate to CONSENT page directly (not /device which needs a click-through)
        consent_url = f"https://accounts.x.ai/oauth2/device/consent?user_code={user_code}"
        page.get(consent_url)
        time.sleep(3)
        st = page_state(page, "10-consent")

        if "sign-in" in page.url:
            print(f" [10] Redirected to sign-in — not logged in!")
            result["error"] = "Not logged in — cannot approve device code"
            return result

        # Click Continue
        clicked = click_button_js(page, "Continue", label="10-continue")
        if not clicked:
            clicked = click_button_js(page, "Approve", label="10-continue-alt")
        time.sleep(2)
        st = page_state(page, "10-after-continue")

        # Click Allow
        approval_done = False
        for allow_attempt in range(5):
            url = page.url
            if "done" in url or "authorized" in url or "success" in url:
                approval_done = True
                print(f" [10-allow] Already authorized (URL)")
                break
            try:
                body = page.ele("css:body").text if page.ele("css:body", timeout=1) else ""
                if any(x in body.lower() for x in ["authorized", "success", "you can close", "device authorized"]):
                    approval_done = True
                    print(f" [10-allow] Found success text!")
                    break
            except Exception:
                pass

            # Strategy 1: Form submit (proven in message.txt — most reliable)
            try:
                form_result = page.run_js(
                    "const form = document.querySelector('form');"
                    "if (form) {"
                    "  const actionInput = form.querySelector('input[name=\"action\"]');"
                    "  if (actionInput) actionInput.value = 'allow';"
                    "  form.submit();"
                    "  return 'form_submitted';"
                    "}"
                    "return 'no_form';"
                )
                if form_result == 'form_submitted':
                    clicked = True
                    print(f" [10-allow] Form submit: {form_result}")
            except Exception:
                pass

            # Strategy 2: Native DrissionPage click (isTrusted:true)
            if not clicked:
                try:
                    for btn_text in ["Allow", "Authorize", "Confirm", "Allow All"]:
                        el = page.ele(f"text:{btn_text}", timeout=1)
                        if el:
                            el.click()
                            clicked = True
                            print(f" [10-allow] Native click: {btn_text}")
                            break
                except Exception:
                    pass

            # Strategy 3: JS button click (last resort — may not trigger React)
            if not clicked:
                clicked = click_button_js(page, "Allow", label=f"10-allow-{allow_attempt}")
                if not clicked:
                    clicked = click_button_js(page, "Authorize", label=f"10-auth-{allow_attempt}")

            if not clicked:
                print(f" [10-allow] No Allow button found (attempt {allow_attempt+1})")
                time.sleep(2)
                continue

            time.sleep(3)
            url = page.url
            if "done" in url or "authorized" in url or "success" in url:
                approval_done = True
                print(f" [10-allow] Authorized after click!")
                break
            try:
                body = page.ele("css:body").text if page.ele("css:body", timeout=1) else ""
                if any(x in body.lower() for x in ["authorized", "success", "you can close", "device authorized"]):
                    approval_done = True
                    print(f" [10-allow] Success text after click!")
                    break
            except Exception:
                pass
            time.sleep(2)

        if not approval_done:
            print(f" [10-allow] WARN: approval may not have completed")

        # Wait for poll result
        print(f" [10] Waiting for token poll...")
        poll_thread.join(timeout=180)

        token_result = poll_result.get("token") or {}
        if poll_result.get("error"):
            print(f" [10] Poll thread error: {poll_result['error']}")
        if "error" in token_result or not token_result.get("access_token"):
            err = token_result.get("error") or poll_result.get("error") or "no token"
            result["error"] = f"Token poll failed: {err}"
            print(f" [10] FAIL: {err}")
            return result

        access_token = token_result.get("access_token", "")
        refresh_token = token_result.get("refresh_token", "")
        print(f" [10] Token obtained! at={len(access_token)} chars, rt={len(refresh_token)} chars")
        result["steps"]["10_token"] = {
            "access_token_len": len(access_token),
            "refresh_token_len": len(refresh_token),
            "expires_in": token_result.get("expires_in"),
        }

        # ═══════════════════════════════════════
        # STEP 11: Push to 9Router
        # ═══════════════════════════════════════
        print(f"\n [11/11] Pushing to 9Router...")
        push_result = pusher.push_via_api(access_token)
        print(f" [11-api] {push_result}")

        push_sql = pusher.push_via_sqlite(
            access_token=access_token,
            refresh_token=refresh_token,
            email=email,
            display_name=f"{first_name} {last_name}",
            expires_in=token_result.get("expires_in", 21600),
            scope=token_result.get("scope", ""),
            id_token=token_result.get("id_token", ""),
        )
        print(f" [11-sql] {push_sql}")

        if push_result.get("ok") or push_sql.get("ok"):
            result["success"] = True
            result["steps"]["11_push"] = {"api": push_result, "sql": push_sql}
            print(f"\n ✅ SUCCESS: {email} -> 9Router!")
            log_event(ocfg["logs_dir"], "SUCCESS", {"email": email, "at_len": len(access_token)})
        else:
            result["error"] = f"Push failed: {push_result} / {push_sql}"

        # ═══════════════════════════════════════
        # STEP 11: Push to 9Router
        # ═══════════════════════════════════════
        print(f"\n [11/11] Pushing to 9Router...")
        push_result = pusher.push_via_api(access_token)
        print(f" [11-api] {push_result}")

        push_sql = pusher.push_via_sqlite(
            access_token=access_token,
            refresh_token=refresh_token,
            email=email,
            display_name=f"{first_name} {last_name}",
            expires_in=token_result.get("expires_in", 21600),
            scope=token_result.get("scope", ""),
            id_token=token_result.get("id_token", ""),
        )
        print(f" [11-sql] {push_sql}")

        if push_result.get("ok") or push_sql.get("ok"):
            result["success"] = True
            result["steps"]["11_push"] = {"api": push_result, "sql": push_sql}
            print(f"\n ✅ SUCCESS: {email} -> 9Router!")
            log_event(ocfg["logs_dir"], "SUCCESS", {"email": email, "at_len": len(access_token)})
        else:
            result["error"] = f"Push failed: {push_result} / {push_sql}"

    except Exception as e:
        result["error"] = f"Exception: {e}"
        traceback.print_exc()
        log_event(ocfg["logs_dir"], "ERROR", {"email": email, "error": str(e)})

    save_account(result, ocfg["accounts_dir"])
    return result


def cmd_run(args):
    """Run the farming process (default subcommand)."""
    cfg = load_config(args.config)
    email_mode = cfg.get("email", {}).get("mode", "generator")

    print("=" * 60)
    print("  GROKKIDDING -> 9Router")
    print("=" * 60)
    print(f"  Target: {cfg['ninrouter']['base_url']}")
    print(f"  Email:  {email_mode}")
    print(f"  Count:  {args.count}")
    if args.dry_run:
        print(f"  Mode: DRY RUN")
    print("=" * 60)

    proxy_rotator = ProxyRotator(
        pool=[] if args.no_proxy else cfg["proxy"]["pool"],
        mode=cfg["proxy"].get("mode", "socks5"),
        adb_config=cfg["proxy"].get("adb"),
    )

    # Email reader: generator.email or IMAP
    ecfg = cfg.get("email", {})
    if email_mode == "generator":
        print(f"  [OK] Email mode: generator.email (browser-based)")
        email_reader = None  # created per-account using browser
    else:
        email_reader = IMAPOtpReader(ecfg["imap_host"], ecfg["imap_port"], ecfg["email"], ecfg["password"])
        email_reader.connect()
        print(f"  [OK] IMAP connected")

    pusher = RouterPusher(
        cfg["ninrouter"]["base_url"], cfg["ninrouter"]["password"],
        cfg["ninrouter"].get("db_path"), debug=True,
    )
    pusher.login()
    print(f"  [OK] 9Router logged in")

    tcfg = cfg["turnstile"]
    solver = TurnstileSolver(
        extension_path=tcfg.get("extension_path", "turnstile_patch/"),
        max_retries=tcfg.get("max_retries", 15),
        timeout=tcfg.get("timeout", 60), debug=True,
    )

    results = []
    for i in range(args.count):
        print(f"\n{'='*60}")
        print(f"  Account {i+1}/{args.count}")
        print(f"{'='*60}")

        # For generator.email mode, create reader from browser
        current_reader = email_reader
        if email_mode == "generator" and solver._browser:
            from .email_generator import GeneratorEmailReader
            current_reader = GeneratorEmailReader(solver._browser)

        try:
            result = run_single_account(
                cfg, solver, proxy_rotator, current_reader, pusher,
                args.dry_run, email_mode=email_mode,
            )
            results.append(result)
            s = "SUCCESS" if result.get("success") else f"FAIL: {result.get('error', '?')[:80]}"
            print(f"\n  RESULT: {s}")
        except Exception as e:
            print(f"  FATAL ERROR: {e}")
            traceback.print_exc()
            results.append({"error": str(e), "success": False})

        # Close browser between accounts to get fresh session
        if i < args.count - 1:
            print(f"\n  Closing browser for fresh session...")
            solver.close()
            time.sleep(5)

    success = sum(1 for r in results if r.get("success"))
    print(f"\n{'='*60}")
    print(f"  DONE: {success}/{args.count} accounts created")
    print(f"{'='*60}")

    if email_mode != "generator" and email_reader:
        email_reader.disconnect()
    solver.close()
    return 0 if success > 0 else 1


def cmd_panel(args):
    """Start the web panel server."""
    from .panel import run_panel
    run_panel(host=args.host, port=args.port)


def cmd_launcher(args):
    """Interactive launcher with arrow-key menu."""
    from .panel import run_panel

    port = args.port or 8083
    host = args.host or "127.0.0.1"
    url = f"http://{host}:{port}"

    # Start panel in background thread
    server_thread = threading.Thread(
        target=run_panel, kwargs={"host": host, "port": port},
        daemon=True,
    )
    server_thread.start()
    time.sleep(1.5)
    webbrowser.open(url)

    options = ["Open Web UI", "Exit"]
    selected = 0

    def draw_menu():
        os.system("cls" if os.name == "nt" else "clear")
        print()
        print("=" * 52)
        print("  Grokidding v1.0.0")
        print("=" * 52)
        print(f"  Server : {url}")
        print("=" * 52)
        print()
        for i, opt in enumerate(options):
            prefix = "  > " if i == selected else "    "
            print(f"{prefix}{opt}")
        print()
        print("  (Arrow keys to navigate, Enter to select)")

    draw_menu()

    while True:
        try:
            key = msvcrt.getch()
            # Arrow keys: first byte is 0xE0 or 0x00, second byte is the actual key
            if key in (b"\xe0", b"\x00"):
                key2 = msvcrt.getch()
                if key2 == b"H":  # Up arrow
                    selected = (selected - 1) % len(options)
                    draw_menu()
                elif key2 == b"P":  # Down arrow
                    selected = (selected + 1) % len(options)
                    draw_menu()
            elif key == b"\r":  # Enter
                if selected == 0:  # Open Web UI
                    webbrowser.open(url)
                elif selected == 1:  # Exit
                    os.system("cls" if os.name == "nt" else "clear")
                    print("\n  Sampai jumpa! \U0001f44b\n")
                    break
            elif key == b"\x1b":  # Escape
                os.system("cls" if os.name == "nt" else "clear")
                print("\n  Sampai jumpa! \U0001f44b\n")
                break
        except KeyboardInterrupt:
            os.system("cls" if os.name == "nt" else "clear")
            print("\n  Sampai jumpa! \U0001f44b\n")
            break

    return 0

def main():
    parser = argparse.ArgumentParser(description="Grokidding -> 9Router")
    subparsers = parser.add_subparsers(dest="command")

    # ── run ──
    run_parser = subparsers.add_parser("run", help="Run farming via CLI")
    run_parser.add_argument("--count", type=int, default=1, help="Number of accounts")
    run_parser.add_argument("--config", type=str, help="Config file path")
    run_parser.add_argument("--dry-run", action="store_true", help="Generate credentials only")
    run_parser.add_argument("--no-proxy", action="store_true", help="Skip proxy rotation")

    # ── tui (default) ──
    tui_parser = subparsers.add_parser("tui", help="Start TUI dashboard (default)")

    # ── panel (legacy) ──
    panel_parser = subparsers.add_parser("panel", help="[Legacy] Start web control panel")
    panel_parser.add_argument("--port", type=int, default=8083, help="Server port")
    panel_parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    panel_parser.add_argument("--config", type=str, help="Config file path")

    args = parser.parse_args()

    # Route to subcommand
    if args.command == "panel":
        print("[WARN] Web panel is legacy. Use 'tui' for the new Terminal UI.")
        return cmd_panel(args)
    elif args.command == "run":
        return cmd_run(args)
    else:
        # Default: TUI
        from .tui import GrokiddingTUI
        app = GrokiddingTUI()
        app.run()


if __name__ == "__main__":
    sys.exit(main())
