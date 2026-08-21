"use client";

import { useEffect, useState, useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  Users,
  CheckCircle,
  WarningCircle,
  TrendUp,
  ArrowClockwise,
} from "@phosphor-icons/react";
import { getStats, getAccounts, getStatus } from "@/lib/api";
import type { Stats, Account, FarmStatus } from "@/lib/types";

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [farmStatus, setFarmStatus] = useState<FarmStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const reduce = useReducedMotion();

  const fetchData = async () => {
    try {
      const [s, a, st] = await Promise.all([
        getStats(),
        getAccounts(),
        getStatus(),
      ]);
      setStats(s);
      setAccounts(a);
      setFarmStatus(st);
    } catch (e) {
      console.error("Failed to fetch dashboard data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return (
      <div className="mx-auto max-w-5xl px-5 pt-14 lg:px-8 lg:pt-8">
        <div className="mb-8">
          <div className="skeleton mb-3 h-8 w-40 rounded-lg" />
          <div className="skeleton h-4 w-64 rounded-lg" />
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-28 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  const recentAccounts = accounts.slice(0, 8);

  return (
    <div className="mx-auto max-w-5xl px-5 pt-14 lg:px-8 lg:pt-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[28px] font-bold tracking-tight text-[var(--color-text)]">
            Dashboard
          </h1>
          <p className="mt-1 text-[14px] text-[var(--color-text-secondary)]">
            Overview of your Grok accounts and farming status.
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-secondary)] transition-all hover:bg-[var(--color-bg-muted)] active:scale-[0.98]"
        >
          <ArrowClockwise size={16} />
          Refresh
        </button>
      </div>

      {/* Farm progress banner */}
      {farmStatus?.running && (
        <motion.div
          initial={reduce ? false : { opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex items-center gap-3 rounded-2xl border border-[var(--color-accent-subtle)] bg-[var(--color-accent-subtle)] px-4 py-3"
        >
          <div className="h-2 w-2 animate-pulse rounded-full bg-[var(--color-accent)]" />
          <p className="text-[14px] font-medium text-[var(--color-text)]">
            {farmStatus.current_step}
          </p>
          <div className="ml-auto flex items-center gap-3">
            <span className="font-mono text-[13px] text-[var(--color-text-secondary)]">
              {farmStatus.completed}/{farmStatus.total}
            </span>
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[var(--color-bg-muted)]">
              <div
                className="h-full rounded-full bg-[var(--color-accent)] transition-all duration-500"
                style={{ width: `${farmStatus.progress}%` }}
              />
            </div>
          </div>
        </motion.div>
      )}

      {/* Stat cards — iOS widget style */}
      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          icon={Users}
          label="Total Accounts"
          value={stats?.total ?? 0}
          color="bg-[var(--color-accent-subtle)] text-[var(--color-accent)]"
          delay={0}
        />
        <StatCard
          icon={CheckCircle}
          label="Active"
          value={stats?.active ?? 0}
          color="bg-[var(--color-success-subtle)] text-[var(--color-success)]"
          delay={0.06}
        />
        <StatCard
          icon={WarningCircle}
          label="Exhausted"
          value={stats?.exhausted ?? 0}
          color="bg-[var(--color-warning-subtle)] text-[var(--color-warning)]"
          delay={0.12}
        />
        <StatCard
          icon={TrendUp}
          label="Success Rate"
          value={`${stats?.rate ?? 0}%`}
          color="bg-[var(--color-success-subtle)] text-[var(--color-success)]"
          delay={0.18}
        />
      </div>

      {/* Recent accounts table */}
      <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <h2 className="text-[16px] font-semibold text-[var(--color-text)]">
            Recent Accounts
          </h2>
          <span className="font-mono text-[13px] text-[var(--color-text-muted)]">
            {stats?.total ?? 0} total
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                  Email
                </th>
                <th className="hidden px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)] sm:table-cell">
                  Name
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                  Status
                </th>
                <th className="hidden px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)] sm:table-cell">
                  Auth
                </th>
              </tr>
            </thead>
            <tbody>
              {recentAccounts.map((account) => (
                <tr
                  key={account.id}
                  className="border-b border-[var(--color-border)] transition-colors last:border-0 hover:bg-[var(--color-bg-subtle)]"
                >
                  <td className="px-5 py-3 font-mono text-[13px] text-[var(--color-text-secondary)]">
                    {account.email || "?"}
                  </td>
                  <td className="hidden px-5 py-3 text-[14px] font-medium text-[var(--color-text)] sm:table-cell">
                    {account.name}
                  </td>
                  <td className="px-5 py-3">
                    <StatusBadge status={account.status} />
                  </td>
                  <td className="hidden px-5 py-3 text-[13px] text-[var(--color-text-muted)] sm:table-cell">
                    {account.auth_type || "oauth"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
  delay,
}: {
  icon: typeof Users;
  label: string;
  value: string | number;
  color: string;
  delay: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!ref.current || reduce) return;
    const el = ref.current;
    import("gsap").then(({ gsap }) => {
      gsap.fromTo(
        el,
        { y: 16, autoAlpha: 0 },
        { y: 0, autoAlpha: 1, duration: 0.5, delay, ease: "back.out(1.4)" }
      );
    });
  }, [delay, reduce]);

  return (
    <div
      ref={ref}
      className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4 shadow-[var(--shadow-sm)] transition-shadow duration-200 hover:shadow-[var(--shadow-md)] sm:p-5"
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] ${color}`}
          >
            <Icon size={16} weight="duotone" />
          </div>
          <p className="truncate text-[12px] font-medium text-[var(--color-text-secondary)] sm:text-[13px]">
            {label}
          </p>
        </div>
        <p className="text-[24px] font-bold tracking-tight text-[var(--color-text)] sm:text-[26px]">
          {value}
        </p>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    active: { bg: "bg-[var(--color-success-subtle)]", text: "text-[var(--color-success)]", label: "Active" },
    exhausted: { bg: "bg-[var(--color-warning-subtle)]", text: "text-[var(--color-warning)]", label: "Exhausted" },
    error: { bg: "bg-[var(--color-error-subtle)]", text: "text-[var(--color-error)]", label: "Error" },
    unavailable: { bg: "bg-[var(--color-bg-muted)]", text: "text-[var(--color-text-muted)]", label: "N/A" },
    unknown: { bg: "bg-[var(--color-bg-muted)]", text: "text-[var(--color-text-muted)]", label: "Unknown" },
    no_token: { bg: "bg-[var(--color-bg-muted)]", text: "text-[var(--color-text-muted)]", label: "No Token" },
  };
  const s = map[status] || map.unknown;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}
