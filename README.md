<div align="center">

# 🤖 Grokidding

### Automated Grok/xAI Account Farmer → 9Router

![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Stars](https://img.shields.io/github/stars/rapoii/grokidding?style=flat)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

> Buat akun Grok/xAI secara otomatis, ambil OAuth token, dan push ke 9Router sebagai provider connection.
> Satu perintah, ratusan akun. 🚀

</div>

---

## 📋 Daftar Isi

- [Apa itu Grokidding?](#-apa-itu-grokidding)
- [Fitur](#-fitur)
- [Alur Kerja](#-alur-kerja)
- [Persyaratan](#-persyaratan)
- [Instalasi](#-instalasi)
- [Konfigurasi](#️-konfigurasi)
- [Tutorial Penggunaan](#-tutorial-penggunaan)
- [Mode Operasi](#️-mode-operasi)
- [Proxy](#-proxy)
- [Troubleshooting](#-troubleshooting)
- [Arsitektur](#-arsitektur)
- [Teknologi](#️-teknologi)
- [Credits](#-credits)
- [License](#-license)

---

## 🤖 Apa itu Grokidding?

**Grokidding** (paket Python: `grok_farmer`) adalah tool otomatisasi yang bisa membuat akun Grok/xAI dalam jumlah banyak sekaligus. Tool ini akan:

1. **Mendaftar** akun baru di xAI secara otomatis menggunakan browser (DrissionPage)
2. **Mengambil** OAuth token dari akun yang baru dibuat
3. **Mengirim** token tersebut ke **9Router** sebagai provider connection

Hasilnya? Kamu punya banyak akun Grok yang siap dipakai lewat 9Router — tanpa klik-klik manual satu per satu.

> **Analogi sederhana:** Bayangkan kamu punya pabrik kecil yang setiap menit bisa bikin akun Grok baru, verifikasi email-nya otomatis, dan langsung menyambungkannya ke server AI kamu. Itulah Grokidding.

### Kenapa bernama "Grokidding"?
Gabungan dari **Grok** + **Kidding** (bercanda) — karena membuat akun Grok jadi semudah bercanda. 😄

---

## ✨ Fitur

### 🔥 Fitur Utama

| # | Fitur | Keterangan |
|---|-------|------------|
| ✅ | **Registrasi xAI Otomatis** | Browser automation via DrissionPage — buka, isi, submit |
| ✅ | **Cloudflare Turnstile Auto-Solve** | Chrome extension patch untuk bypass CAPTCHA |
| ✅ | **IMAP OTP Reader** | Baca kode OTP dari email Migadu (catch-all) secara otomatis |
| ✅ | **OAuth Device Code Flow** | Ambil access_token + refresh_token untuk Grok CLI |
| ✅ | **9Router Push** | Kirim token ke 9Router via API exchange (SQLite fallback) |
| ✅ | **Multi-Protocol Proxy** | Dukungan SOCKS5, SOCKS4, HTTP, HTTPS |
| ✅ | **ADB IP Rotation** | Ganti IP via airplane mode di HP Android |
| ✅ | **Web Control Panel** | Dashboard dark theme dengan real-time WebSocket |
| ✅ | **Quota Tracking** | Pantau penggunaan 500 queries/account/24h |
| ✅ | **Account Renewal** | Hapus akun expired + buat pengganti otomatis |
| ✅ | **Headless Mode** | Jalan di background tanpa jendela browser |
| ✅ | **Grok Proxy Endpoint** | Panel bisa jadi proxy `/v1/responses` untuk Grok CLI |

### 🌟 Feature Highlights

- ⚡ **Cepat** — satu akun baru dalam ~2 menit
- 🔄 **Rotasi otomatis** — proxy ganti tiap akun, IP selalu fresh
- 📊 **Real-time dashboard** — lihat progress langsung dari browser
- 🛡️ **Anti-deteksi** — TLS fingerprint Chrome 131 + Turnstile patch
- 🔁 **Self-healing** — retry otomatis di setiap step, reconnect IMAP
- 💾 **Backup akun** — semua akun tersimpan di `data/accounts/` sebagai JSON
- 📝 **Logging lengkap** — setiap step tercatat di `data/logs/`

---

## 🔄 Alur Kerja

Setiap akun melewati **10 langkah** berikut:

```
┌─────────────────────────────────────────────────────────────┐
│                    GROKIDDING PIPELINE                       │
│                    (per 1 akun)                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    Email random@domain.com dibuat             │
│  │ 1. EMAIL │──→ Menggunakan catch-all domain Migadu        │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    Browser buka accounts.x.ai/sign-up         │
│  │ 2. SIGNUP│──→ Klik "Sign up with email", isi form        │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    Polling INBOX di imap.migadu.com           │
│  │ 3. OTP   │──→ Cari email dari x.ai, ekstrak kode OTP    │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    Ketik OTP 6 karakter (auto-submit)         │
│  │ 4. VERIFY│──→ Tunggu redirect ke halaman profil          │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    Isi nama + password random                 │
│  │ 5. PROFIL│──→ Klik "Complete sign up"                    │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    Jika Cloudflare muncul, solve Turnstile    │
│  │ 6.TURNSTL│──→ Chrome extension patch + shadow DOM        │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    POST ke auth.x.ai/oauth2/device/code      │
│  │ 7. DEVICE│──→ Dapatkan user_code + device_code           │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    Buka halaman approval di browser            │
│  │ 8. APPROV│──→ Klik "Continue" → "Allow"                  │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    Poll auth.x.ai/oauth2/token                │
│  │ 9. TOKEN │──→ Dapatkan access_token + refresh_token      │
│  └────┬─────┘                                               │
│       ▼                                                     │
│  ┌──────────┐    POST /api/oauth/grok-cli/exchange          │
│  │ 10.PUSH  │──→ Atau INSERT langsung ke SQLite 9Router     │
│  └──────────┘                                               │
│                                                             │
│  ✅ Akun berhasil! Ulangi dari langkah 1 untuk akun berikut │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Persyaratan

### Wajib

| Persyaratan | Versi | Keterangan |
|-------------|-------|------------|
| **Python** | 3.14+ | Download di [python.org](https://python.org) |
| **Google Chrome** | Terbaru | Harus terinstall di sistem |
| **9Router** | Terbaru | Server proxy AI — [decolua/9router](https://github.com/decolua/9router) |
| **Migadu Email** | — | Akun email dengan fitur catch-all domain |

### Opsional

| Persyaratan | Kegunaan |
|-------------|----------|
| **Proxy (SOCKS5/HTTP)** | Rotasi IP untuk hindari rate limit |
| **HP Android + ADB** | Rotasi IP via airplane mode (gratis) |
| **FastAPI + Uvicorn** | Untuk menjalankan web control panel |

---

## 📦 Instalasi

> **Untuk pemula:** Ikuti langkah-langkah ini satu per satu. Jangan lupa baca komentar di setiap langkah ya!

### Langkah 1: Clone Repository

Buka terminal (Command Prompt / PowerShell / Git Bash), lalu ketik:

```bash
git clone https://github.com/nousresearch/grokidding.git
cd grokidding
```

### Langkah 2: Install Dependencies

```bash
pip install -r requirements.txt
```

**Isi `requirements.txt`:**
```
DrissionPage>=4.1
curl_cffi>=0.7
lxml>=5.0
```

> 💡 **Tips:** Kalau mau pakai web panel, install juga:
> ```bash
> pip install fastapi uvicorn[standard] requests pydantic
> ```

### Langkah 3: Buat File Konfigurasi

Salin contoh config dan edit dengan data kamu:

```bash
cp config.example.json config.json
```

> ⚠️ **Penting:** Edit `config.json` dengan credential kamu sendiri! Lihat bagian [Konfigurasi](#️-konfigurasi) di bawah.

### Langkah 4: Siapkan Email Catch-All

Kamu butuh domain email dengan fitur **catch-all**. Artinya, email apapun yang dikirim ke `*@domainmu.com` akan masuk ke satu inbox.

Contoh menggunakan **Migadu**:
1. Daftar di [migadu.com](https://migadu.com) (ada paket gratis)
2. Tambahkan domain kamu
3. Aktifkan fitur **Catch-All** di pengaturan domain
4. Catat: IMAP host (`imap.migadu.com`), port (993), email, dan password

### Langkah 5: Siapkan 9Router

Pastikan 9Router sudah berjalan:

```bash
# Install 9Router jika belum
npm install -g 9router

# Jalankan 9Router
9router
```

Catat URL 9Router (misalnya `http://localhost:3000`) dan password-nya.

### Langkah 6: Verifikasi Instalasi

```bash
python -m grok_farmer --dry-run --count 1
```

Kalau berhasil, kamu akan melihat output seperti:
```
============================================================
  GROKKIDDING -> 9Router
============================================================
  [DRY RUN] email=a9k2m1x@domain.com, name=Budi Sari
  DONE: 1/1 accounts created
============================================================
```

Selamat! Grokidding sudah siap dipakai! 🎉

---

## ⚙️ Konfigurasi

Semua konfigurasi ada di file `config.json`. Berikut penjelasan setiap bagian:

### Struktur Lengkap

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
      "socks5://user:pass@proxy2.com:1080"
    ],
    "adb": {
      "enabled": false,
      "device_serial": "DEVICE_SERIAL",
      "adb_path": "adb"
    }
  },
  "turnstile": {
    "solver": "drissionpage",
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

### Penjelasan Detail

#### `ninrouter` — Koneksi ke 9Router

| Field | Tipe | Keterangan |
|-------|------|------------|
| `base_url` | string | URL 9Router (misal: `http://localhost:3000` atau tunnel URL) |
| `password` | string | Password login dashboard 9Router |
| `db_path` | string | Path absolut ke file SQLite 9Router. **Wajib** untuk push via SQLite fallback |

#### `email` — Konfigurasi Email

| Field | Tipe | Keterangan |
|-------|------|------------|
| `imap_host` | string | Server IMAP. Migadu: `imap.migadu.com` |
| `imap_port` | number | Port IMAP (SSL). Biasanya `993` |
| `email` | string | Alamat email untuk login IMAP (admin/catch-all address) |
| `password` | string | Password email IMAP |
| `domain` | string | Domain untuk generate email random. Contoh: `domainmu.com` |

#### `proxy` — Konfigurasi Proxy

| Field | Tipe | Keterangan |
|-------|------|------------|
| `mode` | string | Tipe proxy default: `socks5`, `socks4`, `http`, atau `https` |
| `pool` | array | Daftar URL proxy. Akan dirotasi tiap akun |
| `adb.enabled` | boolean | `true` untuk aktifkan rotasi IP via ADB |
| `adb.device_serial` | string | Serial number HP Android (dari `adb devices`) |
| `adb.adb_path` | string | Path ke executable ADB |

#### `turnstile` — Cloudflare Turnstile Solver

| Field | Tipe | Keterangan |
|-------|------|------------|
| `solver` | string | Metode solver. Gunakan `"drissionpage"` |
| `extension_path` | string | Path ke folder Chrome extension. Default: `"turnstile_patch/"` |
| `max_retries` | number | Jumlah percobaan solve Turnstile. Default: `15` |
| `timeout` | number | Timeout detik per percobaan. Default: `60` |

#### `signup` — Pengaturan Registrasi

| Field | Tipe | Keterangan |
|-------|------|------------|
| `password_length` | number | Panjang password yang di-generate. Default: `16` |
| `max_retries` | number | Jumlah retry jika registrasi gagal. Default: `3` |

#### `output` — Lokasi Output

| Field | Tipe | Keterangan |
|-------|------|------------|
| `accounts_dir` | string | Folder penyimpanan JSON akun. Default: `"data/accounts/"` |
| `logs_dir` | string | Folder penyimpanan log. Default: `"data/logs/"` |

---

## 🚀 Tutorial Penggunaan

### 🟢 Tutorial CLI (Command Line)

Ini cara paling dasar untuk menjalankan Grokidding dari terminal.

#### Menjalankan 1 Akun

```bash
python -m grok_farmer run
```

Apa yang terjadi:
1. Browser Chrome terbuka
2. Grokidding mendaftar akun baru di xAI
3. OTP dibaca dari email
4. Akun diverifikasi
5. Token dikirim ke 9Router
6. Browser tertutup
7. Selesai! ✅

#### Menjalankan Banyak Akun

```bash
python -m grok_farmer run --count 10
```

Ini akan membuat **10 akun** sekaligus. Setiap akun pakai proxy berbeda (jika tersedia).

#### Mode Kering (Dry Run)

```bash
python -m grok_farmer run --dry-run --count 5
```

> **Apa itu Dry Run?** Mode ini hanya **generate** email dan password, tapi **tidak benar-benar mendaftar**. Cocok untuk testing apakah konfigurasi sudah benar.

#### Tanpa Proxy

```bash
python -m grok_farmer run --no-proxy --count 1
```

> ⚠️ **Peringatan:** Tanpa proxy, semua akun dari IP yang sama. xAI bisa memblokir setelah beberapa akun. Gunakan proxy untuk hasil terbaik.

#### Semua Opsi CLI

```
python -m grok_farmer run [opsi]

Opsi:
  --count N       Jumlah akun yang dibuat (default: 1)
  --config PATH   Path ke file config (default: config.json)
  --dry-run       Hanya generate kredensial, tidak daftar sungguhan
  --no-proxy      Matikan rotasi proxy
```

### 🔵 Tutorial Web Panel

Panel web memberikan **dashboard visual** untuk mengontrol Grokidding dari browser.

#### Memulai Panel

```bash
python -m grok_farmer panel --port 8080
```

Lalu buka browser dan akses: **http://localhost:8080**

#### Fitur Panel

Panel punya beberapa tab:

**📊 Dashboard / Home**
- Statistik akun: total, aktif, exhausted, error
- Grafik penggunaan quota
- Tombol mulai farming dari panel

**🚀 Farming**
- Isi jumlah akun yang ingin dibuat
- Pilih mau pakai proxy atau tidak
- Aktifkan dry run jika hanya testing
- Klik "Start Farming" — progress berjalan real-time via WebSocket

**📋 Accounts**
- Lihat semua akun Grok yang tersimpan di 9Router
- Status setiap akun: ✅ active, ⚠️ exhausted, ❌ error
- Tombol hapus akun individual

**📊 Quota**
- Cek sisa quota setiap akun (500 queries/24 jam)
- Lihat penggunaan total dari semua akun
- Identifikasi akun yang sudah habis

**🔄 Renew**
- Otomatis deteksi akun expired
- Hapus dari 9Router dan xAI
- Buat akun pengganti sekaligus
- Satu klik, selesai!

**📝 Logs**
- Log real-time dari setiap proses farming
- Log historis dari file
- Stream via WebSocket

**⚙️ Settings**
- Lihat dan edit `config.json` dari panel
- Test koneksi proxy
- Test koneksi ADB

#### Semua Opsi Panel

```
python -m grok_farmer panel [opsi]

Opsi:
  --port PORT     Port server (default: 8080)
  --host HOST     Bind host (default: 0.0.0.0)
  --config PATH   Path ke file config
```

### 🟡 Tutorial Renew (Perpanjangan Akun)

Akun Grok gratis punya limit **500 queries per 24 jam**. Setelah habis, akun jadi "exhausted" (kode 429). Grokidding bisa **otomatis** mengganti akun yang expired.

#### Via Panel Web (Termudah)

1. Buka panel → tab **Quota**
2. Klik **"Check Quota"** → lihat akun mana yang expired
3. Klik tab **Renew**
4. Pilih berapa akun yang mau di-replace (atau biarkan auto)
5. Klik **"Renew"**
6. Grokidding akan:
   - ✅ Hapus akun expired dari xAI
   - ✅ Hapus koneksi dari 9Router
   - ✅ Buat akun baru pengganti
   - ✅ Push ke 9Router

#### Via API

```bash
# Cek quota
curl http://localhost:8080/api/check-quota

# Renew semua yang expired
curl -X POST http://localhost:8080/api/renew \
  -H "Content-Type: application/json" \
  -d '{"count": 0, "proxy": true}'
```

> **`count: 0`** berarti "auto" — ganti semua yang expired.

---

## 🖥️ Mode Operasi

Grokidding punya **2 mode** operasi:

| | CLI (`run`) | Web Panel (`panel`) |
|---|---|---|
| **Antarmuka** | Terminal/command line | Browser web (dashboard) |
| **Monitoring** | Print ke terminal | Real-time WebSocket |
| **Quota Check** | ❌ Tidak ada | ✅ Ada |
| **Renew** | ❌ Manual | ✅ Satu klik |
| **Settings** | Edit file manual | Edit dari panel |
| **Proxy Test** | ❌ | ✅ |
| **Request Log** | ❌ | ✅ Proxy endpoint |
| **Multi-user** | ❌ | ✅ Bisa diakses jaringan |
| **Headless** | ✅ Dengan `--headless` | ✅ Selalu |

**Rekomendasi:**
- 🟢 **Pemula / Pertama kali** → Pakai **CLI** dulu untuk testing
- 🔵 **Production / Harian** → Pakai **Web Panel** untuk kemudahan monitoring

---

## 🌐 Proxy

### Tipe Proxy yang Didukung

| Tipe | Format | Contoh |
|------|--------|--------|
| **SOCKS5 + Auth** | `socks5://user:pass@host:port` | `socks5://abc:xyz@proxy.com:1080` |
| **SOCKS5 No Auth** | `socks5://host:port` | `socks5://proxy.com:1080` |
| **SOCKS4** | `socks4://host:port` | `socks4://proxy.com:1080` |
| **HTTP** | `http://user:pass@host:port` | `http://abc:xyz@proxy.com:8080` |
| **HTTPS** | `https://user:pass@host:port` | `https://abc:xyz@proxy.com:443` |

### Cara Menambah Proxy

Edit `config.json`, tambahkan proxy ke array `proxy.pool`:

```json
{
  "proxy": {
    "mode": "socks5",
    "pool": [
      "socks5://user1:pass1@server1.com:1080",
      "socks5://user2:pass2@server2.com:1080",
      "http://user3:pass3@server3.com:8080"
    ]
  }
}
```

> 💡 **Tips:** Minimal 3-5 proxy untuk hasil terbaik. Setiap akun pakai proxy berbeda.

### Cara Test Proxy

Via panel web:
1. Buka tab **Settings**
2. Klik **"Test Proxy"**
3. Masukkan URL proxy
4. Lihat hasil: IP yang terdeteksi + status koneksi

Via terminal:
```bash
curl --proxy socks5://user:pass@server.com:1080 https://httpbin.org/ip
```

### Rotasi IP via ADB (Alternatif Gratis)

Kalau kamu punya HP Android, kamu bisa ganti IP tanpa proxy:

1. Aktifkan **USB Debugging** di HP Android
2. Sambungkan HP ke komputer via kabel USB
3. Cek serial number: `adb devices`
4. Edit `config.json`:

```json
{
  "proxy": {
    "adb": {
      "enabled": true,
      "device_serial": "ABCD1234",
      "adb_path": "D:/path/to/adb.exe"
    }
  }
}
```

Cara kerja: setiap akun baru → toggle airplane mode → dapat IP baru dari ISP.

---

## 🔧 Troubleshooting

### Masalah Umum

#### ❌ "Config not found: config.json"

**Penyebab:** File `config.json` belum dibuat atau path salah.

**Solusi:**
```bash
# Pastikan kamu ada di folder grok-farmer
cd grok-farmer

# Buat config dari contoh
cp config.example.json config.json

# Edit dengan data kamu
nano config.json  # atau pakai editor favorit
```

---

#### ❌ "OTP timeout (300s)"

**Penyebab:** Email OTP tidak masuk dalam 5 menit.

**Solusi:**
1. Pastikan domain catch-all aktif
2. Cek IMAP connection manual:
   ```bash
   python -c "
   from grok_farmer.email_reader import IMAPOtpReader
   r = IMAPOtpReader('imap.migadu.com', 993, 'otp@domain.com', 'pass')
   r.connect()
   print('OK')
   "
   ```
3. Pastikan `domain` di config sesuai dengan domain catch-all
4. Cek folder spam di email admin

---

#### ❌ "Could not find 'Sign up with email' button"

**Penyebab:** Halaman xAI berubah atau diblokir.

**Solusi:**
1. Pastikan Chrome terinstall dan bisa buka `accounts.x.ai`
2. Coba tanpa proxy dulu (`--no-proxy`)
3. Update DrissionPage: `pip install --upgrade DrissionPage`

---

#### ❌ "Push failed" (9Router)

**Penyebab:** 9Router tidak bisa diakses atau SQLite locked.

**Solusi:**
1. Pastikan 9Router berjalan: buka `base_url` di browser
2. Cek `db_path` — harus menunjuk ke file SQLite yang benar
3. Pastikan 9Router tidak sedang dipakai proses lain
4. Coba restart 9Router

---

#### ❌ Cloudflare Turnstile Gagal

**Penyebab:** Extension patch tidak terload atau Chrome versi baru.

**Solusi:**
1. Pastikan folder `turnstile_patch/` ada dengan isi:
   - `manifest.json`
   - `script.js`
2. Cek `max_retries` di config (default 15, bisa dinaikkan ke 25)
3. Update Chrome ke versi terbaru

---

#### ❌ Browser Tidak Muncul (Headless Mode)

Ini normal! Di headless mode, Chrome berjalan di background tanpa jendela.

---

#### ❌ Rate Limit / IP Diblokir

**Penyebab:** Terlalu banyak akun dari IP sama.

**Solusi:**
1. Tambah proxy ke pool
2. Gunakan ADB rotation
3. Tambah delay antar akun
4. Kurangi jumlah akun per batch

---

## 📁 Arsitektur

### Struktur File & Folder

```
grokidding/                          ← Root project
│
├── config.json                      ← Konfigurasi utama (isi credential kamu)
├── config.example.json              ← Template config (tanpa credential)
├── requirements.txt                 ← Dependencies Python
├── README.md                        ← Dokumentasi ini
├── PLAN.md                          ← Rencana pengembangan
├── .gitignore                       ← Git ignore rules
│
├── grok_farmer/                     ← Paket Python utama
│   ├── __init__.py                  ← Inisialisasi paket
│   ├── __main__.py                  ← CLI entry point + main farming loop
│   ├── config.py                    ← Config loader & validator
│   ├── signup.py                    ← gRPC-Web registration flow
│   ├── email_reader.py              ← IMAP OTP polling (Migadu)
│   ├── turnstile.py                 ← DrissionPage + Turnstile solver
│   ├── oauth.py                     ← OAuth device code flow
│   ├── router_push.py               ← Push ke 9Router (API + SQLite)
│   ├── proxy.py                     ← Multi-protocol proxy rotation + ADB
│   ├── grpc_web.py                  ← gRPC-Web codec (encode/decode/frame)
│   ├── utils.py                     ← Helper functions (generate, save, log)
│   ├── panel.py                     ← FastAPI web panel server
│   │
│   └── static/
│       └── index.html               ← Dashboard HTML (single-file, dark theme)
│
├── turnstile_patch/                 ← Chrome extension untuk Turnstile bypass
│   ├── manifest.json                ← Extension manifest (MV3)
│   └── script.js                    ← Turnstile patch script
│
└── data/                            ← Output data (auto-generated)
    ├── accounts/                    ← JSON backup setiap akun
    │   └── grok_email_20260721T...json
    └── logs/                        ← Log harian
        └── run_2026-07-21.log
```

### Penjelasan Modul

| Modul | Fungsi | Tipe Koneksi |
|-------|--------|--------------|
| `__main__.py` | Entry point CLI, main loop, argparse | - |
| `config.py` | Load & validasi `config.json` | File I/O |
| `signup.py` | Registrasi via gRPC-Web + Next.js Server Action | HTTP → `accounts.x.ai` |
| `email_reader.py` | Polling OTP via IMAP | IMAP → `imap.migadu.com` |
| `turnstile.py` | Browser automation + Turnstile solve | DrissionPage (Chrome) |
| `oauth.py` | OAuth device code + token polling | HTTP → `auth.x.ai` |
| `router_push.py` | Push token ke 9Router | HTTP → 9Router / SQLite |
| `proxy.py` | Proxy rotation + ADB airplane mode | Socket / ADB |
| `grpc_web.py` | Protobuf encode/decode + gRPC-Web framing | Pure Python |
| `utils.py` | Generate email/password/name, logging | File I/O |
| `panel.py` | FastAPI server + WebSocket + Grok proxy | HTTP/WS → all above |

---

## 🛠️ Teknologi

| Komponen | Teknologi | Versi | Fungsi |
|----------|-----------|-------|--------|
| **Bahasa** | Python | 3.14 | Runtime utama |
| **Browser** | DrissionPage | ≥4.1 | Browser automation (Chrome) |
| **TLS Fingerprint** | curl_cffi | ≥0.7 | HTTP client dengan fingerprint Chrome 131 |
| **gRPC-Web** | Custom codec | - | Encode/decode protobuf untuk xAI API |
| **IMAP** | imaplib (stdlib) | - | Baca OTP dari email |
| **Web Panel** | FastAPI | latest | REST API + WebSocket server |
| **Server** | Uvicorn | latest | ASGI server untuk panel |
| **Turnstile** | Chrome Extension (MV3) | 2.1 | Bypass Cloudflare CAPTCHA |
| **Proxy** | SOCKS5/4, HTTP, HTTPS | - | Rotasi IP per akun |
| **Database** | SQLite3 (9Router) | - | Push token langsung ke DB |
| **CLI** | argparse (stdlib) | - | Command-line interface |

### API Endpoints yang Digunakan

| Endpoint | Fungsi |
|----------|--------|
| `accounts.x.ai/sign-up` | Halaman registrasi |
| `accounts.x.ai/auth_mgmt.AuthManagement/CreateEmailValidationCode` | Kirim OTP (gRPC-Web) |
| `accounts.x.ai/auth_mgmt.AuthManagement/VerifyEmailValidationCode` | Verifikasi OTP (gRPC-Web) |
| `auth.x.ai/oauth2/device/code` | Request device code |
| `auth.x.ai/oauth2/token` | Poll OAuth token |
| `cli-chat-proxy.grok.com/v1/responses` | Proxy Grok CLI requests |

---

## 🙏 Credits

Grokidding dibangun berkat riset dan kode sumber dari komunitas berikut:

| Kontributor | Repo | Kontribusi |
|-------------|------|------------|
| **dongguatanglinux** | [grok-build-auth](https://github.com/dongguatanglinux/grok-build-auth) | Protokol gRPC-Web untuk xAI AuthManagement |
| **ReinerBRO** | [grok-register](https://github.com/ReinerBRO/grok-register) | Chrome extension Turnstile patch (⭐385) |
| **decolua** | [9router](https://github.com/decolua/9router) | OAuth config & provider connection format |

> **Catatan:** Grokidding adalah integrator — menggabungkan teknik dari repo di atas menjadi satu pipeline otomatis end-to-end.

---

## 📄 License

**MIT License**

```
MIT License

Copyright (c) 2026 Nous Research

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<div align="center">

### ⭐ Kalau proyek ini bermanfaat, kasih bintang ya!

**Dibuat dengan ❤️ oleh Nous Research**

</div>
