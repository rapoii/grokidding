"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  Gear,
  FloppyDisk,
  Prohibit,
  Eye,
  EyeSlash,
} from "@phosphor-icons/react";
import { getSettings, updateSettings } from "@/lib/api";
import type { Settings as SettingsType } from "@/lib/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsType>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const reduce = useReducedMotion();

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await getSettings();
        setSettings(data);
      } catch (e) {
        console.error("Failed to fetch settings:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error("Failed to save settings:", e);
    } finally {
      setSaving(false);
    }
  };

  const update = (key: string, value: unknown) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-5 pt-14 lg:px-8 lg:pt-8">
        <div className="skeleton mb-3 h-8 w-40 rounded-lg" />
        <div className="skeleton mb-4 h-4 w-64 rounded-lg" />
        <div className="skeleton h-64 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-5 pt-14 lg:px-8 lg:pt-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight text-[var(--color-text)]">
            Settings
          </h1>
          <p className="mt-1 text-[14px] text-[var(--color-text-secondary)]">
            Configure proxy, 9Router, and email provider.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 rounded-full bg-[var(--color-accent)] px-5 py-2.5 text-[14px] font-semibold text-[var(--color-on-accent)] transition-all hover:bg-[var(--color-accent-hover)] active:scale-[0.98] disabled:opacity-50"
        >
          <FloppyDisk size={18} />
          {saving ? "Saving..." : saved ? "Saved!" : "Save"}
        </button>
      </div>

      {/* Proxy section — iOS grouped form */}
      <SettingsGroup title="Proxy" icon={Gear}>
        <ToggleRow
          label="Enable Proxy"
          description="Route traffic through proxy pool"
          value={!!settings.proxy_enabled}
          onChange={(v) => update("proxy_enabled", v)}
        />
        <InputRow
          label="Proxy Pool URL"
          value={(settings.proxy_pool_url as string) || ""}
          onChange={(v) => update("proxy_pool_url", v)}
          placeholder="socks5://127.0.0.1:1080"
        />
        <InputRow
          label="Proxy Type"
          value={(settings.proxy_type as string) || "socks5"}
          onChange={(v) => update("proxy_type", v)}
          placeholder="socks5"
        />
      </SettingsGroup>

      {/* 9Router section */}
      <SettingsGroup title="9Router" icon={Gear}>
        <InputRow
          label="API URL"
          value={(settings.ninrouter_url as string) || ""}
          onChange={(v) => update("ninrouter_url", v)}
          placeholder="http://localhost:20128"
        />
        <InputRow
          label="Password"
          type={showPassword ? "text" : "password"}
          value={(settings.ninrouter_password as string) || ""}
          onChange={(v) => update("ninrouter_password", v)}
          placeholder="Enter password"
          icon={
            <button
              onClick={() => setShowPassword(!showPassword)}
              className="flex h-5 w-5 items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
            </button>
          }
        />
        <InputRow
          label="Database Path"
          value={(settings.ninrouter_db_path as string) || ""}
          onChange={(v) => update("ninrouter_db_path", v)}
          placeholder="C:/Users/Rafi/.9router/data.db"
          mono
        />
      </SettingsGroup>

      {/* Email section */}
      <SettingsGroup title="Email Provider" icon={Gear}>
        <InputRow
          label="IMAP Host"
          value={(settings.imap_host as string) || ""}
          onChange={(v) => update("imap_host", v)}
          placeholder="imap.migadu.com"
        />
        <InputRow
          label="IMAP Port"
          value={String(settings.imap_port || "")}
          onChange={(v) => update("imap_port", parseInt(v) || 993)}
          placeholder="993"
          mono
        />
        <InputRow
          label="Email Address"
          value={(settings.imap_user as string) || ""}
          onChange={(v) => update("imap_user", v)}
          placeholder="otp@yourdomain.tech"
        />
      </SettingsGroup>

      {/* Danger zone */}
      <div className="mt-6 overflow-hidden rounded-2xl border border-[var(--color-error-subtle)] bg-[var(--color-bg-elevated)]">
        <div className="border-b border-[var(--color-error-subtle)] px-5 py-4">
          <h2 className="flex items-center gap-2 text-[16px] font-semibold text-[var(--color-error)]">
            <Prohibit size={18} />
            Danger Zone
          </h2>
        </div>
        <div className="px-5 py-4">
          <p className="text-[13px] text-[var(--color-text-secondary)]">
            Reset all settings to defaults. This action cannot be undone.
          </p>
          <button
            onClick={() => setSettings({})}
            className="mt-3 flex items-center gap-2 rounded-full border border-[var(--color-error)] px-4 py-2 text-[13px] font-medium text-[var(--color-error)] transition-all hover:bg-[var(--color-error-subtle)] active:scale-[0.98]"
          >
            <Prohibit size={16} />
            Reset to defaults
          </button>
        </div>
      </div>
    </div>
  );
}

function SettingsGroup({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Gear;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={false}
      className="mb-6 overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]"
    >
      <div className="border-b border-[var(--color-border)] px-5 py-4">
        <h2 className="flex items-center gap-2 text-[16px] font-semibold text-[var(--color-text)]">
          <Icon size={18} className="text-[var(--color-text-muted)]" />
          {title}
        </h2>
      </div>
      <div className="divide-y divide-[var(--color-border)]">{children}</div>
    </motion.div>
  );
}

function InputRow({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  mono,
  icon,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  mono?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <div className="px-5 py-4">
      <p className="mb-2 text-[14px] font-medium text-[var(--color-text)]">{label}</p>
      <div className="relative">
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`w-full rounded-[10px] border border-[var(--color-border-strong)] bg-[var(--color-bg-subtle)] px-3 py-2.5 text-[14px] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none ${mono ? "font-mono" : ""} ${icon ? "pr-10" : ""}`}
        />
        {icon && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">{icon}</div>
        )}
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  description,
  value,
  onChange,
}: {
  label: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between px-5 py-4">
      <div>
        <p className="text-[14px] font-medium text-[var(--color-text)]">{label}</p>
        <p className="text-[12px] text-[var(--color-text-muted)]">{description}</p>
      </div>
      <button
        className="ios-toggle"
        data-on={value}
        onClick={() => onChange(!value)}
        role="switch"
        aria-checked={value}
      >
        <span className="sr-only">{label}</span>
      </button>
    </div>
  );
}
