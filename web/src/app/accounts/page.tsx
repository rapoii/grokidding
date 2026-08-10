"use client";

import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  MagnifyingGlass,
  Trash,
  ArrowClockwise,
  Users,
} from "@phosphor-icons/react";
import { getAccounts, deleteAccount, checkQuota } from "@/lib/api";
import type { Account, QuotaData } from "@/lib/types";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [quota, setQuota] = useState<QuotaData | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const reduce = useReducedMotion();

  const fetchAccounts = async () => {
    try {
      const data = await getAccounts();
      setAccounts(data);
    } catch (e) {
      console.error("Failed to fetch accounts:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const filtered = useMemo(() => {
    if (!search) return accounts;
    const q = search.toLowerCase();
    return accounts.filter(
      (a) =>
        a.email?.toLowerCase().includes(q) ||
        a.name?.toLowerCase().includes(q),
    );
  }, [accounts, search]);

  const handleDelete = async (id: string) => {
    try {
      await deleteAccount(id);
      setAccounts((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      console.error("Failed to delete account:", e);
    }
  };

  const handleQuotaCheck = async () => {
    setQuotaLoading(true);
    try {
      const data = await checkQuota();
      setQuota(data);
    } catch (e) {
      console.error("Quota check failed:", e);
    } finally {
      setQuotaLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-5 pt-14 lg:px-8 lg:pt-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight text-[var(--color-text)]">
            Accounts
          </h1>
          <p className="mt-1 text-[14px] text-[var(--color-text-secondary)]">
            Manage your Grok accounts and check quotas.
          </p>
        </div>
        <button
          onClick={handleQuotaCheck}
          disabled={quotaLoading}
          className="flex items-center gap-2 rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] px-4 py-2 text-[13px] font-medium text-[var(--color-text-secondary)] transition-all hover:bg-[var(--color-bg-muted)] active:scale-[0.98] disabled:opacity-50"
        >
          <ArrowClockwise size={16} className={quotaLoading ? "animate-spin" : ""} />
          Check Quota
        </button>
      </div>

      {/* Status summary chips */}
      <div className="mb-6 flex flex-wrap gap-2">
        <StatusChip
          label="Total"
          value={accounts.length}
          color="text-[var(--color-accent)]"
        />
        <StatusChip
          label="Active"
          value={accounts.filter((a) => a.status === "active").length}
          color="text-[var(--color-success)]"
        />
        <StatusChip
          label="Exhausted"
          value={accounts.filter((a) => a.status === "exhausted").length}
          color="text-[var(--color-warning)]"
        />
        <StatusChip
          label="Error"
          value={accounts.filter((a) => a.status === "error").length}
          color="text-[var(--color-error)]"
        />
      </div>

      {/* Quota panel */}
      <AnimatePresence>
        {quota && (
          <motion.div
            initial={reduce ? false : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 overflow-hidden rounded-2xl border border-[var(--color-accent-subtle)] bg-[var(--color-accent-subtle)] p-5"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-semibold text-[var(--color-text)]">Quota Summary</p>
                <p className="mt-1 font-mono text-[13px] text-[var(--color-text-secondary)]">
                  {quota.total_remaining} / {quota.total_limit} remaining
                </p>
              </div>
              <div className="text-right">
                <p className="text-[11px] text-[var(--color-text-muted)]">Total Used</p>
                <p className="font-mono text-[20px] font-bold text-[var(--color-text)]">
                  {quota.total_used}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search */}
      <div className="mb-4 relative">
        <MagnifyingGlass
          size={18}
          className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
        />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by email or name"
          className="w-full rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] py-2.5 pl-11 pr-4 text-[14px] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
        />
      </div>

      {/* Accounts list — iOS table */}
      <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <h2 className="text-[16px] font-semibold text-[var(--color-text)]">
            All Accounts
          </h2>
          <span className="font-mono text-[13px] text-[var(--color-text-muted)]">
            {filtered.length} shown
          </span>
        </div>

        {loading ? (
          <div className="p-5">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="skeleton mb-3 h-14 rounded-xl" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Users size={32} weight="duotone" className="mb-2 text-[var(--color-text-muted)]" />
            <p className="text-[14px] text-[var(--color-text-muted)]">No accounts found</p>
          </div>
        ) : (
          <div className="max-h-[600px] overflow-y-auto">
            {filtered.map((account, i) => (
              <motion.div
                key={account.id}
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.02 }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-center gap-4 border-b border-[var(--color-border)] px-5 py-3 transition-colors last:border-0 hover:bg-[var(--color-bg-subtle)]"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-medium text-[var(--color-text)]">
                    {account.name}
                  </p>
                  <p className="truncate font-mono text-[12px] text-[var(--color-text-muted)]">
                    {account.email || "?"}
                  </p>
                </div>
                <StatusBadge status={account.status} />
                <button
                  onClick={() => handleDelete(account.id)}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-error-subtle)] hover:text-[var(--color-error)]"
                  title="Delete account"
                >
                  <Trash size={16} />
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusChip({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1.5">
      <span className="text-[12px] text-[var(--color-text-muted)]">{label}</span>
      <span className={`font-mono text-[14px] font-bold ${color}`}>{value}</span>
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
