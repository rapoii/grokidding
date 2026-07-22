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
import sys
import time
import traceback
import webbrowser
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .email_reader import IMAPOtpReader
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

def run_single_account(cfg, solver, proxy_rotator, email_reader, pusher, dry_run=False):
    ecfg = cfg["email"]
    scfg = cfg["signup"]
    ocfg = cfg["output"]

    email = generate_email(ecfg["domain"])
    password = generate_password(scfg.get("password_length", 16))
    first_name = generate_name()
    last_name = generate_name()  # separate random name for last
    proxy = proxy_rotator.next() if proxy_rotator.pool else ""

    result = {
        "email": email, "password": password,
        "first_name": first_name, "last_name": last_name,
        "proxy": proxy, "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": {}, "success": False,
    }

    if dry_run:
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
        clicked = click_button_js(page, "Sign up", label="5")
        if not clicked:
            submit_form_js(page, "input[type=email]", label="5-fallback")
        time.sleep(3)
        st = page_state(page, "5")
        result["steps"]["5_signup"] = {"h1": st.get("h1")}

        # ═══════════════════════════════════════
        # STEP 6: Wait for OTP via IMAP
        # ═══════════════════════════════════════
        email_reader._conn.select("INBOX")
        time.sleep(5)
        print(f"  [6/10] Waiting for OTP for {email} (max 300s)...")
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
        # Wait until we're on the OTP verification page
        otp_page = wait_for_h1(page, "verify your email", timeout=10)
        if not otp_page:
            h1_now = page.ele("tag:h1", timeout=1)
            print(f"    [7] WARN: not on verify page, h1={h1_now.text if h1_now else '?'}")
        print(f"  [7/10] Typing OTP {otp_clean}...")
        otp_el = page.ele("tag:input@name=code", timeout=3)
        if not otp_el:
            otp_el = page.ele("@data-input-otp=true", timeout=2)
        if not otp_el:
            otp_el = page.ele("tag:input", timeout=3)
        if otp_el:
            otp_el.click()
            time.sleep(0.3)
            # Type character by character (input-otp library)
            for ch in otp_clean:
                otp_el.input(ch)
                time.sleep(0.15)
            time.sleep(2)
            # Verify OTP was typed into correct field
            val = page.run_js('return document.querySelector("input[name=code]")?.value || document.querySelector("input")?.value || ""')
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
        # STEP 9: Click "Complete sign up"
        # ═══════════════════════════════════════
        print(f"  [9/10] Clicking 'Complete sign up'...")
        clicked = click_button_js(page, "Complete sign up", label="9")
        if not clicked:
            # Try form submit
            submit_form_js(page, "input[type=password]", label="9-fallback")
        time.sleep(5)
        st = page_state(page, "9")

        # Check if redirected to grok.com
        redirected = "grok.com" in page.url
        print(f"    [9] redirected to grok.com: {redirected}")
        result["steps"]["9_complete"] = {"redirected": redirected, "url": page.url[:80]}

        if not redirected:
            # Handle Turnstile if needed
            try:
                ts_el = page.ele("@name=cf-turnstile-response", timeout=3)
                if ts_el:
                    print(f"    [9] Turnstile detected! Solving...")
                    solver.solve_turnstile()
                    time.sleep(3)
                    clicked = click_button_js(page, "Complete sign up", label="9-ts")
                    time.sleep(5)
                    redirected = "grok.com" in page.url
            except Exception:
                pass

        if not redirected:
            result["error"] = f"Signup may have failed. URL: {page.url[:60]}"
            # Don't return yet — try OAuth anyway

        # ═══════════════════════════════════════
        # STEP 10: OAuth device code flow
        # ═══════════════════════════════════════
        print(f"\n  [10/10] OAuth device code flow...")
        oauth_client = OAuthClient(debug=True)
        device_result = oauth_client.request_device_code()
        if "error" in device_result:
            result["error"] = f"Device code failed: {device_result['error']}"
            return result

        user_code = device_result.get("user_code")
        device_code = device_result.get("device_code")
        verification_uri = device_result.get("verification_uri", "https://accounts.x.ai/oauth2/device")
        interval = device_result.get("interval", 5)
        print(f"    [10] device code: {user_code}")
        result["steps"]["10_device"] = {"user_code": user_code}

        # Navigate to approval page (code pre-filled if logged in)
        approval_url = f"{verification_uri}?user_code={user_code}"
        page.get(approval_url)
        time.sleep(3)
        st = page_state(page, "10-approval")

        # Check if redirected to sign-in (not logged in)
        if "sign-in" in page.url:
            print(f"    [10] Redirected to sign-in — not logged in!")
            result["error"] = "Not logged in — cannot approve device code"
            return result

        # Click "Continue"
        clicked = click_button_js(page, "Continue", label="10-continue")
        if not clicked:
            result["error"] = "Could not click Continue on device code page"
            return result
        time.sleep(3)
        st = page_state(page, "10-consent")

        # Click "Allow"
        # Try DrissionPage click first (more reliable for React)
        allow_clicked = False
        try:
            btns = page.eles("tag:button")
            for b in btns:
                if (b.text or "").strip() == "Allow":
                    b.click()
                    allow_clicked = True
                    print(f"    [10-allow] DrissionPage: clicked")
                    break
        except Exception as e:
            print(f"    [10-allow] DrissionPage error: {e}")

        if not allow_clicked:
            allow_clicked = click_button_js(page, "Allow", label="10-allow")

        if not allow_clicked:
            result["error"] = "Could not click Allow on consent page"
            return result

        # Wait for redirect to /done or "Device Authorized"
        print(f"    [10-allow] Waiting for approval confirmation...")
        approval_done = False
        for _ in range(20):  # up to 20 seconds
            time.sleep(1)
            url = page.url
            if "/done" in url or "/approve" in url:
                # Check for "Device Authorized" text
                try:
                    body_text = page.run_js('return document.body?.innerText?.substring(0, 200) || ""')
                    if "authorized" in body_text.lower() or "device" in body_text.lower():
                        approval_done = True
                        print(f"    [10-allow] Approval confirmed: {body_text[:80]}")
                        break
                except Exception:
                    pass
            if "/done" in url:
                approval_done = True
                break

        page_state(page, "10-done")
        if not approval_done:
            print(f"    [10-allow] WARN: approval may not have completed")

        # Poll for token
        print(f"    [10] Polling for OAuth token...")
        token_result = oauth_client.poll_token(device_code, interval=interval, timeout=120)
        if "error" in token_result:
            result["error"] = f"Token poll failed: {token_result['error']}"
            return result

        access_token = token_result.get("access_token", "")
        refresh_token = token_result.get("refresh_token", "")
        print(f"    [10] Token obtained! at={len(access_token)} chars, rt={len(refresh_token)} chars")
        result["steps"]["10_token"] = {
            "access_token_len": len(access_token),
            "refresh_token_len": len(refresh_token),
            "expires_in": token_result.get("expires_in"),
        }

        # ── PUSH TO 9ROUTER ──
        print(f"\n  [PUSH] Pushing to 9Router...")
        push_result = pusher.push_via_api(access_token)
        result["steps"]["push"] = push_result

        if push_result.get("success"):
            result["success"] = True
            print(f"  [SUCCESS] {email} -> 9Router!")
            log_event(ocfg["logs_dir"], "SUCCESS", {"email": email})
        else:
            # Fallback: SQLite push
            print(f"  [PUSH] API push failed, trying SQLite...")
            push_sql = pusher.push_via_sqlite(
                access_token=access_token,
                refresh_token=refresh_token,
                email=email,
                display_name=f"{first_name} {last_name}",
                id_token=token_result.get("id_token", ""),
                expires_in=token_result.get("expires_in", 21600),
            )
            result["steps"]["push_sqlite"] = push_sql
            if push_sql.get("success"):
                result["success"] = True
                print(f"  [SUCCESS] {email} -> SQLite!")
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

    print("=" * 60)
    print("  GROKKIDDING -> 9Router")
    print("=" * 60)
    print(f"  Target: {cfg['ninrouter']['base_url']}")
    print(f"  Email: {cfg['email']['domain']}")
    print(f"  Count: {args.count}")
    if args.dry_run:
        print(f"  Mode: DRY RUN")
    print("=" * 60)

    proxy_rotator = ProxyRotator(
        pool=[] if args.no_proxy else cfg["proxy"]["pool"],
        mode=cfg["proxy"].get("mode", "socks5"),
        adb_config=cfg["proxy"].get("adb"),
    )

    ecfg = cfg["email"]
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
        timeout=tcfg.get("timeout", 60), debug=True, headless=args.headless,
    )

    results = []
    for i in range(args.count):
        print(f"\n{'='*60}")
        print(f"  Account {i+1}/{args.count}")
        print(f"{'='*60}")

        try:
            result = run_single_account(cfg, solver, proxy_rotator, email_reader, pusher, args.dry_run)
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

    email_reader.disconnect()
    solver.close()
    return 0 if success > 0 else 1


