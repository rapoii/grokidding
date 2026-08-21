# CLAUDE.md — Panduan Cepat Perintah & Pengembangan Grokidding

Dokumen ini menyediakan instruksi singkat mengenai perintah CLI, arsitektur layanan, dan panduan kode untuk Claude Code / Cursor / CLI Autonomous Agents pada proyek **Grokidding** (`grok-farmer`).

---

## 1. Perintah Operasi & Pengembangan Utama

```bash
# Menjalankan farming akun secara paralel (contoh: 10 akun)
python -m grok_farmer run --parallel --count 10

# Uji coba farming tanpa membuat akun sungguhan (Dry Run)
python -m grok_farmer run --dry-run --count 1

# Menjalankan Web Panel Server (Port 8090)
python -m grok_farmer panel --port 8090

# Menjalankan Textual TUI Interactive Dashboard di terminal
python -m grok_farmer tui

# Melakukan refresh seluruh expired OAuth token di 9Router
python -m grok_farmer refresh

# Verifikasi koneksi 9Router AI Gateway
curl -s http://localhost:20128/v1/models

# Audit kualitas UI/UX Anti-AI Slop (Impeccable CLI)
npx impeccable detect grok_farmer/static/index.html
```

---

## 2. Struktur Proyek & File Kunci

```text
grok-farmer/
├── AGENTS.md                  # Panduan autonomous agent & aturan arsitektur
├── CLAUDE.md                  # Panduan cepat CLI & developer workflows
├── DESIGN.md                  # Dokumentasi design system, tipografi, & UI/UX standard
├── config.json                # Konfigurasi proxy, ninrouter DB, dan credentials (masked)
├── data/
│   └── farming_sessions.db    # Histori sesi farming SQLite
├── grok_farmer/               # Python Core Package
│   ├── __main__.py            # CLI entrypoint (subcommands: run, panel, tui, refresh)
│   ├── signup.py              # Otomatisasi browser signup xAI
│   ├── turnstile.py           # Bypass Cloudflare Turnstile CAPTCHA
│   ├── email_generator.py     # Temp mail & IMAP OTP extractor
│   ├── router_push.py         # Push OAuth token ke SQLite 9Router
│   ├── token_refresher.py     # OAuth Token Refresher logic
│   ├── proxy.py               # IP rotation: SOCKS5 pool & ADB Airplane toggle
│   ├── panel.py               # FastAPI backend & WebSocket server
│   └── static/
│       └── index.html         # Ultra-smooth SPA UI (Alpine.js + Tailwind + GSAP)
└── requirements.txt           # Python package dependencies
```

---

## 3. Konvensi Kode & Best Practices

- **Python Environment**: Gunakan Python 3.10+ dengan static typing hints. Selalu gunakan context manager saat membuka koneksi database SQLite atau file.
- **Asynchronous & Threading**:
  - Di `panel.py`, eksekusi farming engine dijalankan pada daemon thread terpisah agar FastAPI event loop dan streaming WebSocket tetap non-blocking.
- **Frontend SPA**:
  - `index.html` ditulis dengan struktur mandiri (*single-file architecture*).
  - State management ditangani secara reaktif oleh Alpine.js (`grokApp()`).
  - Tidak diperkenankan menambah framework berat yang memerlukan Node build step di sisi client (Next.js/React hydration bundler) untuk menjaga kecepatan akses di low-end hardware.
- **Anti-AI Slop**:
  - Sebelum menandai tugas UI selesai, jalankan `npx impeccable detect grok_farmer/static/index.html` untuk menjamin 0 warning.
