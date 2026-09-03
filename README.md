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
2. Baca OTP dari **generator.email** (tanpa IMAP)
3. Ambil OAuth token via device code flow
4. Push token ke 9Router sebagai provider connection

---

## ✨ Fitur

| Fitur | Keterangan |
|-------|------------|
| ✅ Registrasi xAI | Browser automation + Cloudflare Turnstile auto-solve |
| ✅ generator.email OTP | Baca kode OTP otomatis via browser scraping (tanpa IMAP) |
| ✅ OAuth → 9Router | Device code flow + API exchange (SQLite fallback) |
| ✅ Multi-Protocol Proxy | SOCKS5, SOCKS4, HTTP, HTTPS + ADB airplane mode |
| ✅ TUI Dashboard | Terminal UI (Textual) dengan live logs, stats, settings |
| ✅ Quota Tracking | Pantau penggunaan 500 queries/account/24h |
| ✅ Account Renewal | Hapus expired + buat pengganti otomatis |
| ✅ Stop Farming | Hentikan proses farming kapan saja |

---

## 🔄 Alur Kerja

```
Email (generator.email) → Signup xAI → OTP via browser → Verify → Profile → Turnstile
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

> 💡 Untuk TUI: `pip install textual platformdirs`

### 2. Buat Config

```bash
cp config.example.json config.json
# Edit config.json dengan data kamu
```

### 3. Siapkan 9Router

```bash
npm install -g 9router
9router
```

### 4. Jalankan!

```bash
# TUI Dashboard (default)
python -m grok_farmer

# CLI farming
python -m grok_farmer run --count 3

# Legacy web panel
python -m grok_farmer panel --port 8083
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
    "mode": "generator"
  },
  "proxy": {
    "mode": "socks5",
    "pool": [
      "socks5://user:pass@proxy1.com:1080",
      "socks5://user:pass@proxy2.com:1080"
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
  }
}
```

| Field | Keterangan |
|-------|------------|
| `ninrouter.base_url` | URL 9Router (default: `http://localhost:20128`) |
| `ninrouter.password` | Password login 9Router |
| `ninrouter.db_path` | Path SQLite 9Router (opsional, otomatis deteksi `%APPDATA%/9Router/db/data.sqlite`) |
| `email.mode` | `"generator"` (pakai generator.email) |
| `proxy.mode` | Mode rotasi IP: `socks5` atau `off` |
| `proxy.pool` | Daftar URL proxy (rotasi tiap akun) |

---

## 🖥️ TUI Dashboard

Jalankan `python -m grok_farmer` untuk membuka TUI:

| Tab | Fungsi |
|-----|--------|
| 📊 Dashboard | Start/Stop farming, live logs, stats |
| 📋 Accounts | Daftar akun + status (active/error/exhausted) |
| 📊 Quota | Cek sisa queries per akun |
| 🔄 Renew | Hapus expired + buat pengganti |
| 📝 Logs | Log lengkap |
| ⚙️ Settings | Edit proxy, 9Router config |

**Keyboard shortcuts:**
- `f` — Start farming
- `s` — Stop farming
- `r` — Refresh data
- `q` — Quit

---

## 🌐 Proxy

| Tipe | Format |
|------|--------|
| SOCKS5 + Auth | `socks5://user:pass@host:port` |
| SOCKS5 No Auth | `socks5://host:port` |
| SOCKS4 | `socks4://host:port` |
| HTTP | `http://user:pass@host:port` |
| HTTPS | `https://user:pass@host:port` |

Minimal 3-5 proxy untuk hasil terbaik. Atur via TUI Settings.

**ADB IP Rotation (gratis, tanpa proxy):**
1. Aktifkan USB Debugging di HP Android
2. Cek serial: `adb devices`
3. Set `proxy.adb.enabled: true` + `device_serial` di config

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Config not found | `cp config.example.json config.json` lalu edit |
| OTP timeout | generator.email mungkin lambat, naikkan timeout |
| Button not found | Update Chrome + DrissionPage |
| Push failed | Cek 9Router running, cek `db_path` benar |
| Turnstile gagal | Pastikan `turnstile_patch/` ada |
| Textual error | `pip install textual platformdirs` |

---

## 📁 Arsitektur

```
grokidding/
├── grok_farmer/
│   ├── __main__.py        # CLI entry point
│   ├── tui.py             # Textual TUI dashboard
│   ├── email_generator.py # generator.email OTP reader
│   ├── turnstile.py       # Turnstile solver + browser
│   ├── signup.py          # xAI registration (gRPC-Web)
│   ├── oauth.py           # Device code OAuth flow
│   ├── router_push.py     # 9Router push (API + SQLite)
│   ├── email_reader.py    # [Legacy] IMAP OTP reader
│   ├── proxy.py           # Multi-protocol proxy rotation
│   ├── grpc_web.py        # gRPC-Web protobuf codec
│   ├── config.py          # Config loader
│   └── utils.py           # Helpers
├── turnstile_patch/       # Chrome extension
├── config.json            # ⚠️ Gitignored
├── config.example.json    # Contoh config
├── requirements.txt
└── README.md
```

---

## ⚙️ Teknologi

| Komponen | Teknologi |
|----------|-----------|
| Browser | DrissionPage (Chrome DevTools Protocol) |
| HTTP Client | curl_cffi (TLS fingerprint: Chrome 131) |
| Signup Protocol | gRPC-Web + Protobuf |
| Email | generator.email (browser scraping) |
| OAuth | xAI Device Code Flow |
| TUI | Textual (Python) |
| Proxy | SOCKS5/4, HTTP, HTTPS + local TCP forwarder |

---

## 🙏 Credits

- [dongguatanglinux/grok-build-auth](https://github.com/dongguatanglinux/grok-build-auth) — gRPC-Web signup protocol
- [ReinerBRO/grok-register](https://github.com/ReinerBRO/grok-register) — Turnstile Chrome extension patch
- [decolua/9router](https://github.com/decolua/9router) — AI provider router

---

## 📄 License

[MIT License](LICENSE) — Copyright (c) 2026 [Rafi Permana](https://github.com/rapoii)

**Dibuat oleh [Rafi Permana](https://github.com/rapoii)**
