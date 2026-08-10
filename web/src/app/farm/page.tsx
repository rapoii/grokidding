"use client";

import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  Play,
  Stop,
  Lightning,
  ArrowClockwise,
  Trash,
} from "@phosphor-icons/react";
import { startFarm, stopFarm, getStatus, getLogs } from "@/lib/api";
import { GrokWS } from "@/lib/ws";
import type { FarmStatus } from "@/lib/types";

export default function FarmPage() {
  const [count, setCount] = useState(1);
  const [cooldown, setCooldown] = useState(5);
  const [useProxy, setUseProxy] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [parallel, setParallel] = useState(false);
  const [status, setStatus] = useState<FarmStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<GrokWS | null>(null);
  const reduce = useReducedMotion();

  // Fetch initial status
  useEffect(() => {
    const init = async () => {
      try {
        const [st, lg] = await Promise.all([getStatus(), getLogs()]);
        setStatus(st);
        setRunning(st.running);
        setLogs(lg.logs || []);
      } catch (e) {
        console.error("Failed to fetch farm status:", e);
      }
    };
    init();
  }, []);

  // WebSocket for real-time logs
  useEffect(() => {
    const ws = new GrokWS({
      onLog: (line) => {
        setLogs((prev) => [...prev.slice(-199), line]);
      },
      onProgress: (data) => {
        setStatus(data);
        setRunning(data.running);
      },
      onConnect: () => {},
      onDisconnect: () => {},
    });
    wsRef.current = ws;
    ws.connect();
    return () => ws.destroy();
  }, []);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  // Poll status when running
  useEffect(() => {
    if (!running) return;
    const interval = setInterval(async () => {
      try {
        const st = await getStatus();
        setStatus(st);
        if (!st.running) setRunning(false);
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [running]);

  const handleStart = async () => {
    try {
      await startFarm({
        count,
        proxy: useProxy,
        dry_run: dryRun,
        parallel,
        cooldown,
      });
      setRunning(true);
      setLogs([]);
    } catch (e) {
      console.error("Failed to start farm:", e);
    }
  };

  const handleStop = async () => {
    try {
      await stopFarm();
      setRunning(false);
    } catch (e) {
      console.error("Failed to stop farm:", e);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 pl-16 lg:pl-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight text-[var(--color-text)]">
            Farm
          </h1>
          <p className="mt-1 text-[14px] text-[var(--color-text-secondary)]">
            Create new Grok accounts and monitor progress.
          </p>
        </div>
      </div>

      {/* Progress banner */}
      {status?.running && (
        <motion.div
          initial={reduce ? false : { opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 rounded-2xl border border-[var(--color-accent-subtle)] bg-[var(--color-accent-subtle)] px-5 py-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-2 w-2 animate-pulse rounded-full bg-[var(--color-accent)]" />
              <p className="text-[14px] font-semibold text-[var(--color-text)]">
                {status.current_step}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[13px] text-[var(--color-text-secondary)]">
                  {status.completed}/{status.total}
                </span>
              </div>
              <span className="font-mono text-[13px] text-[var(--color-success)]">
                {status.successful} ok
              </span>
              <span className="font-mono text-[13px] text-[var(--color-error)]">
                {status.failed} fail
              </span>
            </div>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--color-bg-muted)]">
            <div
              className="h-full rounded-full bg-[var(--color-accent)] transition-all duration-500"
              style={{ width: `${status.progress}%` }}
            />
          </div>
        </motion.div>
      )}

      {/* Controls — iOS settings group */}
      <div className="mb-6 overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
        <div className="border-b border-[var(--color-border)] px-5 py-4">
          <h2 className="text-[16px] font-semibold text-[var(--color-text)]">
            Configuration
          </h2>
        </div>

        <div className="divide-y divide-[var(--color-border)]">
          {/* Count */}
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-[14px] font-medium text-[var(--color-text)]">Count</p>
              <p className="text-[12px] text-[var(--color-text-muted)]">Number of accounts to create</p>
            </div>
            <input
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(parseInt(e.target.value) || 1)}
              disabled={running}
              className="w-20 rounded-[10px] border border-[var(--color-border-strong)] bg-[var(--color-bg-subtle)] px-3 py-2 text-right font-mono text-[14px] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none disabled:opacity-50"
            />
          </div>

          {/* Cooldown */}
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-[14px] font-medium text-[var(--color-text)]">Cooldown</p>
              <p className="text-[12px] text-[var(--color-text-muted)]">Seconds between attempts</p>
            </div>
            <input
              type="number"
              min={0}
              max={120}
              value={cooldown}
              onChange={(e) => setCooldown(parseInt(e.target.value) || 0)}
              disabled={running}
              className="w-20 rounded-[10px] border border-[var(--color-border-strong)] bg-[var(--color-bg-subtle)] px-3 py-2 text-right font-mono text-[14px] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none disabled:opacity-50"
            />
          </div>

          {/* Toggles */}
          <ToggleRow
            label="Parallel"
            description="Run multiple accounts simultaneously"
            value={parallel}
            onChange={setParallel}
            disabled={running}
          />
          <ToggleRow
            label="Proxy"
            description="Route traffic through proxy pool"
            value={useProxy}
            onChange={setUseProxy}
            disabled={running}
          />
          <ToggleRow
            label="Dry Run"
            description="Test without creating real accounts"
            value={dryRun}
            onChange={setDryRun}
            disabled={running}
          />
        </div>

        {/* Action button */}
        <div className="border-t border-[var(--color-border)] px-5 py-4">
          {!running ? (
            <button
              onClick={handleStart}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-[var(--color-accent)] px-4 py-3 text-[15px] font-semibold text-[var(--color-on-accent)] transition-all hover:bg-[var(--color-accent-hover)] active:scale-[0.98]"
            >
              <Play size={18} weight="fill" />
              Start Farm
            </button>
          ) : (
            <button
              onClick={handleStop}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-[var(--color-error)] px-4 py-3 text-[15px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
            >
              <Stop size={18} weight="fill" />
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Logs — glass panel */}
      <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div className="flex items-center gap-2">
            <h2 className="text-[16px] font-semibold text-[var(--color-text)]">Logs</h2>
            <div
              className={`h-2 w-2 rounded-full ${running ? "animate-pulse bg-[var(--color-success)]" : "bg-[var(--color-text-muted)]"}`}
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setLogs([])}
              className="flex h-8 w-8 items-center justify-center rounded-full text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-muted)] hover:text-[var(--color-text)]"
              title="Clear logs"
            >
              <Trash size={16} />
            </button>
          </div>
        </div>

        <div
          ref={logRef}
          className="h-80 overflow-y-auto px-5 py-3 font-mono text-[12px] leading-relaxed"
        >
          {logs.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <Lightning size={32} weight="duotone" className="mb-2 text-[var(--color-text-muted)]" />
              <p className="text-[14px] text-[var(--color-text-muted)]">No logs yet</p>
              <p className="text-[12px] text-[var(--color-text-muted)]">Start farming to see real-time logs</p>
            </div>
          ) : (
            logs.map((line, i) => (
              <motion.div
                key={i}
                initial={reduce ? false : { opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                className={`py-0.5 ${
                  line.includes("ERROR")
                    ? "text-[var(--color-error)]"
                    : line.includes("SUCCESS")
                      ? "text-[var(--color-success)]"
                      : "text-[var(--color-text-secondary)]"
                }`}
              >
                {line}
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  description,
  value,
  onChange,
  disabled,
}: {
  label: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-5 py-4">
      <div>
        <p className="text-[14px] font-medium text-[var(--color-text)]">{label}</p>
        <p className="text-[12px] text-[var(--color-text-muted)]">{description}</p>
      </div>
      <button
        className={`ios-toggle ${disabled ? "opacity-50" : ""}`}
        data-on={value}
        onClick={() => !disabled && onChange(!value)}
        disabled={disabled}
        role="switch"
        aria-checked={value}
      >
        <span className="sr-only">{label}</span>
      </button>
    </div>
  );
}
