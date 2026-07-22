<div align="center">

<img src="docs/banner.png" alt="Grokidding Banner" width="100%">

# 🤖 Grokidding

### Automated Grok/xAI Account Farmer → 9Router

![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Stars](https://img.shields.io/github/stars/rapoii/grokidding?style=flat)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

> Buat akun Grok/xAI secara otomatis, ambil OAuth token, dan push ke 9Router sebagai provider connection.

</div>

---

## 🤖 Apa itu Grokidding?

**Grokidding** (paket Python: `grok_farmer`) otomatisasi pembuatan akun Grok/xAI:
1. Registrasi akun via browser (DrissionPage)
2. Ambil OAuth token via device code flow
3. Push token ke 9Router sebagai provider connection

---

## ✨ Fitur

| Fitur | Keterangan |
|-------|------------|
| ✅ Registrasi xAI | Browser automation + Cloudflare Turnstile auto-solve |
| ✅ IMAP OTP Reader | Baca kode OTP otomatis dari email catch-all (Migadu) |
| ✅ OAuth → 9Router | Device code flow + API exchange (SQLite fallback) |
| ✅ Multi-Protocol Proxy | SOCKS5, SOCKS4, HTTP, HTTPS + ADB airplane mode |
| ✅ Web Control Panel | Dark theme dashboard, real-time WebSocket, live logs |
| ✅ Quota Tracking | Pantau penggunaan 500 queries/account/24h |
| ✅ Account Renewal | Hapus expired + buat pengganti otomatis (satu klik) |
| ✅ Stop Farming | Hentikan proses farming kapan saja dari dashboard |
| ✅ Grok Proxy Endpoint | Panel bisa jadi proxy `/v1/responses` untuk Grok CLI |

---

## 🔄 Alur Kerja

```
Email → Signup xAI → OTP via IMAP → Verify → Profile → Turnstile
  → Device Code → Approve → Token → Push ke 9Router → ✅
```

---

## 📦 Instalasi

### 1. Clone & Install

```bash
git clone https://github.com/rapoii/grokidding.git
cd grokidding
pip install -r requirements.txt
```

> 💡 Untuk web panel: `pip install fastapi uvicorn[standard] requests pydantic`

### 2. Buat Config

```bash
cp config.example.json config.json
# Edit config.json dengan data kamu (lihat bagian Konfigurasi)
```

### 3. Siapkan Email Catch-All

Kamu butuh domain dengan fitur **catch-all** (semua `*@domain.com` masuk ke satu inbox).

Contoh menggunakan [Migadu](https://migadu.com) (ada paket gratis):
1. Daftar → tambah domain → aktifkan **Catch-All**
2. Catat: IMAP host, port, email, password

### 4. Siapkan 9Router

```bash
npm install -g 9router
9router
```

### 5. Jalankan!

```bash
# Langsung buka Web UI (default)
python -m grok_farmer

# Atau dry run dulu untuk testing
python -m grok_farmer run --dry-run --count 1
```

---

## ⚙️ Konfigurasi

Edit `config.json`:

```json
{
  "ninrouter": {
    "base_url": "http://localhost:3000",
    "password": "password-kamu",
    "db_path": "C:/Users/Kamu/AppData/Roaming/9router/db/data.sqlite"
  },
  "email": {
    "imap_host": "imap.migadu.com",
    "imap_port": 993,
    "email": "otp@domainmu.com",
    "password": "password-imap-kamu",
    "domain": "domainmu.com"
  },
  "proxy": {
    "mode": "socks5",
    "pool": [
      "socks5://user:pass@proxy1.com:1080",
      "http://user:pass@proxy2.com:8080"
    ],
    "adb": {
      "enabled": false,
      "device_serial": "DEVICE_SERIAL",
      "adb_path": "adb"
    }
  },
  "turnstile": {
    "extension_path": "turnstile_patch/",
    "max_retries": 15,
    "timeout": 60
  },
  "signup": {
    "password_length": 16,
    "max_retries": 3
  },
  "output": {
    "accounts_dir": "data/accounts/",
    "logs_dir": "data/logs/"
  }
}
```

| Field | Keterangan |
|-------|------------|
| `ninrouter.base_url` | URL 9Router (`http://localhost:3000` atau tunnel URL) |
| `ninrouter.password` | Password login 9Router |
| `ninrouter.db_path` | Path absolut ke SQLite 9Router (untuk fallback push) |
| `email.imap_host` | Server IMAP (Migadu: `imap.migadu.com`) |
| `email.domain` | Domain untuk generate email random |
| `proxy.mode` | Mode rotasi IP: `socks5` atau `off` |
| `proxy.pool` | Daftar URL proxy (rotasi tiap akun) |
| `proxy.adb.enabled` | `true` untuk rotasi IP via airplane mode |

> 💡 Semua setting bisa diedit langsung dari Web UI (tab **⚙️ Settings**). Tidak perlu edit file manual.

---

## 🚀 Tutorial

<p align="center">
  <img src="docs/screenshot-dashboard.png" alt="Grokidding Dashboard" width="90%">
</p>

### 1. Jalankan Grokidding

```bash
python -m grok_farmer
```

Terminal akan menampilkan menu interaktif. Tekan **Enter** pada opsi **"Open Web UI"** — browser otomatis terbuka ke dashboard.

### 2. Mulai Farming

Di dashboard Web UI:
1. Isi **jumlah akun** yang ingin dibuat
2. Atur **proxy mode** di tab ⚙️ Settings (socks5 / off)
3. Klik **"Start Farming"**
4. Progress berjalan **real-time** via WebSocket + Live Logs
5. Klik **"Stop"** kapan saja untuk menghentikan proses

<p align="center">
  <img src="docs/screenshot-full.png" alt="Grokidding Full Dashboard" width="90%">
</p>

### 3. Pantau Akun & Quota

- **📊 Quota** → cek sisa 500 queries per akun (auto-refresh setelah farming selesai)
- **📋 Accounts** → lihat status semua akun (active/exhausted/error)

### 4. Renew Akun Expired

1. Tab **🔄 Renew** → klik **"Renew"**
2. Grokidding otomatis: hapus expired dari xAI + 9Router → buat baru → push

### 5. Edit Config dari Panel

Tab **⚙️ Settings** → edit konfigurasi langsung dari browser:
- **IP Rotation** — pilih mode: Off / Proxy SOCKS5 / ADB Airplane Mode
- **Email** — IMAP host, port, email address, domain
- **9Router** — base URL, password, database path

### 6. Semua Tab

| Tab | Fungsi |
|-----|--------|
| 📊 Dashboard | Statistik akun, grafik quota, Start/Stop farming |
| 📋 Accounts | Daftar akun, status, hapus individual |
| 📊 Quota | Cek sisa 500 queries/account/24h (cached 30s) |
| 🔄 Renew | Hapus expired + buat pengganti |
| 📝 Logs | Live Logs real-time via WebSocket |
| ⚙️ Settings | Edit config, test proxy/ADB, simpan |

---

## 🌐 Proxy

| Tipe | Format |
|------|--------|
| SOCKS5 + Auth | `socks5://user:pass@host:port` |
| SOCKS5 No Auth | `socks5://host:port` |
| SOCKS4 | `socks4://host:port` |
| HTTP | `http://user:pass@host:port` |
| HTTPS | `https://user:pass@host:port` |

Edit `config.json` → tambah ke `proxy.pool`, atau tambah via tab **⚙️ Settings** di Web UI. Minimal 3-5 proxy untuk hasil terbaik.

**ADB IP Rotation (gratis, tanpa proxy):**
1. Aktifkan USB Debugging di HP Android
2. Cek serial: `adb devices`
3. Set `proxy.adb.enabled: true` + `device_serial` di config

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Config not found | `cp config.example.json config.json` lalu edit |
| OTP timeout | Cek catch-all domain aktif, cek folder spam |
| Button not found | Update Chrome + DrissionPage, coba mode proxy Off |
| Push failed | Cek 9Router running, cek `db_path` benar |
| Turnstile gagal | Pastikan `turnstile_patch/` ada, naikkan `max_retries` |
| IP diblokir | Aktifkan proxy atau ADB rotation, kurangi batch |
| Proxy error | Cek koneksi proxy via tab Settings → Test Proxy |

---

## 📁 Arsitektur

```
grokidding/
├── grok_farmer/           # Python package
│   ├── __main__.py        # CLI entry point + interactive launcher
│   ├── panel.py           # FastAPI web panel + quota cache + WebSocket
│   ├── static/index.html  # Dashboard frontend (dark theme)
│   ├── turnstile.py       # Turnstile solver + browser launcher
│   ├── signup.py          # xAI registration (gRPC-Web)
│   ├── oauth.py           # Device code OAuth flow
│   ├── router_push.py     # 9Router push (API + SQLite fallback)
│   ├── email_reader.py    # IMAP OTP reader
│   ├── proxy.py           # Multi-protocol proxy rotation
│   ├── grpc_web.py        # gRPC-Web protobuf codec
│   ├── config.py          # Config loader
│   └── utils.py           # Helpers (generate, save, log)
├── turnstile_patch/       # Chrome extension (Turnstile bypass)
├── config.json            # ⚠️ Gitignored — credentials kamu
├── config.example.json    # Contoh config (placeholder)
├── requirements.txt       # Dependencies
└── README.md
```

---

## ⚙️ Teknologi

| Komponen | Teknologi |
|----------|-----------|
| Browser | DrissionPage (Chrome DevTools Protocol) |
| HTTP Client | curl_cffi (TLS fingerprint: Chrome 131) |
| Signup Protocol | gRPC-Web + Protobuf (Connect-ES) |
| Email | IMAP (Migadu catch-all) |
| OAuth | xAI Device Code Flow |
| Web Panel | FastAPI + Uvicorn + WebSocket |
| Proxy | SOCKS5/4, HTTP, HTTPS + local TCP forwarder |

---

## 🙏 Credits

- [dongguatanglinux/grok-build-auth](https://github.com/dongguatanglinux/grok-build-auth) — gRPC-Web signup protocol
- [ReinerBRO/grok-register](https://github.com/ReinerBRO/grok-register) — Turnstile Chrome extension patch
- [decolua/9router](https://github.com/decolua/9router) — AI provider router

---

## 📄 License

[MIT License](LICENSE) — Copyright (c) 2026 [Rafi Permana](https://github.com/rapoii)

**Dibuat dengan ❤️ oleh [Rafi Permana](https://github.com/rapoii)**
