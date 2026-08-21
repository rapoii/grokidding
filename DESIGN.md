# DESIGN.md — Grokidding UI/UX Design System & Performance Standard

Dokumen ini mendefinisikan filosofi desain visual, sistem warna, arsitektur tipografi, layout responsif, dan standar performa low-end hardware pada **Grokidding Web Panel**.

---

## 1. Filosofi Desain: Editorial Minimalism & Utilitarian Anti-AI Slop

Desain antarmuka Grokidding mengadopsi standar **taste-skill** dan **ui-ux-pro-max-skill** yang mengutamakan:
- **Tenang & Jujur**: Menghindari elemen visual heboh (*neon glows, 3D cards, heavy shadows*).
- **Macro Whitespace**: Pengaturan jarak yang lapang dan bernapas antar elemen.
- **Tipografi Presisi**: Kontras visual tinggi antara heading, data teknis, dan label metrik.
- **Hardware-Friendly 60fps**: Meniadakan overhead kompilasi JavaScript runtime besar di browser pengguna.

---

## 2. Palet Warna (Warm Bone & Accent Terakota)

| Token Warna | Hex / Nilai | Penggunaan |
| :--- | :--- | :--- |
| `canvas` | `#FBFBFA` | Latar belakang kanvas utama (Warm Bone) |
| `surface` | `#FFFFFF` | Permukaan kartu, panel kontrol, dan modal |
| `surface-alt` | `#F7F6F3` | Background tabel header, secondary input, & pill tags |
| `border` | `#EAEAEA` | Garis pembatas tipis flat (1px solid) |
| `border-strong` | `#D8D5C9` | Garis fokus input & hover state |
| `text-primary` | `#111111` | Heading utama & data penting |
| `text-secondary` | `#666666` | Label deskriptif & keterangan sekunder |
| `text-muted` | `#8E8E93` | Metadata halus, placeholder, & watermark |
| `accent` | `#D97757` | Warna aksen hangat terakota (Primary Action Button) |
| `accent-hover` | `#C4684A` | State hover untuk tombol utama |
| `status-active` | `#10B981` | Status akun aktif (Emerald) |
| `status-exhausted`| `#F59E0B` | Status akun exhausted / renew needed (Amber) |
| `status-error` | `#EF4444` | Status error / koneksi putus (Rose) |

---

## 3. Tipografi & Hirarki

- **Primary Sans-Serif**: `Geist Sans`, `-apple-system`, `BlinkMacSystemFont`, `sans-serif`
  - Digunakan untuk heading, navigasi, kontrol, dan tombol antarmuka.
- **Technical Monospace**: `JetBrains Mono`, `SF Mono`, `monospace`
  - Digunakan untuk alamat email, UUID koneksi, status port, input angka, dan terminal log streaming.
- **Tracking & Weight**:
  - Judul Card Metrik: `text-[11px] uppercase tracking-wider font-semibold`
  - Angka Nilai Metrik: `text-2xl sm:text-3xl font-bold font-mono tracking-tight`

---

## 4. Layout Responsif (Desktop & Mobile 390x844)

1. **Desktop Viewport (>= 1024px)**:
   - **Stat Cards**: Grid 4 kolom simetris.
   - **Main Area**: Asymmetrical 2-kolom — Tabel akun (7 kolom) di kiri dengan sticky header, dan Terminal Live Activity Log (5 kolom) di kanan.
2. **Mobile Viewport (< 640px / 390x844)**:
   - **Stat Cards**: Grid 2x2 rapi dengan padding sentuhan yang cukup.
   - **Tabel Akun**: Otomatis bertransformasi menjadi **Card List View** vertikal yang ramah ibu jari (*thumb-friendly*).
   - **Anti-Clipping**: Tombol aksi ("Deactivate") dan teks UUID tidak pernah terpotong oleh batas viewport horizontal.

---

## 5. Standar Performa Low-End Device (60fps Engine)

- **Zero-Build Architecture**: Menggunakan Alpine.js 3 + Tailwind CSS via CDN. Tidak membutuhkan hydration cycle dari Next.js / React bundle.
- **GPU Compositing**:
  ```css
  .gpu-layer {
    will-change: transform, opacity;
    transform: translateZ(0);
  }
  ```
- **Micro-Animations via GSAP 3**: Transisi halus saat inisialisasi stat card dengan durasi cepat (< 250ms) dan akselerasi `power2.out`.
- **Accessibility & Motion Preference**:
  - Mengikuti `prefers-reduced-motion: reduce` untuk menonaktifkan seluruh animasi visual bagi perangkat dengan mode hemat daya.

---

## 6. Checklist Verifikasi Impeccable (Anti-AI Slop)

- [x] **No Fake Pulsing Dots**: Status indicator tenang dan jujur tanpa `animate-pulse` tak berdasar.
- [x] **No Nested Cards**: Menghindari pembungkus card di dalam card. Menggunakan divider tipis dan macro-spacing.
- [x] **No Generic Stock Slop**: Zero emoji berlebihan di layout, zero font Inter generic, zero drop-shadow pekat.
- [x] **Clean Audit Score**: Wajib menghasilkan `0 anti-patterns` pada audit `npx impeccable detect`.
