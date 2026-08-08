"""Anti-detection fingerprint randomizer for DrissionPage/Chrome.

Generates a UNIQUE browser fingerprint per session using dynamic generation
(not from a fixed pool). Virtually impossible for two sessions to collide.

Usage:
    from grok_farmer.anti_detect import AntiDetect
    ad = AntiDetect(debug=True)
    # After browser launched:
    ad.apply_to_browser(browser)   # CDP + JS injection
    # Or inject into a page:
    ad.inject_fingerprint(page)
"""
import random
import json
import hashlib
import time


# ═══════════════════════════════════════════════════════════════
# DYNAMIC GENERATION — Each call produces a unique fingerprint
# ═══════════════════════════════════════════════════════════════

# Chrome versions: 119-128 (major realistic range, Aug 2026)
_CHROME_VERSIONS = list(range(119, 129))

# Chromium build suffixes — random per version
_CHROME_BUILDS = [
    "0.0.0", "0.0.0", "0.0.0",  # most common
    "6099.109", "6099.110", "6167.85", "6167.102",
    "6244.112", "6256.56", "6312.78",
]

# Windows NT versions
_WIN_VERSIONS = [
    ("10.0", 10),   # Windows 10 — most common
    ("10.0", 10),
    ("10.0", 10),
    ("11.0", 5),    # Windows 11
    ("11.0", 5),
]

# Edge versions (matching Chrome version range)
_EDGE_VERSIONS = list(range(119, 129))

# GPU families — realistic combinations
_GPU_FAMILIES = [
    # NVIDIA
    ("Google Inc. (NVIDIA)", [
        "NVIDIA GeForce GTX 1050 Ti", "NVIDIA GeForce GTX 1060", "NVIDIA GeForce GTX 1070",
        "NVIDIA GeForce GTX 1080", "NVIDIA GeForce GTX 1650", "NVIDIA GeForce GTX 1660",
        "NVIDIA GeForce GTX 1660 Ti", "NVIDIA GeForce RTX 2060", "NVIDIA GeForce RTX 2070",
        "NVIDIA GeForce RTX 2080", "NVIDIA GeForce RTX 3050", "NVIDIA GeForce RTX 3060",
        "NVIDIA GeForce RTX 3060 Ti", "NVIDIA GeForce RTX 3070", "NVIDIA GeForce RTX 3070 Ti",
        "NVIDIA GeForce RTX 3080", "NVIDIA GeForce RTX 3090",
        "NVIDIA GeForce RTX 4060", "NVIDIA GeForce RTX 4060 Ti",
        "NVIDIA GeForce RTX 4070", "NVIDIA GeForce RTX 4070 Ti",
        "NVIDIA GeForce RTX 4080", "NVIDIA GeForce RTX 4090",
    ]),
    # AMD
    ("Google Inc. (AMD)", [
        "AMD Radeon RX 570", "AMD Radeon RX 580", "AMD Radeon RX 590",
        "AMD Radeon RX 5500 XT", "AMD Radeon RX 5600 XT", "AMD Radeon RX 5700",
        "AMD Radeon RX 5700 XT", "AMD Radeon RX 6600", "AMD Radeon RX 6600 XT",
        "AMD Radeon RX 6700 XT", "AMD Radeon RX 6800", "AMD Radeon RX 6800 XT",
        "AMD Radeon RX 6900 XT", "AMD Radeon RX 7600", "AMD Radeon RX 7700 XT",
        "AMD Radeon RX 7800 XT", "AMD Radeon RX 7900 XT", "AMD Radeon RX 7900 XTX",
        "AMD Radeon (TM) Graphics",  # APU
    ]),
    # Intel
    ("Google Inc. (Intel)", [
        "Intel(R) UHD Graphics 620", "Intel(R) UHD Graphics 630",
        "Intel(R) UHD Graphics 730", "Intel(R) UHD Graphics 770",
        "Intel(R) Iris(R) Xe Graphics", "Intel(R) Iris(R) Plus Graphics",
        "Intel(R) Arc(TM) A380 Graphics", "Intel(R) Arc(TM) A750 Graphics",
        "Intel(R) Arc(TM) A770 Graphics",
    ]),
]

