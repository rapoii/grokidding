"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { motion } from "motion/react";
import {
  Users,
  Lightning,
  WarningCircle,
  CheckCircle,
  TrendUp,
  ArrowClockwise,
} from "@phosphor-icons/react";
import { getStats, getAccounts, getStatus } from "@/lib/api";
import type { Stats, Account, FarmStatus } from "@/lib/types";
import clsx from "clsx";

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  delay,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
  delay: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useRef(
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (!ref.current || reduced.current) return;
    const el = ref.current;
    import("gsap").then(({ gsap }) => {
      gsap.fromTo(
        el,
        { y: 16, autoAlpha: 0 },
        { y: 0, autoAlpha: 1, duration: 0.5, delay, ease: "back.out(1.4)" }
      );
    });
  }, [delay]);

  return (
    <div
      ref={ref}
      className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5 shadow-[var(--shadow-sm)] transition-shadow duration-200 hover:shadow-[var(--shadow-md)]"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[13px] text-[var(--color-text-muted)]">{label}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight text-[var(--color-text)]">
            {value}
          </p>
        </div>
        <div
          className={clsx(
            "flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)]",
            color
          )}
        >
          <Icon size={20} weight="duotone" />
        </div>
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
    <span className={clsx("inline-flex items-center rounded-[var(--radius-full)] px-2 py-0.5 text-[11px] font-medium", s.bg, s.text)}>
      {s.label}
    </span>
  );
}

function ProgressBanner({ farm }: { farm: FarmStatus }) {
  if (!farm.running) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 rounded-[var(--radius-lg)] border border-[var(--color-accent-muted)] bg-[var(--color-accent-subtle)] p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Lightning size={16} weight="fill" className="text-[var(--color-accent)] animate-pulse" />
          <span className="text-sm font-medium text-[var(--color-accent-hover)]">Farming in progress</span>
        </div>
        <span className="text-sm font-mono text-[var(--color-accent)]">
          {farm.completed}/{farm.total}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-[var(--color-accent-muted)] overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-[var(--color-accent)]"
          initial={{ width: 0 }}
          animate={{ width: `${farm.progress}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-[12px] text-[var(--color-text-secondary)]">
        <span>{farm.current_step}</span>
        <span>
          <span className="text-[var(--color-success)]">{farm.successful} ok</span>
          {" / "}
          <span className="text-[var(--color-error)]">{farm.failed} fail</span>
        </span>
      </div>
    </motion.div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [farm, setFarm] = useState<FarmStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [s, a, f] = await Promise.all([getStats(), getAccounts(), getStatus()]);
      setStats(s);
      setAccounts(a);
      setFarm(f);
    } catch {
      // API might be down
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 10000);
    return () => clearInterval(iv);
  }, [refresh]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-3 text-[var(--color-text-muted)]">
          <ArrowClockwise size={20} className="animate-spin" />
          <span className="text-sm">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  const recentAccounts = accounts.slice(0, 8);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 pl-16 lg:px-8 lg:pl-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text)]">Dashboard</h1>
          <p className="mt-0.5 text-sm text-[var(--color-text-muted)]">
            Overview of your Grok accounts and farming status
          </p>
        </div>
        <button
          onClick={refresh}
          className="flex items-center gap-2 rounded-[var(--radius-full)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-sm text-[var(--color-text-secondary)] shadow-[var(--shadow-sm)] transition-all duration-150 hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] cursor-pointer"
        >
          <ArrowClockwise size={14} />
          Refresh
        </button>
      </div>

      {/* Farm progress banner */}
      {farm && <ProgressBanner farm={farm} />}

      {/* Stat cards */}
      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Total Accounts"
          value={stats?.total ?? 0}
          icon={Users}
          color="bg-[var(--color-info-subtle)] text-[var(--color-info)]"
          delay={0}
        />
        <StatCard
          label="Active"
          value={stats?.active ?? 0}
          icon={CheckCircle}
          color="bg-[var(--color-success-subtle)] text-[var(--color-success)]"
          delay={0.06}
        />
        <StatCard
          label="Exhausted"
          value={stats?.exhausted ?? 0}
          icon={WarningCircle}
          color="bg-[var(--color-warning-subtle)] text-[var(--color-warning)]"
          delay={0.12}
        />
        <StatCard
          label="Success Rate"
          value={`${stats?.rate ?? 0}%`}
          icon={TrendUp}
          color="bg-[var(--color-accent-subtle)] text-[var(--color-accent)]"
          delay={0.18}
        />
      </div>

      {/* Recent accounts table */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <h2 className="text-sm font-semibold text-[var(--color-text)]">Recent Accounts</h2>
          <span className="text-[12px] text-[var(--color-text-muted)]">
            {accounts.length} total
          </span>
        </div>

        {recentAccounts.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Users size={32} className="mx-auto mb-3 text-[var(--color-text-muted)] opacity-40" />
            <p className="text-sm text-[var(--color-text-muted)]">No accounts yet</p>
            <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
              Start farming to create accounts
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
                    Email
                  </th>
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
                    Name
                  </th>
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
                    Status
                  </th>
                  <th className="hidden px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)] md:table-cell">
                    Auth
                  </th>
                </tr>
              </thead>
              <tbody>
                {recentAccounts.map((acc) => (
                  <tr
                    key={acc.id}
                    className="border-b border-[var(--color-border)] last:border-0 transition-colors duration-100 hover:bg-[var(--color-bg-subtle)]"
                  >
                    <td className="px-5 py-3">
                      <span className="font-mono text-[13px] text-[var(--color-text)]">
                        {acc.email}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-[13px] text-[var(--color-text-secondary)]">
                      {acc.name}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={acc.status} />
                    </td>
                    <td className="hidden px-5 py-3 text-[12px] text-[var(--color-text-muted)] md:table-cell">
                      {acc.auth_type}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
