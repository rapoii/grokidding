"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Play,
  Stop,
  Lightning,
  ArrowClockwise,
  Trash,
  Download,
  ArrowsOut,
} from "@phosphor-icons/react";
import { startFarm, stopFarm, getStatus } from "@/lib/api";
import { GrokWS } from "@/lib/ws";
import type { FarmStatus } from "@/lib/types";
import clsx from "clsx";

function LogLine({ line, index }: { line: string; index: number }) {
  const isError = /error|fail|crash|exception/i.test(line);
  const isSuccess = /success|ok|complete|token|saved/i.test(line);
  const isWarning = /warn|skip|cooldown|expired/i.test(line);

  let color = "text-[var(--color-text-secondary)]";
  if (isError) color = "text-[var(--color-error)]";
  else if (isSuccess) color = "text-[var(--color-success)]";
  else if (isWarning) color = "text-[var(--color-warning)]";

  return (
    <motion.div
      initial={{ opacity: 0, x: -4 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.15, delay: Math.min(index * 0.01, 0.3) }}
      className={clsx("font-mono text-[12px] leading-relaxed", color)}
    >
      {line}
    </motion.div>
  );
}

export default function FarmPage() {
  const [farm, setFarm] = useState<FarmStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [count, setCount] = useState(1);
  const [parallel, setParallel] = useState(false);
  const [useProxy, setUseProxy] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [cooldown, setCooldown] = useState(5);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<GrokWS | null>(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  // WebSocket connection
  useEffect(() => {
    const ws = new GrokWS({
      onConnect: () => setConnected(true),
      onDisconnect: () => setConnected(false),
      onLog: (line) => setLogs((prev) => [...prev.slice(-499), line]),
      onProgress: (data) => setFarm(data),
    });
    wsRef.current = ws;
    ws.connect();

    // Initial fetch
    getStatus().then(setFarm).catch(() => {});

    return () => ws.destroy();
  }, []);

  const handleStart = useCallback(async () => {
    try {
      setLogs([]);
      await startFarm({ count, parallel, proxy: useProxy, dry_run: dryRun, cooldown });
    } catch (e) {
      setLogs((prev) => [...prev, `[ERROR] ${e instanceof Error ? e.message : String(e)}`]);
    }
  }, [count, parallel, useProxy, dryRun, cooldown]);

  const handleStop = useCallback(async () => {
    try {
      await stopFarm();
    } catch (e) {
      setLogs((prev) => [...prev, `[ERROR] ${e instanceof Error ? e.message : String(e)}`]);
    }
  }, []);

  const handleExport = useCallback(() => {
    const blob = new Blob([logs.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `grokidding-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [logs]);

  const isRunning = farm?.running ?? false;

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 pl-16 lg:px-8 lg:pl-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-[var(--color-text)]">Farm</h1>
        <p className="mt-0.5 text-sm text-[var(--color-text-muted)]">
          Create new Grok accounts and monitor progress
        </p>
      </div>

      {/* Controls */}
      <div className="mb-6 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5 shadow-[var(--shadow-sm)]">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {/* Count */}
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[var(--color-text-muted)]">
              Count
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              disabled={isRunning}
              className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] transition-colors focus:border-[var(--color-accent)] focus:outline-none disabled:opacity-50"
            />
          </div>

          {/* Cooldown */}
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[var(--color-text-muted)]">
              Cooldown (s)
            </label>
            <input
              type="number"
              min={0}
              max={60}
              value={cooldown}
              onChange={(e) => setCooldown(Number(e.target.value))}
              disabled={isRunning}
              className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] transition-colors focus:border-[var(--color-accent)] focus:outline-none disabled:opacity-50"
            />
          </div>

          {/* Toggles */}
          <div className="flex flex-col gap-2">
            <label className="text-[12px] font-medium text-[var(--color-text-muted)]">Options</label>
            <Toggle label="Parallel" checked={parallel} onChange={setParallel} disabled={isRunning} />
            <Toggle label="Proxy" checked={useProxy} onChange={setUseProxy} disabled={isRunning} />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[12px] font-medium text-[var(--color-text-muted)]">Mode</label>
            <Toggle label="Dry Run" checked={dryRun} onChange={setDryRun} disabled={isRunning} />
          </div>

          {/* Action */}
          <div className="flex items-end">
            {isRunning ? (
              <button
                onClick={handleStop}
                className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-md)] bg-[var(--color-error)] px-4 py-2.5 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-all duration-150 hover:opacity-90 active:scale-[0.98] cursor-pointer"
              >
                <Stop size={16} weight="fill" />
                Stop
              </button>
            ) : (
              <button
                onClick={handleStart}
                className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-md)] bg-[var(--color-accent)] px-4 py-2.5 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-all duration-150 hover:bg-[var(--color-accent-hover)] active:scale-[0.98] cursor-pointer"
              >
                <Play size={16} weight="fill" />
                Start Farm
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress */}
      <AnimatePresence>
        {isRunning && farm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 overflow-hidden"
          >
            <div className="rounded-[var(--radius-lg)] border border-[var(--color-accent-muted)] bg-[var(--color-accent-subtle)] p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Lightning size={18} weight="fill" className="text-[var(--color-accent)] animate-pulse" />
                  <span className="text-sm font-medium text-[var(--color-accent-hover)]">
                    {farm.current_step}
                  </span>
                  {farm.current_email && (
                    <span className="font-mono text-[12px] text-[var(--color-text-muted)]">
                      {farm.current_email}
                    </span>
                  )}
                </div>
                <span className="font-mono text-sm text-[var(--color-accent)]">
                  {farm.completed}/{farm.total}
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-[var(--color-accent-muted)] overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-[var(--color-accent)]"
                  animate={{ width: `${farm.progress}%` }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>
              <div className="mt-2 flex gap-4 text-[12px]">
                <span className="text-[var(--color-success)]">{farm.successful} successful</span>
                <span className="text-[var(--color-error)]">{farm.failed} failed</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Logs */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-[var(--color-text)]">Logs</h2>
            <div
              className={clsx(
                "h-2 w-2 rounded-full",
                connected ? "bg-[var(--color-success)]" : "bg-[var(--color-text-muted)]"
              )}
              title={connected ? "WebSocket connected" : "Disconnected"}
            />
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleExport}
              disabled={logs.length === 0}
              className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-text)] disabled:opacity-30 cursor-pointer"
              title="Export logs"
            >
              <Download size={14} />
            </button>
            <button
              onClick={() => setLogs([])}
              disabled={logs.length === 0}
              className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-text)] disabled:opacity-30 cursor-pointer"
              title="Clear logs"
            >
              <Trash size={14} />
            </button>
          </div>
        </div>

        <div
          ref={logContainerRef}
          className="max-h-[50vh] min-h-[200px] overflow-y-auto px-5 py-3"
        >
          {logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <ArrowsOut size={28} className="mb-2 text-[var(--color-text-muted)] opacity-30" />
              <p className="text-sm text-[var(--color-text-muted)]">No logs yet</p>
              <p className="text-[12px] text-[var(--color-text-muted)]">
                Start farming to see real-time logs
              </p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {logs.map((line, i) => (
                <LogLine key={`${i}-${line.slice(0, 20)}`} line={line} index={i} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className={clsx("flex items-center gap-2 text-[13px] cursor-pointer", disabled && "opacity-50 pointer-events-none")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx(
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200 cursor-pointer",
          checked ? "bg-[var(--color-accent)]" : "bg-[var(--color-bg-muted)]"
        )}
      >
        <span
          className={clsx(
            "inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform duration-200",
            checked ? "translate-x-[18px]" : "translate-x-[3px]"
          )}
        />
      </button>
      <span className="text-[var(--color-text-secondary)]">{label}</span>
    </label>
  );
}