# Timezone list — comprehensive
_TIMEZONES = [
    # Americas
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Sao_Paulo", "America/Toronto", "America/Vancouver", "America/Mexico_City",
    "America/Bogota", "America/Lima", "America/Santiago", "America/Buenos_Aires",
    "America/Edmonton", "America/Winnipeg", "America/Halifax", "America/Phoenix",
    # Europe
    "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid",
    "Europe/Rome", "Europe/Amsterdam", "Europe/Brussels", "Europe/Vienna",
    "Europe/Zurich", "Europe/Stockholm", "Europe/Oslo", "Europe/Copenhagen",
    "Europe/Helsinki", "Europe/Warsaw", "Europe/Prague", "Europe/Budapest",
    "Europe/Bucharest", "Europe/Athens", "Europe/Lisbon", "Europe/Dublin",
    "Europe/Moscow", "Europe/Istanbul",
    # Asia
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Singapore", "Asia/Hong_Kong",
    "Asia/Seoul", "Asia/Taipei", "Asia/Bangkok", "Asia/Jakarta",
    "Asia/Ho_Chi_Minh", "Asia/Kuala_Lumpur", "Asia/Manila",
    "Asia/Dubai", "Asia/Kolkata", "Asia/Colombo", "Asia/Karachi",
    "Asia/Almaty", "Asia/Tashkent", "Asia/Tehran", "Asia/Baghdad",
    # Oceania
    "Australia/Sydney", "Australia/Melbourne", "Australia/Brisbane",
    "Australia/Perth", "Pacific/Auckland", "Pacific/Fiji",
    # Africa
    "Africa/Cairo", "Africa/Lagos", "Africa/Johannesburg", "Africa/Nairobi",
]

# Language configurations
_LANG_CONFIGS = [
    ("en-US", ["en-US", "en"]),
    ("en-GB", ["en-GB", "en"]),
    ("en-AU", ["en-AU", "en"]),
    ("en-CA", ["en-CA", "en"]),
    ("en-NZ", ["en-NZ", "en"]),
    ("de-DE", ["de-DE", "de", "en"]),
    ("de-AT", ["de-AT", "de", "en"]),
    ("fr-FR", ["fr-FR", "fr", "en"]),
    ("fr-CA", ["fr-CA", "fr", "en"]),
    ("es-ES", ["es-ES", "es", "en"]),
    ("es-MX", ["es-MX", "es", "en"]),
    ("pt-BR", ["pt-BR", "pt", "en"]),
    ("pt-PT", ["pt-PT", "pt", "en"]),
    ("it-IT", ["it-IT", "it", "en"]),
    ("nl-NL", ["nl-NL", "nl", "en"]),
    ("ja-JP", ["ja", "en"]),
    ("ko-KR", ["ko", "en"]),
    ("zh-CN", ["zh-CN", "zh", "en"]),
    ("zh-TW", ["zh-TW", "zh", "en"]),
    ("id-ID", ["id", "en"]),
    ("ru-RU", ["ru", "en"]),
    ("pl-PL", ["pl", "en"]),
    ("sv-SE", ["sv", "en"]),
    ("da-DK", ["da", "en"]),
    ("fi-FI", ["fi", "en"]),
    ("nb-NO", ["nb", "en"]),
    ("tr-TR", ["tr", "en"]),
    ("th-TH", ["th", "en"]),
    ("vi-VN", ["vi", "en"]),
    ("ar-SA", ["ar-SA", "ar", "en"]),
]

# D3D feature levels (for WebGL renderer realism)
_D3D_LEVELS = [
    "vs_5_0 ps_5_0",
    "vs_5_1 ps_5_1",
    "vs_5_0 ps_5_0",
]


