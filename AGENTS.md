# AGENTS.md — Petunjuk & Konvensi Autonomous AI Agent untuk Grokidding

Dokumen ini ditujukan untuk agen AI (seperti Hermes, Claude Code, Cursor, Codex, dll.) yang bekerja di dalam codebase **Grokidding** (`grok-farmer`).

---

## 1. Ikhtisar Proyek & Arsitektur
- **Nama Aplikasi**: Grokidding (Project Grok-Farmer)
- **Tujuan**: Platform Otomatisasi High-Performance Farming Akun xAI/Grok, Bypass Cloudflare Turnstile, OTP Email Extraction, OAuth Device Code Flow, dan Sinkronisasi Multi-Account Pool ke **9Router Local AI Gateway**.
- **Filosofi UI/UX**: *Pure Light Mode*, Clean, Minimalist, Precision-Engineered, Anti-AI Slop, Multi-Device Responsive (Desktop & Mobile 390x844 / 403x881), dan **Ultra-Smooth Low-End Device Friendly (60fps)**.
- **Komponen Utama**:
  1. **Core Farming Engine (`grok_farmer/`)**:
     - `signup.py`: Puppeteer/Playwright headless browser automation untuk signup di `accounts.x.ai` dan consent OAuth.
     - `turnstile.py`: Modul deteksi & bypass Cloudflare Turnstile token.
     - `email_generator.py`: Generator temporary email & IMAP reader untuk menangkap kode verifikasi OTP 6-digit.
     - `router_push.py`: Pustaka sinkronisasi credentials (`accessToken`, `refreshToken`, `expiresAt`) ke database SQLite 9Router (`data.sqlite`).
     - `token_refresher.py` & `cron_token_refresher.py`: Background job untuk auto-refresh expired OAuth token.
     - `proxy.py`: Manajemen IP rotation (SOCKS5/HTTP Proxy Pool & ADB Android Airplane Mode toggle).
     - `session_stats.py`: Pencatatan metrik performa sesi farming ke SQLite (`data/farming_sessions.db`).
  2. **FastAPI Web Panel & Live UI (`grok_farmer/panel.py` & `grok_farmer/static/index.html`)**:
     - Backend: FastAPI + WebSocket streaming log real-time (`/ws`).
     - Frontend: Single-File SPA berbasis **Alpine.js 3 + Tailwind CSS CDN + GSAP 3 + Lucide Icons**.
     - Zero Webpack/Next.js client-side bundle overhead — instan dimuat dan sangat ringan di low-end hardware.
  3. **Textual TUI Dashboard (`grok_farmer/tui.py`)**:
     - Terminal User Interface interaktif berbasis Textual untuk monitoring langsung dari CLI.

---

## 2. Standar Kualitas Desain & Anti-AI Slop (Mandatory)
Seluruh perubahan antarmuka pengguna pada Web Panel **wajib mematuhi**:
1. **Taste & Editorial Minimalism**:
   - Palette warna: Background Warm Bone (`#FBFBFA`), Surface Murni (`#FFFFFF`), Border tipis halus (`#EAEAEA`), Aksen Terakota (`#D97757`).
   - Font: Sans-serif modern (**Geist Sans / SF Pro**) dan Monospace untuk data teknis (**JetBrains Mono**).
   - Hindari drop shadow tebal (`shadow-lg`/`shadow-xl`), gunakan `shadow-subtle` / border flat.
   - Hindari warna neon, gradient norak, dan font generik membosankan.
2. **Low-End Hardware Friendly (60fps)**:
   - Wajib memanfaatkan CSS Hardware Compositing: `transform: translateZ(0)` dan `will-change: transform, opacity`.
   - Gunakan transisi micro-animation ringan melalui GSAP 3 dengan fallback `prefers-reduced-motion`.
3. **Audit Bebas AI Slop**:
   - Setiap perubahan UI pada `index.html` wajib divalidasi menggunakan CLI Impeccable:
     ```bash
     npx impeccable detect grok_farmer/static/index.html
     ```
   - Hasil audit harus menghasilkan **0 anti-patterns (Clean)**. Tidak boleh ada nested cards berlebihan, fake pulsing dots, atau teks terpotong.
4. **Mobile Responsive Standard (390x844)**:
   - Tabel koneksi/akun harus otomatis bertransformasi menjadi **Card List View** vertikal yang ramah sentuhan (touch-friendly) pada viewport `< sm` (mobile).

---

## 3. Aturan Keamanan, Kredensial & Lingkungan
- **Masking Sensitif**: Kredensial, password ninrouter, IMAP password, dan bearer token dilarang keras dicetak/ditampilkan secara mentah (*plaintext*). Selalu gunakan format `***` atau `[REDACTED]`.
- **Database 9Router**: Terletak pada `C:/Users/<user>/AppData/Roaming/9Router/db/data.sqlite`. Akses mutasi tabel `providerConnections` hanya untuk provider `grok-cli`.
- **Manajemen Port & Browser Process**:
  - Web Panel berjalan di port default `8090`.
  - Jika terjadi tabrakan port debugging Chromium pada proses paralel, bersihkan orphan process dengan perintah aman:
    ```bash
    taskkill /F /IM chrome.exe /T
    ```

---

## 4. Alur Kerja Sebelum Selesai (Definition of Done)
1. **Syntax & Import Check**:
   ```bash
   python -m py_compile grok_farmer/panel.py
   python -m grok_farmer run --dry-run --count 1
   ```
2. **Audit Impeccable**:
   ```bash
   npx impeccable detect grok_farmer/static/index.html
   ```
3. **Visual Verification**:
   - Uji respon antarmuka dan snapshot via Playwright pada resolusi Desktop (1280x800) dan Mobile (390x844).
4. **Git Hygiene**:
   - Pastikan working tree bersih dan commit pesan mengikuti konvensi Semantic Commit (`feat:`, `fix:`, `refactor:`).