def cmd_panel(args):
    """Start the web panel server."""
    from .panel import run_panel
    run_panel(host=args.host, port=args.port)


def cmd_launcher(args):
    """Interactive launcher — start panel and open browser."""
    from .panel import run_panel

    port = args.port or 8083
    host = args.host or "127.0.0.1"
    url = f"http://{host}:{port}"

    print()
    print("=" * 52)
    print("  Grokidding v1.0.0")
    print("=" * 52)
    print(f"  Server : {url}")
    print("=" * 52)
    print()
    print("  > Open Web UI")
    print("    Exit")
    print()

    # Start panel in background thread
    server_thread = threading.Thread(
        target=run_panel, kwargs={"host": host, "port": port},
        daemon=True,
    )
    server_thread.start()

    # Wait a moment for server to start
    time.sleep(1.5)

    # Auto-open browser
    webbrowser.open(url)
    print(f"  [OK] Panel running at {url}")

    while True:
        try:
            choice = input("\n  Pilih (1=Open Web UI, 2=Exit): ").strip()
            if choice == "1":
                webbrowser.open(url)
                print("  [OK] Browser dibuka")
            elif choice == "2":
                print("\n  Sampai jumpa! 👋\n")
                break
            else:
                print("  Pilihan tidak valid. Ketik 1 atau 2.")
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Sampai jumpa! 👋\n")
            break

    return 0


