"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "motion/react";
import {
  Gear,
  ArrowClockwise,
  FloppyDisk,
  Prohibit,
  Eye,
  EyeSlash,
} from "@phosphor-icons/react";
import { getSettings, updateSettings } from "@/lib/api";
import type { Settings } from "@/lib/types";
import clsx from "clsx";

function SettingGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
      <div className="border-b border-[var(--color-border)] px-5 py-3">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">{title}</h3>
      </div>
      <div className="p-5">
        {children}
      </div>
    </div>
  );
}

function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 py-2 first:pt-0 last:pb-0">
      <label className="text-[13px] font-medium text-[var(--color-text)]">{label}</label>
      {description && (
        <p className="text-[12px] text-[var(--color-text-muted)]">{description}</p>
      )}
      <div className="mt-1">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPasswords, setShowPasswords] = useState(false);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = useCallback(async () => {
    if (!settings) return;
    setSaving(true);
    setError(null);
    try {
      await updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }, [settings]);

  const updateNested = useCallback((path: string[], value: unknown) => {
    setSettings((prev) => {
      if (!prev) return prev;
      const next = JSON.parse(JSON.stringify(prev));
      let obj: Record<string, unknown> = next;
      for (let i = 0; i < path.length - 1; i++) {
        if (!obj[path[i]]) obj[path[i]] = {};
        obj = obj[path[i]] as Record<string, unknown>;
      }
      obj[path[path.length - 1]] = value;
      return next;
    });
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <ArrowClockwise size={20} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  const proxy = (settings?.proxy as Record<string, unknown>) || {};
  const ninrouter = (settings?.ninrouter as Record<string, unknown>) || {};
  const email = (settings?.email as Record<string, unknown>) || {};

  return (
    <div className="mx-auto max-w-3xl px-6 py-8 lg:px-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text)]">Settings</h1>
          <p className="mt-0.5 text-sm text-[var(--color-text-muted)]">
            Configure farming parameters
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !settings}
          className={clsx(
            "flex items-center gap-2 rounded-[var(--radius-full)] px-5 py-2.5 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-all duration-150 active:scale-[0.98] cursor-pointer",
            saved
              ? "bg-[var(--color-success)]"
              : "bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)]",
            saving && "opacity-70"
          )}
        >
          {saved ? (
            <>
              <FloppyDisk size={14} />
              Saved
            </>
          ) : saving ? (
            <>
              <ArrowClockwise size={14} className="animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <FloppyDisk size={14} />
              Save
            </>
          )}
        </button>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 rounded-[var(--radius-md)] border border-[var(--color-error-subtle)] bg-[var(--color-error-subtle)] p-3 text-sm text-[var(--color-error)]"
        >
          {error}
        </motion.div>
      )}

      <div className="space-y-4">
        {/* Proxy settings */}
        <SettingGroup title="Proxy">
          <SettingRow label="Use Proxy" description="Route farming through proxy">
            <select
              value={String(proxy.enabled ?? true)}
              onChange={(e) => updateNested(["proxy", "enabled"], e.target.value === "true")}
              className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
            >
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </SettingRow>
          <SettingRow label="Proxy Pool" description="Proxy URLs (one per line)">
            <textarea
              value={((proxy.pool as string[]) || []).join("\n")}
              onChange={(e) =>
                updateNested(
                  ["proxy", "pool"],
                  e.target.value.split("\n").filter(Boolean)
                )
              }
              rows={3}
              placeholder="socks5://user:pass@host:port"
              className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-[13px] text-[var(--color-text)] transition-colors placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
            />
          </SettingRow>
        </SettingGroup>

        {/* 9Router settings */}
        <SettingGroup title="9Router">
          <SettingRow label="API URL" description="9Router API endpoint">
            <input
              type="text"
              value={String(ninrouter.api_url ?? "http://localhost:20128")}
              onChange={(e) => updateNested(["ninrouter", "api_url"], e.target.value)}
              className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] transition-colors focus:border-[var(--color-accent)] focus:outline-none"
            />
          </SettingRow>
          <SettingRow label="Password">
            <div className="relative">
              <input
                type={showPasswords ? "text" : "password"}
                value={String(ninrouter.password ?? "")}
                onChange={(e) => updateNested(["ninrouter", "password"], e.target.value)}
                className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 pr-10 text-sm text-[var(--color-text)] transition-colors focus:border-[var(--color-accent)] focus:outline-none"
              />
              <button
                onClick={() => setShowPasswords(!showPasswords)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)] cursor-pointer"
              >
                {showPasswords ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </SettingRow>
          <SettingRow label="DB Path" description="SQLite database path (leave empty for auto-detect)">
            <input
              type="text"
              value={String(ninrouter.db_path ?? "")}
              onChange={(e) => updateNested(["ninrouter", "db_path"], e.target.value)}
              placeholder="Auto-detect"
              className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-[13px] text-[var(--color-text)] transition-colors placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
            />
          </SettingRow>
        </SettingGroup>

        {/* Email settings */}
        <SettingGroup title="Email Provider">
          <SettingRow label="Provider" description="Email OTP provider">
            <select
              value={String(email.provider ?? "generator.email")}
              onChange={(e) => updateNested(["email", "provider"], e.target.value)}
              className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
            >
              <option value="generator.email">generator.email</option>
              <option value="imap">IMAP</option>
            </select>
          </SettingRow>
        </SettingGroup>
      </div>
    </div>
  );
}
