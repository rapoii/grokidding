"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  MagnifyingGlass,
  Trash,
  ArrowClockwise,
  Users,
  CheckCircle,
  WarningCircle,
  XCircle,
  Clock,
} from "@phosphor-icons/react";
import { getAccounts, deleteAccount, checkQuota } from "@/lib/api";
import type { Account, QuotaData } from "@/lib/types";
import clsx from "clsx";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; text: string; icon: React.ElementType; label: string }> = {
    active: { bg: "bg-[var(--color-success-subtle)]", text: "text-[var(--color-success)]", icon: CheckCircle, label: "Active" },
    exhausted: { bg: "bg-[var(--color-warning-subtle)]", text: "text-[var(--color-warning)]", icon: WarningCircle, label: "Exhausted" },
    error: { bg: "bg-[var(--color-error-subtle)]", text: "text-[var(--color-error)]", icon: XCircle, label: "Error" },
    unavailable: { bg: "bg-[var(--color-bg-muted)]", text: "text-[var(--color-text-muted)]", icon: Clock, label: "N/A" },
    unknown: { bg: "bg-[var(--color-bg-muted)]", text: "text-[var(--color-text-muted)]", icon: Clock, label: "Unknown" },
    no_token: { bg: "bg-[var(--color-bg-muted)]", text: "text-[var(--color-text-muted)]", icon: Clock, label: "No Token" },
  };
  const s = map[status] || map.unknown;
  const Icon = s.icon;
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-[var(--radius-full)] px-2 py-0.5 text-[11px] font-medium", s.bg, s.text)}>
      <Icon size={12} />
      {s.label}
    </span>
  );
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [quotaData, setQuotaData] = useState<QuotaData | null>(null);
  const [checkingQuota, setCheckingQuota] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getAccounts();
      setAccounts(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCheckQuota = useCallback(async () => {
    setCheckingQuota(true);
    try {
      const data = await checkQuota();
      setQuotaData(data);
    } catch {
      // silent
    } finally {
      setCheckingQuota(false);
    }
  }, []);

  const handleDelete = useCallback(async (id: string) => {
    setDeleting(id);
    try {
      await deleteAccount(id);
      setAccounts((prev) => prev.filter((a) => a.id !== id));
      setConfirmDelete(null);
    } catch {
      // silent
    } finally {
      setDeleting(null);
    }
  }, []);

  const filtered = accounts.filter(
    (a) =>
      a.email.toLowerCase().includes(search.toLowerCase()) ||
      a.name.toLowerCase().includes(search.toLowerCase())
  );

  const statusCounts = accounts.reduce(
    (acc, a) => {
      acc[a.status] = (acc[a.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 pl-16 lg:px-8 lg:pl-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text)]">Accounts</h1>
          <p className="mt-0.5 text-sm text-[var(--color-text-muted)]">
            Manage your Grok accounts in 9Router
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCheckQuota}
            disabled={checkingQuota}
            className="flex items-center gap-2 rounded-[var(--radius-full)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-sm text-[var(--color-text-secondary)] shadow-[var(--shadow-sm)] transition-all duration-150 hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] disabled:opacity-50 cursor-pointer"
          >
            <ArrowClockwise size={14} className={checkingQuota ? "animate-spin" : ""} />
            Check Quota
          </button>
          <button
            onClick={refresh}
            className="flex items-center gap-2 rounded-[var(--radius-full)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-sm text-[var(--color-text-secondary)] shadow-[var(--shadow-sm)] transition-all duration-150 hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] cursor-pointer"
          >
            <ArrowClockwise size={14} />
            Refresh
          </button>
        </div>
      </div>

      {/* Status summary chips */}
      <div className="mb-4 flex flex-wrap gap-2">
        {Object.entries(statusCounts).map(([status, count]) => (
          <span
            key={status}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-full)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-1 text-[12px]"
          >
            <StatusBadge status={status} />
            <span className="font-medium text-[var(--color-text)]">{count}</span>
          </span>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
        <input
          type="text"
          placeholder="Search by email or name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] py-2.5 pl-9 pr-4 text-sm text-[var(--color-text)] transition-colors placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
        />
      </div>

      {/* Quota summary */}
      <AnimatePresence>
        {quotaData && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 overflow-hidden"
          >
            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)]">Total Tokens</p>
                  <p className="text-lg font-semibold text-[var(--color-text)]">
                    {(quotaData.total_limit / 1_000_000).toFixed(1)}M
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)]">Remaining</p>
                  <p className="text-lg font-semibold text-[var(--color-success)]">
                    {(quotaData.total_remaining / 1_000_000).toFixed(1)}M
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)]">Used</p>
                  <p className="text-lg font-semibold text-[var(--color-warning)]">
                    {(quotaData.total_used / 1_000_000).toFixed(1)}M
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-[var(--color-text-muted)]">Accounts Checked</p>
                  <p className="text-lg font-semibold text-[var(--color-text)]">
                    {quotaData.total_accounts}
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Accounts table */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <ArrowClockwise size={20} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Users size={32} className="mb-3 text-[var(--color-text-muted)] opacity-30" />
            <p className="text-sm text-[var(--color-text-muted)]">
              {search ? "No accounts match your search" : "No accounts found"}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Email</th>
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Name</th>
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Status</th>
                  <th className="hidden px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)] md:table-cell">Auth</th>
                  <th className="hidden px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)] lg:table-cell">Created</th>
                  <th className="px-5 py-3 text-right text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((acc) => (
                  <motion.tr
                    key={acc.id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="border-b border-[var(--color-border)] last:border-0 transition-colors duration-100 hover:bg-[var(--color-bg-subtle)]"
                  >
                    <td className="px-5 py-3">
                      <span className="font-mono text-[13px] text-[var(--color-text)]">{acc.email}</span>
                    </td>
                    <td className="px-5 py-3 text-[13px] text-[var(--color-text-secondary)]">{acc.name}</td>
                    <td className="px-5 py-3"><StatusBadge status={acc.status} /></td>
                    <td className="hidden px-5 py-3 text-[12px] text-[var(--color-text-muted)] md:table-cell">{acc.auth_type}</td>
                    <td className="hidden px-5 py-3 text-[12px] text-[var(--color-text-muted)] lg:table-cell">
                      {acc.created_at ? new Date(acc.created_at).toLocaleDateString() : "-"}
                    </td>
                    <td className="px-5 py-3 text-right">
                      {confirmDelete === acc.id ? (
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleDelete(acc.id)}
                            disabled={deleting === acc.id}
                            className="rounded-[var(--radius-sm)] bg-[var(--color-error)] px-2 py-1 text-[11px] font-medium text-white transition-opacity hover:opacity-90 cursor-pointer"
                          >
                            {deleting === acc.id ? "..." : "Confirm"}
                          </button>
                          <button
                            onClick={() => setConfirmDelete(null)}
                            className="rounded-[var(--radius-sm)] px-2 py-1 text-[11px] text-[var(--color-text-muted)] hover:bg-[var(--color-bg-subtle)] cursor-pointer"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDelete(acc.id)}
                          className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-error-subtle)] hover:text-[var(--color-error)] cursor-pointer"
                          title="Delete account"
                        >
                          <Trash size={14} />
                        </button>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
