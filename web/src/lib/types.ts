/* ── Grokidding TypeScript Types ── */

export interface Account {
  id: string;
  email: string;
  name: string;
  active: boolean;
  status: "active" | "exhausted" | "error" | "unavailable" | "unknown" | "no_token";
  error_code?: number;
  last_error?: string;
  last_error_at?: string;
  model_lock?: string[];
  backoff_level?: number;
  auth_type?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Stats {
  total: number;
  active: number;
  exhausted: number;
  errored: number;
  rate: number;
}

export interface FarmStatus {
  running: boolean;
  total: number;
  completed: number;
  successful: number;
  failed: number;
  current_step: string;
  current_email: string;
  started_at: string | null;
  finished_at: string | null;
  progress: number;
}

export interface FarmRequest {
  count: number;
  proxy: boolean;
  dry_run: boolean;
  parallel: boolean;
  cooldown: number;
}

export interface SessionHistory {
  id: string;
  started_at: string;
  finished_at?: string;
  total: number;
  successful: number;
  failed: number;
  duration?: number;
}

export interface QuotaAccount {
  name: string;
  email: string;
  status: string;
  limit: number;
  remaining: number;
  used: number;
}

export interface QuotaData {
  total_accounts: number;
  total_limit: number;
  total_remaining: number;
  total_used: number;
  accounts: QuotaAccount[];
}

export interface Settings {
  [key: string]: unknown;
}

export interface LogResponse {
  logs: string[];
  panel_logs: string[];
}

// WebSocket message types
export type WSMessage =
  | { type: "log"; line: string }
  | { type: "progress"; data: FarmStatus }
  | { type: "quota"; data: QuotaData };
