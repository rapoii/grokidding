"""End-to-end test: generator.email + xAI signup + OTP pipeline.

Run with Python 3.14 (NOT hermes venv):
  PYTHONPATH="" python test_pipeline.py

Tests:
1. Launch DrissionPage browser
2. Generate email from generator.email
3. Navigate to x.ai signup page
4. Fill email and submit
5. Wait for OTP via GeneratorEmailReader
6. Type OTP into browser
"""
import sys
import time

def main():
    print("=" * 60)
    print("  GROKIDDING END-TO-END PIPELINE TEST")
    print("=" * 60)

    # Step 0: Import all modules
    print("\n[0/6] Importing modules...")
    try:
        from grok_farmer.email_generator import generate_email_from_browser, GeneratorEmailReader
        from grok_farmer.signup import SignupClient
        from grok_farmer.oauth import OAuthClient
        from grok_farmer.turnstile import TurnstileSolver
        from grok_farmer.router_push import RouterPusher
        print("  OK: All imports successful")
    except ImportError as e:
        print(f"  FAIL: Import error: {e}")
        sys.exit(1)

    # Step 1: Launch browser
    print("\n[1/6] Launching browser...")
    from DrissionPage import ChromiumOptions, ChromiumPage
    co = ChromiumOptions()
    co.set_argument("--disable-extensions")
    co.set_argument("--no-first-run")
    co.auto_port()
    try:
        page = ChromiumPage(co)
        print(f"  OK: Browser launched, title={page.title}")
    except Exception as e:
        print(f"  FAIL: Browser launch failed: {e}")
        sys.exit(1)

    try:
        # Step 2: Generate email from generator.email
        print("\n[2/6] Generating email from generator.email...")
        email = generate_email_from_browser(page, max_attempts=5)
        if not email:
            print("  FAIL: Could not generate email")
            sys.exit(1)
        user_part, domain_part = email.split("@", 1)
        print(f"  OK: Generated email: {email}")
        print(f"      User: {user_part}, Domain: {domain_part}")

        # Step 3: Create GeneratorEmailReader
        print("\n[3/6] Creating GeneratorEmailReader...")
        email_reader = GeneratorEmailReader(page)
        print(f"  OK: GeneratorEmailReader created")

        # Step 4: Navigate to x.ai signup and fill email
        print("\n[4/6] Navigating to x.ai signup...")
        page.get("https://accounts.x.ai/sign-up?redirect=grok-com&return_to=%2F")
        time.sleep(4)
        h1 = page.ele("tag:h1", timeout=3)
        print(f"  Page h1: {h1.text if h1 else 'N/A'}")

        # Accept cookies if present
        try:
            cookie_btn = page.ele("text:Accept", timeout=2)
            if cookie_btn:
                cookie_btn.click()
                print("  Accepted cookies")
                time.sleep(1)
        except Exception:
            pass

        # Click "Sign up with email"
        print("  Clicking 'Sign up with email'...")
        buttons = page.eles("tag:button")
        for btn in buttons:
            if "sign up with email" in (btn.text or "").lower():
                btn.click()
                print(f"  OK: Clicked '{btn.text}'")
                break
        else:
            # Try JS click
            page.run_js("""
                for (const b of document.querySelectorAll('button')) {
                    if (b.textContent.toLowerCase().includes('sign up with email')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            """)
            print("  Used JS fallback for 'Sign up with email'")
        time.sleep(3)

        # Fill email
        print(f"  Filling email: {email}")
        email_input = page.ele("tag:input@type=email", timeout=3)
        if not email_input:
            email_input = page.ele("tag:input", timeout=3)
        if email_input:
            email_input.click()
            email_input.input(email)
            time.sleep(1)
            print(f"  OK: Email filled")
        else:
            print("  FAIL: Could not find email input")
            sys.exit(1)

        # Click "Sign up" button
        print("  Clicking 'Sign up' button...")
        signup_btns = page.eles("tag:button")
        for btn in signup_btns:
            txt = (btn.text or "").strip().lower()
            if txt == "sign up":
                btn.click()
                print(f"  OK: Clicked 'Sign up'")
                break
        else:
            # Fallback: form submit
            page.run_js("""
                const input = document.querySelector('input[type=email]');
                if (input && input.form) {
                    input.form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
                }
            """)
            print("  Used form submit fallback")
        time.sleep(5)

        h1_now = page.ele("tag:h1", timeout=3)
        print(f"  Page h1 after submit: {h1_now.text if h1_now else 'N/A'}")

        # Step 5: Wait for OTP
        print(f"\n[5/6] Waiting for OTP for {email} (max 180s, poll every 5s)...")
        otp = email_reader.wait_for_otp(
            target_email=email,
            timeout=180,
            poll_interval=5,
        )
        if not otp:
            print("  FAIL: OTP timeout (180s)")
            sys.exit(1)
        otp_clean = otp.replace("-", "")
        print(f"  OK: OTP received: {otp} -> cleaned: {otp_clean}")

        # Step 6: Type OTP
        print(f"\n[6/6] Typing OTP {otp_clean} into browser...")
        otp_input = page.ele("tag:input@name=code", timeout=3)
        if not otp_input:
            otp_input = page.ele("@data-input-otp=true", timeout=2)
        if not otp_input:
            otp_input = page.ele("tag:input", timeout=3)

        if otp_input:
            otp_input.click()
            time.sleep(0.3)
            for ch in otp_clean:
                otp_input.input(ch)
                time.sleep(0.15)
            time.sleep(2)
            otp_input.input("\n")
            time.sleep(3)
            h1_after = page.ele("tag:h1", timeout=3)
            print(f"  OK: OTP typed, page h1: {h1_after.text if h1_after else 'N/A'}")
        else:
            print("  WARN: Could not find OTP input field (may have auto-submitted)")

        # Summary
        print("\n" + "=" * 60)
        print("  TEST COMPLETE")
        print("=" * 60)
        print(f"  Email: {email}")
        print(f"  OTP: {otp_clean}")
        print(f"  Status: {'SUCCESS' if otp_clean else 'PARTIAL'}")

    finally:
        # Cleanup
        print("\n  Closing browser...")
        try:
            page.quit()
        except Exception:
            pass
        print("  Done.")


if __name__ == "__main__":
    main()