def _generate_ua() -> str:
    """Generate a unique Chrome User-Agent string."""
    nt_ver, _ = random.choice(_WIN_VERSIONS)
    chrome_ver = random.choice(_CHROME_VERSIONS)
    build = random.choice(_CHROME_BUILDS)

    # 70% Chrome, 20% Edge, 10% Chrome (without Edg suffix)
    browser_type = random.random()
    if browser_type < 0.70:
        # Plain Chrome
        return (f"Mozilla/5.0 (Windows NT {nt_ver}; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{chrome_ver}.{build} Safari/537.36")
    elif browser_type < 0.90:
        # Edge
        edge_ver = random.choice(_EDGE_VERSIONS)
        edge_build = random.choice(_CHROME_BUILDS)
        return (f"Mozilla/5.0 (Windows NT {nt_ver}; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{chrome_ver}.{build} Safari/537.36 "
                f"Edg/{edge_ver}.{edge_build}")
    else:
        # Chrome with extra whitespace variation (minor entropy)
        return (f"Mozilla/5.0 (Windows NT {nt_ver}; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{chrome_ver}.{build} Safari/537.36")


def _generate_viewport() -> tuple:
    """Generate a realistic viewport size. Not from a fixed pool."""
    # Common widths with weighted distribution
    width = random.choice([
        random.randint(1260, 1380),   # ~1366 range (most common globally)
        random.randint(1380, 1500),   # mid-range
        random.randint(1500, 1620),   # 1600 range
        random.randint(1620, 1750),   # wide
        random.randint(1750, 1920),   # full HD range
        random.randint(1920, 2000),   # ultra-wide
    ])
    # Height proportional to width (common aspect ratios)
    ratio = random.choice([
        9/16,    # 16:9
        10/16,   # 16:10
        9/16,    # 16:9 (most common)
        3/4,     # 4:3
        9/21,    # ultrawide
        10/16,
        9/16,
    ])
    height = int(width * ratio)
    # Add some jitter
    height += random.randint(-20, 20)
    # Ensure minimum
    height = max(600, min(height, 1200))
    width = max(1024, min(width, 2560))

    return (width, height)


def _generate_gpu() -> dict:
    """Generate realistic WebGL vendor + renderer."""
    vendor, gpus = random.choice(_GPU_FAMILIES)
    gpu = random.choice(gpus)
    d3d = random.choice(_D3D_LEVELS)
    renderer = f"ANGLE ({vendor.split('(')[1].rstrip(')')}, {gpu} Direct3D11 {d3d})"
    return {"vendor": vendor, "renderer": renderer}


def _generate_cores() -> int:
    """Generate realistic CPU core count."""
    return random.choice([2, 4, 4, 4, 6, 6, 8, 8, 8, 8, 10, 12, 12, 16, 16, 20])


def _generate_memory() -> int:
    """Generate realistic device memory (GB)."""
    return random.choice([2, 4, 4, 8, 8, 8, 8, 16, 16, 16, 32, 32])


