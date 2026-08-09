"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import clsx from "clsx";
import {
  House,
  Lightning,
  Users,
  Gear,
  List,
  X,
  Sun,
  Moon,
  Monitor,
} from "@phosphor-icons/react";
import { useTheme } from "@/lib/theme-provider";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: House },
  { href: "/farm", label: "Farm", icon: Lightning },
  { href: "/accounts", label: "Accounts", icon: Users },
  { href: "/settings", label: "Settings", icon: Gear },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { theme, resolved, setTheme } = useTheme();

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  const cycleTheme = useCallback(() => {
    const order: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];
    const idx = order.indexOf(theme);
    setTheme(order[(idx + 1) % order.length]);
  }, [theme, setTheme]);

  const ThemeIcon = theme === "system" ? Monitor : resolved === "dark" ? Moon : Sun;

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed left-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-md)] border border-[var(--color-border)] lg:hidden cursor-pointer"
        aria-label="Open menu"
      >
        <List size={20} className="text-[var(--color-text)]" />
      </button>

      {/* Mobile overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm lg:hidden"
            onClick={closeMobile}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <AnimatePresence>
        {(mobileOpen || true) && (
          <motion.aside
            className={clsx(
              "fixed left-0 top-0 z-50 flex h-[100dvh] w-64 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-elevated)]",
              "lg:translate-x-0 lg:static lg:z-auto",
              !mobileOpen && "max-lg:-translate-x-full"
            )}
            initial={false}
            animate={{ x: mobileOpen ? 0 : undefined }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            {/* Brand */}
            <div className="flex items-center justify-between px-5 py-5">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-accent)]">
                  <Lightning size={18} weight="fill" className="text-white" />
                </div>
                <div>
                  <h1 className="text-sm font-semibold text-[var(--color-text)] leading-tight">
                    Grokidding
                  </h1>
                  <p className="text-[11px] text-[var(--color-text-muted)]">
                    Account Farmer
                  </p>
                </div>
              </div>
              <button
                onClick={closeMobile}
                className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] hover:bg-[var(--color-bg-subtle)] lg:hidden cursor-pointer"
                aria-label="Close menu"
              >
                <X size={16} className="text-[var(--color-text-muted)]" />
              </button>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-3 py-2">
              <div className="mb-2 px-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
                  Navigation
                </span>
              </div>
              <ul className="space-y-0.5">
                {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
                  const active = pathname === href || (href !== "/" && pathname.startsWith(href));
                  return (
                    <li key={href}>
                      <Link
                        href={href}
                        onClick={closeMobile}
                        className={clsx(
                          "group flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2.5 text-sm font-medium transition-all duration-150",
                          active
                            ? "bg-[var(--color-accent-subtle)] text-[var(--color-accent)]"
                            : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-text)]"
                        )}
                      >
                        <Icon
                          size={18}
                          weight={active ? "fill" : "regular"}
                          className={clsx(
                            "shrink-0 transition-colors duration-150",
                            active ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)] group-hover:text-[var(--color-text-secondary)]"
                          )}
                        />
                        {label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>

            {/* Footer */}
            <div className="border-t border-[var(--color-border)] px-3 py-3">
              <button
                onClick={cycleTheme}
                className="flex w-full items-center gap-3 rounded-[var(--radius-md)] px-3 py-2.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-subtle)] transition-colors duration-150 cursor-pointer"
              >
                <ThemeIcon size={18} className="shrink-0" />
                <span className="capitalize">{theme}</span>
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
