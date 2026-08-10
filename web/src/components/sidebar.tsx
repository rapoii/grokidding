"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  House,
  Lightning,
  Users,
  Gear,
  List,
  X,
  Sun,
  Moon,
  CircleHalf,
} from "@phosphor-icons/react";
import { useTheme } from "@/lib/theme-provider";

const navItems = [
  { href: "/", label: "Dashboard", icon: House },
  { href: "/farm", label: "Farm", icon: Lightning },
  { href: "/accounts", label: "Accounts", icon: Users },
  { href: "/settings", label: "Settings", icon: Gear },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, resolved, setTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const reduce = useReducedMotion();

  const ThemeIcon =
    theme === "light" ? Sun : theme === "dark" ? Moon : CircleHalf;

  const cycleTheme = () => {
    const order = ["light", "dark", "system"] as const;
    const idx = order.indexOf(theme);
    setTheme(order[(idx + 1) % order.length]);
  };

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  return (
    <>
      {/* Mobile hamburger — floating glass */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed left-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-full glass lg:hidden"
        aria-label="Open menu"
      >
        <List size={20} weight="bold" />
      </button>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={reduce ? { opacity: 0 } : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMobileOpen(false)}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {mobileOpen ? (
          <motion.aside
            initial={reduce ? { opacity: 0 } : { x: -280 }}
            animate={{ x: 0, opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { x: -280 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed left-0 top-0 z-50 flex h-[100dvh] w-[260px] flex-col glass-panel lg:hidden"
          >
            <SidebarContent
              pathname={pathname}
              theme={theme}
              resolved={resolved}
              ThemeIcon={ThemeIcon}
              cycleTheme={cycleTheme}
              onClose={() => setMobileOpen(false)}
            />
          </motion.aside>
        ) : null}
      </AnimatePresence>

      {/* Desktop sidebar — persistent, never on mobile */}
      <aside className="sticky top-0 hidden h-[100dvh] w-[240px] shrink-0 flex-col glass-panel lg:flex">
        <SidebarContent
          pathname={pathname}
          theme={theme}
          resolved={resolved}
          ThemeIcon={ThemeIcon}
          cycleTheme={cycleTheme}
        />
      </aside>
    </>
  );
}

function SidebarContent({
  pathname,
  theme,
  resolved,
  ThemeIcon,
  cycleTheme,
  onClose,
}: {
  pathname: string;
  theme: "light" | "dark" | "system";
  resolved: "light" | "dark";
  ThemeIcon: typeof Sun;
  cycleTheme: () => void;
  onClose?: () => void;
}) {
  return (
    <>
      {/* Brand header */}
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[var(--color-accent)] shadow-md">
          <Lightning size={18} weight="fill" className="text-[var(--color-on-accent)]" />
        </div>
        <div className="min-w-0">
          <p className="text-[15px] font-semibold tracking-tight text-[var(--color-text)]">
            Grokidding
          </p>
          <p className="text-[11px] text-[var(--color-text-muted)]">
            Account Farmer
          </p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-full hover:bg-[var(--color-bg-muted)] lg:hidden"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2">
        <p className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
          Navigation
        </p>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[14px] font-medium transition-all duration-200 ${
                    active
                      ? "bg-[var(--color-accent-subtle)] text-[var(--color-accent)]"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-muted)] hover:text-[var(--color-text)]"
                  }`}
                >
                  <Icon size={18} weight={active ? "fill" : "regular"} />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer — theme toggle */}
      <div className="border-t border-[var(--color-border)] px-3 py-3">
        <button
          onClick={cycleTheme}
          className="flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-[14px] font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-muted)] hover:text-[var(--color-text)]"
        >
          <ThemeIcon size={18} className="shrink-0" />
          <span className="capitalize">{theme}</span>
        </button>
      </div>
    </>
  );
}