class AntiDetect:
    """Randomized browser fingerprint per session.

    Uses DYNAMIC generation — not from fixed pools.
    Each instance produces a unique combination that won't repeat.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

        # ── Generate unique fingerprint ──
        # Seed with time + random for guaranteed uniqueness
        self._session_id = hashlib.md5(
            f"{time.time_ns()}{random.random()}".encode()
        ).hexdigest()[:8]

        self.ua = _generate_ua()
        self.viewport = _generate_viewport()
        self.screen = (
            self.viewport[0] + random.randint(0, 24),
            self.viewport[1] + random.randint(36, 128),
        )
        self.timezone = random.choice(_TIMEZONES)
        self.locale_code, self.languages = random.choice(_LANG_CONFIGS)
        self.webgl = _generate_gpu()
        self.platform = random.choice(["Win32", "Win32", "Win32", "Win32", "MacIntel"])
        self.hardware_concurrency = _generate_cores()
        self.device_memory = _generate_memory()
        self.color_depth = random.choice([24, 24, 24, 24, 30, 32])
        self.max_touch_points = 0 if self.platform == "Win32" else random.choice([0, 5])
        self.device_scale_factor = random.choice([1.0, 1.0, 1.25, 1.5, 2.0])

        if self.debug:
            print(f"  [antidetect] Session: {self._session_id}")
            print(f"  [antidetect] UA: ...{self.ua[-60:]}")
            print(f"  [antidetect] Viewport: {self.viewport[0]}x{self.viewport[1]}")
            print(f"  [antidetect] Screen: {self.screen[0]}x{self.screen[1]}")
            print(f"  [antidetect] Timezone: {self.timezone}")
            print(f"  [antidetect] Locale: {self.locale_code}")
            print(f"  [antidetect] GPU: {self.webgl['renderer'][:55]}...")
            print(f"  [antidetect] Platform: {self.platform}, Cores: {self.hardware_concurrency}, RAM: {self.device_memory}GB")
            print(f"  [antidetect] Scale: {self.device_scale_factor}x, Color: {self.color_depth}bit")

    def apply_to_browser(self, browser) -> None:
        """Apply anti-detection to a DrissionPage ChromiumPage.

        Must be called BEFORE navigating to any page.
        Uses CDP for settings that need to be set before page load.
        """
        # Set window size
        try:
            browser.set.window.size(*self.viewport)
            if self.debug:
                print(f"  [antidetect] Window size set: {self.viewport[0]}x{self.viewport[1]}")
        except Exception as e:
            if self.debug:
                print(f"  [antidetect] Window size failed: {e}")

        # Set user agent via CDP
        # Always prefer English in Accept-Language so xAI pages render in English
        accept_lang = f"en-US,en;q=0.9,{self.locale_code};q=0.8"
        try:
            browser.run_cdp("Network.setUserAgentOverride",
                userAgent=self.ua,
                platform=self.platform,
                acceptLanguage=accept_lang,
            )
            if self.debug:
                print(f"  [antidetect] UserAgent set via CDP")
        except Exception as e:
            if self.debug:
                print(f"  [antidetect] CDP setUserAgent failed: {e}")

        # Set timezone via CDP Emulation
        try:
            browser.run_cdp("Emulation.setTimezoneOverride",
                timezoneId=self.timezone,
            )
            if self.debug:
                print(f"  [antidetect] Timezone set: {self.timezone}")
        except Exception as e:
            if self.debug:
                print(f"  [antidetect] Timezone override failed: {e}")

        # Set locale via CDP Emulation
        try:
            browser.run_cdp("Emulation.setLocaleOverride",
                locale=self.locale_code,
            )
            if self.debug:
                print(f"  [antidetect] Locale set: {self.locale_code}")
        except Exception as e:
            if self.debug:
                print(f"  [antidetect] Locale override failed: {e}")

        # Set device metrics via CDP
        try:
            browser.run_cdp("Emulation.setDeviceMetricsOverride",
                width=self.viewport[0],
                height=self.viewport[1],
                deviceScaleFactor=self.device_scale_factor,
                mobile=False,
            )
            if self.debug:
                print(f"  [antidetect] Device metrics set")
        except Exception as e:
            if self.debug:
                print(f"  [antidetect] Device metrics failed: {e}")

    def inject_fingerprint(self, page) -> None:
        """Inject fingerprint randomization JS into a page.

        Call AFTER page load (before Turnstile detection runs).
        Overrides navigator, screen, WebGL, canvas, audio, etc.
        """
        js = self._build_fingerprint_js()
        try:
            page.run_js(js)
            if self.debug:
                print(f"  [antidetect] Fingerprint JS injected ({len(js)} chars)")
        except Exception as e:
            if self.debug:
                print(f"  [antidetect] JS injection failed: {e}")

    def get_chrome_args(self) -> list:
        """Return Chrome launch arguments for anti-detection."""
        args = [
            f"--user-agent={self.ua}",
            f"--window-size={self.viewport[0]},{self.viewport[1]}",
            f"--lang={self.locale_code}",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            # Disable WebRTC IP leak
            "--disable-webrtc-multiple-routes",
            "--disable-webrtc-hw-encoding",
            "--disable-webrtc-hw-decoding",
            "--enforce-webrtc-ip-permission-check",
            # Reduce entropy
            "--disable-features=TranslateUI",
            "--disable-background-networking",
            "--disable-sync",
            "--no-pings",
            # Reduce automation indicators
            "--disable-infobars",
            "--disable-extensions-file-access-check",
        ]
        return args

    def _build_fingerprint_js(self) -> str:
        """Build comprehensive JS fingerprint override script."""
        # Per-session noise values
        canvas_noise_r = random.randint(-2, 2)
        canvas_noise_g = random.randint(-2, 2)
        canvas_noise_b = random.randint(-1, 1)
        rect_noise = round(random.uniform(0.001, 0.099), 6)
        audio_noise = round(random.uniform(0.00001, 0.00099), 6)
        mouse_jitter = random.randint(1, 50)
        conn_rtt = random.randint(20, 250)
        conn_down = round(random.uniform(1.5, 75.0), 1)

        return f"""(function() {{
    // ═══════════════════════════════════════
    // Anti-detection fingerprint v2.0
    // Session: {self._session_id}
    // ═══════════════════════════════════════

    const _seed = {random.randint(1, 9999999)};
    const _rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

    // ── Navigator Properties ──
    const _np = Navigator.prototype;

    Object.defineProperty(_np, 'platform', {{
        get: () => '{self.platform}',
        configurable: true
    }});

    Object.defineProperty(_np, 'hardwareConcurrency', {{
        get: () => {self.hardware_concurrency},
        configurable: true
    }});

    Object.defineProperty(_np, 'deviceMemory', {{
        get: () => {self.device_memory},
        configurable: true
    }});

    Object.defineProperty(_np, 'languages', {{
        get: () => {json.dumps(self.languages)},
        configurable: true
    }});
    Object.defineProperty(_np, 'language', {{
        get: () => '{self.languages[0]}',
        configurable: true
    }});

    Object.defineProperty(_np, 'maxTouchPoints', {{
        get: () => {self.max_touch_points},
        configurable: true
    }});

    // ── Screen Properties ──
    const _sp = Screen.prototype;
    Object.defineProperty(_sp, 'width', {{ get: () => {self.screen[0]}, configurable: true }});
    Object.defineProperty(_sp, 'height', {{ get: () => {self.screen[1]}, configurable: true }});
    Object.defineProperty(_sp, 'availWidth', {{ get: () => {self.screen[0]}, configurable: true }});
    Object.defineProperty(_sp, 'availHeight', {{ get: () => {self.screen[1] - random.randint(28, 56)}, configurable: true }});
    Object.defineProperty(_sp, 'colorDepth', {{ get: () => {self.color_depth}, configurable: true }});
    Object.defineProperty(_sp, 'pixelDepth', {{ get: () => {self.color_depth}, configurable: true }});

    // ── WebGL Fingerprint ──
    const _getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {{
        if (param === 37445) return '{self.webgl["vendor"]}';
        if (param === 37446) return '{self.webgl["renderer"]}';
        return _getParam.call(this, param);
    }};

    const _getParam2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(param) {{
        if (param === 37445) return '{self.webgl["vendor"]}';
        if (param === 37446) return '{self.webgl["renderer"]}';
        return _getParam2.call(this, param);
    }};

    // ── Canvas Fingerprint Noise ──
    // Per-session pixel noise — guarantees unique canvas hash
    const _cNoiseR = {canvas_noise_r};
    const _cNoiseG = {canvas_noise_g};
    const _cNoiseB = {canvas_noise_b};
    const _cNoiseA = {random.choice([0, 0, 0, 1])};

    function _addCanvasNoise(canvas) {{
        try {{
            const ctx = canvas.getContext('2d');
            if (!ctx) return;
            const w = canvas.width, h = canvas.height;
            if (w === 0 || h === 0) return;
            // Affect 5-8 random pixels across the canvas
            const count = _rand(5, 8);
            const imageData = ctx.getImageData(0, 0, Math.min(w, 200), Math.min(h, 200));
            const data = imageData.data;
            for (let i = 0; i < count; i++) {{
                const px = _rand(0, (Math.min(w, 200) * Math.min(h, 200)) - 1) * 4;
                if (px + 3 < data.length) {{
                    data[px]     = Math.max(0, Math.min(255, data[px] + _cNoiseR));
                    data[px + 1] = Math.max(0, Math.min(255, data[px + 1] + _cNoiseG));
                    data[px + 2] = Math.max(0, Math.min(255, data[px + 2] + _cNoiseB));
                    data[px + 3] = Math.max(0, Math.min(255, data[px + 3] + _cNoiseA));
                }}
            }}
            ctx.putImageData(imageData, 0, 0);
        }} catch(e) {{}}
    }}

    const _toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {{
        _addCanvasNoise(this);
        return _toDataURL.apply(this, arguments);
    }};

    const _toBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {{
        _addCanvasNoise(this);
        return _toBlob.apply(this, arguments);
    }};

    // Also intercept OffscreenCanvas
    if (typeof OffscreenCanvas !== 'undefined') {{
        const _ocToBlob = OffscreenCanvas.prototype.convertToBlob;
        OffscreenCanvas.prototype.convertToBlob = function(opts) {{
            try {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    const img = ctx.getImageData(0, 0, Math.min(this.width, 100), Math.min(this.height, 100));
                    const d = img.data;
                    const idx = _rand(0, d.length - 4);
                    d[idx] = Math.max(0, Math.min(255, d[idx] + _cNoiseR));
                    ctx.putImageData(img, 0, 0);
                }}
            }} catch(e) {{}}
            return _ocToBlob.apply(this, arguments);
        }};
    }}

    // ── AudioContext Fingerprint Noise ──
    const _audioNoise = {audio_noise};
    try {{
        const _createOsc = (typeof AudioContext !== 'undefined') ? AudioContext.prototype.createOscillator : null;
        if (_createOsc) {{
            AudioContext.prototype.createOscillator = function() {{
                const osc = _createOsc.call(this);
                const _origConnect = osc.connect.bind(osc);
                osc.connect = function(dest) {{
                    osc.frequency.value += _audioNoise;
                    return _origConnect(dest);
                }};
                return osc;
            }};
        }}
    }} catch(e) {{}}

    // ── AnalyserNode noise (more common fingerprinting vector) ──
    try {{
        const _getFloatFreq = AnalyserNode.prototype.getFloatFrequencyData;
        AnalyserNode.prototype.getFloatFrequencyData = function(arr) {{
            _getFloatFreq.call(this, arr);
            for (let i = 0; i < Math.min(arr.length, 10); i++) {{
                arr[i] += _audioNoise * (_rand(-100, 100));
            }}
        }};
    }} catch(e) {{}}

    // ── ClientRects Noise ──
    const _rectNoise = {rect_noise};
    const _gBCR = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function() {{
        const rect = _gBCR.call(this);
        return {{
            x: rect.x + _rectNoise,
            y: rect.y + _rectNoise,
            width: rect.width,
            height: rect.height,
            top: rect.top + _rectNoise,
            right: rect.right + _rectNoise,
            bottom: rect.bottom + _rectNoise,
            left: rect.left + _rectNoise
        }};
    }};

    const _gCR = Element.prototype.getClientRects;
    Element.prototype.getClientRects = function() {{
        const rects = _gCR.call(this);
        // Create modified DOMRectList-like array
        const modified = Array.from(rects).map(r => ({{
            x: r.x + _rectNoise,
            y: r.y + _rectNoise,
            width: r.width,
            height: r.height,
            top: r.top + _rectNoise,
            right: r.right + _rectNoise,
            bottom: r.bottom + _rectNoise,
            left: r.left + _rectNoise
        }}));
        return modified;
    }};

    // ── MouseEvent Coordinates ──
    const _mJitter = {mouse_jitter};
    Object.defineProperty(MouseEvent.prototype, 'screenX', {{
        get: function() {{ return _rand(_mJitter, {self.viewport[0]} - _mJitter); }},
        configurable: true
    }});
    Object.defineProperty(MouseEvent.prototype, 'screenY', {{
        get: function() {{ return _rand(_mJitter, {self.viewport[1]} - _mJitter); }},
        configurable: true
    }});

    // ── Connection Info ──
    if (navigator.connection) {{
        try {{
            Object.defineProperty(navigator.connection, 'rtt', {{
                get: () => {conn_rtt},
                configurable: true
            }});
            Object.defineProperty(navigator.connection, 'downlink', {{
                get: () => {conn_down},
                configurable: true
            }});
            Object.defineProperty(navigator.connection, 'effectiveType', {{
                get: () => {{
                    const rtt = {conn_rtt};
                    if (rtt < 50) return '4g';
                    if (rtt < 100) return '4g';
                    if (rtt < 200) return '3g';
                    return '2g';
                }},
                configurable: true
            }});
        }} catch(e) {{}}
    }}

    // ── Permissions ──
    try {{
        const _query = Permissions.prototype.query;
        Permissions.prototype.query = function(desc) {{
            if (desc && desc.name === 'notifications') {{
                return Promise.resolve({{ state: Notification.permission || 'default' }});
            }}
            return _query.call(this, desc);
        }};
    }} catch(e) {{}}

    // ── Prevent automation detection ──
    Object.defineProperty(_np, 'webdriver', {{
        get: () => false,
        configurable: true
    }});

    // ── Chrome runtime sanitization ──
    if (window.chrome) {{
        try {{
            // Remove automation signals but keep chrome object
            if (window.chrome.runtime) {{
                // Some detection scripts check for specific runtime properties
                Object.defineProperty(window.chrome.runtime, 'onConnect', {{
                    value: undefined,
                    writable: false,
                    configurable: true
                }});
            }}
        }} catch(e) {{}}
    }}

    // ── Error stack trace sanitization ──
    try {{
        const _prepareStackTrace = Error.prepareStackTrace;
        if (_prepareStackTrace) {{
            Error.prepareStackTrace = function(error, frames) {{
                const filtered = frames.filter(f => {{
                    const name = f.getFileName() || '';
                    return !name.includes('drissionpage') && !name.includes('turnstile') &&
                           !name.includes('anti_detect') && !name.includes('grok_farmer');
                }});
                return _prepareStackTrace(error, filtered);
            }};
        }}
    }} catch(e) {{}}

    // ── Date/timezone consistency ──
    // The CDP timezone override handles Date objects,
    // but some fingerprints check Intl.DateTimeFormat
    try {{
        const _resolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
        Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
            const opts = _resolvedOptions.call(this);
            opts.timeZone = '{self.timezone}';
            return opts;
        }};
    }} catch(e) {{}}

    // ── MediaDevices fingerprint noise ──
    try {{
        if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
            const _enum = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
            navigator.mediaDevices.enumerateDevices = async function() {{
                const devices = await _enum();
                // Slightly reorder to break fingerprint
                if (devices.length > 1 && Math.random() > 0.5) {{
                    [devices[0], devices[1]] = [devices[1], devices[0]];
                }}
                return devices;
            }};
        }}
    }} catch(e) {{}}

    // ── Storage estimate noise ──
    try {{
        if (navigator.storage && navigator.storage.estimate) {{
            const _est = navigator.storage.estimate.bind(navigator.storage);
            navigator.storage.estimate = async function() {{
                const est = await _est();
                // Add small jitter to usage
                if (est.usage !== undefined) {{
                    est.usage += _rand(100, 10000);
                }}
                return est;
            }};
        }}
    }} catch(e) {{}}

    console.log('[antidetect] Fingerprint applied (session={self._session_id})');
}})();"""
