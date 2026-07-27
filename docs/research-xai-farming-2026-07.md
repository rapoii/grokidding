# xAI/Grok Account Farming Research — July 2026

## Working Repos (Ranked by Relevance)

| Repo | Stars | Language | Approach | Status |
|------|-------|----------|----------|--------|
| Charles-0509/Grok-Register | 480 | Go | CLI: register → OAuth → CPA JSON | Active Jul 27 |
| dongguatanglinux/grok-build-auth | 290 | Python | Pure HTTP gRPC-Web, no browser | Active Jul 10 |
| Git-creat7/grokRegister-cpa | 280 | Python | GUI/CLI, protocol HTTP + Device Flow | Active |
| ReinerBRO/grok-register | 385 | Python | DrissionPage + turnstilePatch | Mar 2026 |
| dzDev37/Auto-sign-up-grok-dezz | 48 | Python | Playwright + 9Router direct push | Active Jul 27 |
| AaronL725/grok-register | - | Python | DrissionPage, 4 email providers | Active |
| kaidenzeto/grok-register | - | Python | gRPC-Web + CloakBrowser | Active |
| 0xKii/grok-account-farm | 1 | Python | Bulk registration + grok2api | Jul 15 |

## xAI Signup Flow (July 2026)

1. Navigate to accounts.x.ai/sign-up
2. Accept cookies dialog
3. Click "Sign up with email"
4. Fill email → submit
5. xAI sends OTP via gRPC-Web (format: XXX-XXX, 6 chars)
6. Fill OTP → auto-submits on 6 chars
7. Fill profile (givenName, familyName, password)
8. Turnstile CAPTCHA (invisible with extension, visible without)
9. Click "Complete sign up"
10. Redirect to grok.com (if success)
11. OAuth: authorization code flow or device code flow
12. Token exchange → push to 9Router/grok2api/CPA

## Critical Blockers (July 2026)

### 1. Free Tier 402 Block
- xAI returns `personal-team-blocked:spending-limit` (HTTP 402)
- Affects ALL new free accounts
- `/v1/models` returns 200 (false positive), `/v1/responses` returns 402
- May be reversible (xAI frequently flip-flops)

### 2. Email Domain Flagging
- varevastudio.tech FLAGGED by xAI
- generator.email domains also flagged
- Microsoft email accounts reportedly survive longer
- Self-hosted CF Workers/D1 alias mail is best approach
- Tempmail.lol API also works

### 3. Registration "Access Denied"
- Reported Jul 23-25 on linux.do
- xAI tightening registration for automated accounts
- Possible new anti-bot measures

### 4. Device Flow Rate Limiting
- `slow_down` / `429` errors on concurrent registrations
- Need serialization + random delays

## What's Working NOW

1. ✅ Account registration still works (tightening)
2. ✅ SSO extraction works
3. ✅ OAuth PKCE authorization code flow works
4. ⚠️ Device Flow hitting rate limits under concurrency
5. ✅ cli-chat-proxy.grok.com with X-XAI-Token-Auth headers works

## Approaches Used by Other Tools

| Approach | Status | Notes |
|----------|--------|-------|
| Pure HTTP/gRPC-Web (dongguatanglinux) | ✅ Working | curl_cffi fingerprint, YesCaptcha |
| DrissionPage browser (ReinerBRO, AaronL725) | ✅ Working | turnstilePatch extension |
| Playwright + channel='chrome' (dzDev37) | ✅ Working | Real Chrome, turnstilePatch |
| CloakBrowser (kaidenzeto) | ✅ Working | Binary-level stealth Chromium |
| Protocol + Device Flow (Git-creat7) | ⚠️ Partial | Rate limiting issues |

## dzDev37/Auto-sign-up-grok-dezz Patterns

Key techniques from their single-file implementation:

1. **OTP input**: `page.locator('input[name=code]').fill(code)` — simple and reliable
2. **Turnstile**: Just wait for auto-solve (extension patches MouseEvent.screenX/screenY)
3. **Error detection**: Check page body text for 'too weak', 'already', 'invalid'
4. **SSO cookie capture**: Save ALL cookies for later device code approval
5. **9Router push**: Device code flow, inject SSO cookies into browser context

## Recommendations for Grokidding

1. **Email**: Switch to self-hosted CF Workers/D1 or tempmail.lol API
2. **OTP input**: Use `input[name=code]` selector (verified working)
3. **Turnstile**: Wait for auto-solve, don't click manually
4. **Error handling**: Detect common errors from page text
5. **Throttle**: Add delays between accounts (not parallel)
6. **Consider CPA format**: Most repos now export CPA-compatible auth JSON

## CPA Auth Export Format
```json
{
  "type": "xai",
  "auth_kind": "oauth",
  "access_token": "...",
  "refresh_token": "...",
  "base_url": "https://cli-chat-proxy.grok.com/v1",
  "headers": {
    "X-XAI-Token-Auth": "xai-grok-cli",
    "x-grok-client-version": "0.2.99",
    "x-grok-client-identifier": "grok-shell"
  }
}
```
