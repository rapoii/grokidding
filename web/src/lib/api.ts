/* ── Grokidding API Client ── */

import type {
  Account,
  Stats,
  FarmStatus,
  FarmRequest,
  SessionHistory,
  Settings,
  LogResponse,
} from "./types";

// Use relative URLs — Next.js rewrites proxy to FastAPI backend
const BASE = "";

import Cookies from "js-cookie";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = Cookies.get("auth_token");
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...init?.headers,
  };
  
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Status & Stats ──

export async function getStatus(): Promise<FarmStatus> {
  return request("/api/status");
}

export async function getStats(): Promise<Stats> {
  return request("/api/stats");
}

// ── Accounts ──

export async function getAccounts(): Promise<Account[]> {
  return request("/api/accounts");
}

export async function deleteAccount(id: string): Promise<{ deleted: string }> {
  return request(`/api/accounts/${id}`, { method: "DELETE" });
}

// ── Farming ──

export async function startFarm(req: FarmRequest): Promise<{ started: boolean; count: number }> {
  return request("/api/farm", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function stopFarm(): Promise<{ stopped: boolean }> {
  return request("/api/stop", { method: "POST" });
}

// ── Logs ──

export async function getLogs(limit = 200): Promise<LogResponse> {
  return request(`/api/logs?limit=${limit}`);
}

// ── Sessions ──

export async function getSessions(limit = 20): Promise<{ sessions: SessionHistory[] }> {
  return request(`/api/sessions?limit=${limit}`);
}

// ── Settings ──

export async function getSettings(): Promise<Settings> {
  return request("/api/settings");
}

export async function updateSettings(data: Settings): Promise<{ ok: boolean }> {
  return request("/api/settings", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Renew ──

export async function renewAccounts(): Promise<{ renewed: number; failed: number; errors: string[] }> {
  return request("/api/renew", { method: "POST", body: JSON.stringify({}) });
}

// ── Auth ──

export async function login(
  username: string,
  password: string
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      return { ok: false, error: body.error || body.detail || `HTTP ${res.status}` };
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function logout(): Promise<{ ok: boolean }> {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
    return { ok: true };
  } catch {
    return { ok: false };
  }
}

// ── Proxy Test ──

export async function testProxy(proxy: string, type = "socks5"): Promise<{ ok: boolean; ip?: string; error?: string }> {
  return request("/api/proxy/test", {
    method: "POST",
    body: JSON.stringify({ proxy, type }),
  });
}