def main():
    parser = argparse.ArgumentParser(description="Grokidding -> 9Router")
    subparsers = parser.add_subparsers(dest="command")

    # ── run (default) ──
    run_parser = subparsers.add_parser("run", help="Run farming (default)")
    run_parser.add_argument("--count", type=int, default=1, help="Number of accounts")
    run_parser.add_argument("--config", type=str, help="Config file path")
    run_parser.add_argument("--dry-run", action="store_true", help="Generate credentials only")
    run_parser.add_argument("--no-proxy", action="store_true", help="Skip proxy rotation")
    run_parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")

    # ── panel ──
    panel_parser = subparsers.add_parser("panel", help="Start web control panel")
    panel_parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    panel_parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    panel_parser.add_argument("--config", type=str, help="Config file path")

    # ── launcher (default: no subcommand) ──
    parser.add_argument("--port", type=int, default=None, help="Panel port (default: 8083)")
    parser.add_argument("--host", type=str, default=None, help="Bind host (default: 127.0.0.1)")

    args = parser.parse_args()

    # Route to subcommand
    if args.command == "panel":
        return cmd_panel(args)
    elif args.command == "run":
        return cmd_run(args)
    else:
        # Default: interactive launcher
        return cmd_launcher(args)


if __name__ == "__main__":
    sys.exit(main())
