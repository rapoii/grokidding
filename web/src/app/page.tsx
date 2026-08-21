"use client";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { FarmControlPanel } from "@/components/features/farm-control-panel";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { useWebSocket } from "@/hooks/use-websocket";
import { useStats } from "@/hooks/use-api";
import { useState } from "react";
import { 
  Users, 
  Activity, 
  AlertTriangle, 
  Zap,
  Server,
  ArrowUpRight,
  Play,
  Pause
} from "lucide-react";
import * as api from "@/lib/api-client";

export default function DashboardPage() {
  const { data: stats, mutate: mutateStats } = useStats();
  const [isStartingAll, setIsStartingAll] = useState(false);
  const [isStoppingAll, setIsStoppingAll] = useState(false);
  const { status: wsStatus } = useWebSocket({
    onMessage: (msg) => {
      if (msg.type === 'progress' || msg.type === 'status_change') {
        mutateStats();
      }
    }
  });

  const handleStartAll = async () => {
    setIsStartingAll(true);
    try {
      await api.startAllAccounts();
      mutateStats();
    } catch (error) {
      console.error("Failed to start all accounts:", error);
    } finally {
      setIsStartingAll(false);
    }
  };

  const handleStopAll = async () => {
    setIsStoppingAll(true);
    try {
      await api.stopAllAccounts();
      mutateStats();
    } catch (error) {
      console.error("Failed to stop all accounts:", error);
    } finally {
      setIsStoppingAll(false);
    }
  };
  return (
    <DashboardShell>
      {/* Header Section */}
      <header className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight text-[var(--text-primary)] leading-none mb-1">
            Dashboard
          </h1>
          <p className="text-[15px] text-[var(--text-secondary)]">
            System overview and real-time farm monitoring
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full glass-subtle text-xs font-medium text-[var(--status-success)]">
            <span className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-[var(--status-success)] animate-pulse' : wsStatus === 'connecting' ? 'bg-[var(--status-warning)] animate-pulse' : 'bg-[var(--status-error)]'}`} />
            {wsStatus === 'connected' ? 'System Operational' : wsStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
          </div>
          <Button leftIcon={<Play className="w-4 h-4" />} size="sm" onClick={handleStartAll} disabled={isStartingAll}>
            {isStartingAll ? 'Starting...' : 'Start All'}
          </Button>
          <Button variant="secondary" leftIcon={<Pause className="w-4 h-4" />} size="sm" onClick={handleStopAll} disabled={isStoppingAll}>
            {isStoppingAll ? 'Stopping...' : 'Stop All'}
          </Button>
        </div>
      </header>

      {/* Stats Grid */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard 
          title="Total Accounts" 
          value={stats?.totalAccounts.toLocaleString() || "0"} 
          icon={Users}
          color="var(--accent-blue)"
        />
        <StatCard 
          title="Active Sessions" 
          value={stats?.activeSessions.toLocaleString() || "0"} 
          subtitle="currently farming"
          icon={Activity}
          color="var(--status-success)"
        />
        <StatCard 
          title="Exhausted Today" 
          value={stats?.exhaustedToday.toLocaleString() || "0"} 
          icon={AlertTriangle}
          color="var(--status-warning)"
        />
        <StatCard 
          title="Avg. Response Time" 
          value={stats?.avgResponseTime ? `${stats.avgResponseTime}ms` : "0ms"} 
          icon={Zap}
          color="var(--accent-indigo)"
        />
      </section>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Activity & Quota */}
        <div className="lg:col-span-2 space-y-6">
          {/* Farm Control Panel */}
          <FarmControlPanel 
            isRunning={stats?.activeSessions ? stats.activeSessions > 0 : false} 
            activeCount={stats?.activeSessions || 0}
            totalCount={stats?.totalAccounts || 0}
            onStart={handleStartAll}
            onStop={handleStopAll}
          />
          
          {/* Live Activity Chart Placeholder */}
          <GlassCard padding="none" className="overflow-hidden">
            <div className="p-5 border-b border-[var(--glass-border)] flex items-center justify-between">
              <h3 className="font-semibold text-[var(--text-primary)]">Live Request Volume</h3>
              <div className="flex gap-2">
                {["1H", "6H", "24H", "7D"].map((t) => (
                  <button key={t} className="px-2 py-1 text-xs font-medium rounded hover:bg-white/5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div className="h-64 w-full bg-gradient-to-b from-transparent to-[var(--accent-blue)]/5 flex items-end px-4 pb-4 relative">
              {/* Simulated Chart Bars */}
              <div className="flex items-end justify-between w-full h-full gap-1 opacity-80">
                {Array.from({ length: 40 }).map((_, i) => {
                  const height = Math.max(10, (i * 7 + 13) % 90); // deterministic pseudo-random height
                  return (
                    <div 
                      key={i} 
                      className="flex-1 bg-[var(--accent-blue)]/40 hover:bg-[var(--accent-blue)]/70 transition-all duration-300 rounded-t-sm"
                      style={{ height: `${height}%` }}
                    />
                  );
                })}
              </div>
              <div className="absolute top-4 right-4 glass-subtle px-3 py-1.5 rounded-lg text-xs font-mono text-[var(--text-secondary)]">
                12.4k req/min
              </div>
            </div>
          </GlassCard>

          {/* Recent Accounts Table Preview */}
          <GlassCard padding="none" className="overflow-hidden">
            <div className="p-5 border-b border-[var(--glass-border)] flex items-center justify-between">
              <h3 className="font-semibold text-[var(--text-primary)]">Recent Account Activity</h3>
              <Button variant="ghost" size="sm" rightIcon={<ArrowUpRight className="w-3 h-3" />}>
                View All
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-black/5 dark:bg-white/5 text-[var(--text-secondary)] uppercase text-xs tracking-wider">
                  <tr>
                    <th className="px-5 py-3 font-medium">Account</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Last Action</th>
                    <th className="px-5 py-3 font-medium text-right">Requests</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--glass-border)]">
                  {[
                    { email: "user_alpha@proton.me", status: "running", action: "Farming active", reqs: "1,240" },
                    { email: "dev_test_02@gmail.com", status: "cooldown", action: "Rate limited", reqs: "856" },
                    { email: "worker_node_7@outlook.com", status: "success", action: "Completed batch", reqs: "3,412" },
                    { email: "backup_acct_x@tempmail.net", status: "error", action: "Auth failed", reqs: "0" },
                    { email: "main_ops_lead@company.io", status: "stopped", action: "Manual pause", reqs: "12,890" },
                  ].map((row, i) => (
                    <tr key={i} className="hover:bg-white/[0.02] transition-colors group cursor-pointer">
                      <td className="px-5 py-3 font-medium text-[var(--text-primary)]">{row.email}</td>
                      <td className="px-5 py-3">
                        <StatusBadge status={row.status as "running" | "cooldown" | "success" | "error" | "stopped"} />
                      </td>
                      <td className="px-5 py-3 text-[var(--text-secondary)]">{row.action}</td>
                      <td className="px-5 py-3 text-right font-mono text-[var(--text-secondary)]">{row.reqs}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </div>

        {/* Right Column - System & Quick Actions */}
        <div className="space-y-6">
          {/* System Health Widget */}
          <GlassCard>
            <div className="flex items-center gap-3 mb-4">
              <Server className="w-5 h-5 text-[var(--accent-blue)]" />
              <h3 className="font-semibold text-[var(--text-primary)]">System Health</h3>
            </div>
            
            <div className="space-y-4">
              <HealthRow label="WebSocket Connection" status={wsStatus === 'connected' ? 'connected' : wsStatus === 'connecting' ? 'warning' : 'error'} />
              <HealthRow label="Database Latency" value={stats?.dbLatency ? `${stats.dbLatency}ms` : "—"} status={!stats ? undefined : stats.dbLatency < 50 ? 'good' : stats.dbLatency < 200 ? 'warning' : 'error'} />
              <HealthRow label="Memory Usage" value={stats?.memoryUsage ? `${stats.memoryUsage}%` : "—"} status={!stats ? undefined : stats.memoryUsage < 70 ? 'good' : stats.memoryUsage < 90 ? 'warning' : 'error'} />
              <HealthRow label="Uptime" value={stats?.uptime || "—"} />
            </div>
          </GlassCard>

          {/* Quick Actions */}
          <GlassCard>
            <h3 className="font-semibold text-[var(--text-primary)] mb-4">Quick Actions</h3>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" size="sm" className="justify-start">Import Proxies</Button>
              <Button variant="secondary" size="sm" className="justify-start">Export Logs</Button>
              <Button variant="secondary" size="sm" className="justify-start">Renew All</Button>
              <Button variant="secondary" size="sm" className="justify-start">Clear Cache</Button>
            </div>
          </GlassCard>
        </div>
      </div>
    </DashboardShell>
  );
}

/* --- Helper Components --- */

function StatCard({ title, value, change, trend, subtitle, icon: Icon, color }: {
  title: string;
  value: string;
  change?: string;
  trend?: "up" | "down" | "neutral";
  subtitle?: string;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <GlassCard padding="md" className="relative overflow-hidden group">
      <div className="flex items-start justify-between mb-3">
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}15`, color }}>
          <Icon className="w-5 h-5" />
        </div>
        {change && (
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
            trend === "up" ? "text-[var(--status-success)] bg-[var(--status-success)]/10" :
            trend === "down" ? "text-[var(--status-error)] bg-[var(--status-error)]/10" :
            "text-[var(--text-secondary)] bg-black/5 dark:bg-white/5"
          }`}>
            {change}
          </span>
        )}
      </div>
      <p className="text-[var(--text-secondary)] text-sm font-medium mb-1">{title}</p>
      <p className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">{value}</p>
      {subtitle && <p className="text-xs text-[var(--text-tertiary)] mt-1">{subtitle}</p>}
      
      {/* Hover Glow Effect */}
      <div className="absolute -right-4 -bottom-4 w-24 h-24 rounded-full blur-2xl opacity-0 group-hover:opacity-20 transition-opacity duration-500 pointer-events-none" style={{ backgroundColor: color }} />
    </GlassCard>
  );
}

function HealthRow({ label, value, status }: { label: string; value?: string; status?: "connected" | "good" | "warning" | "error" }) {
  const statusColors = {
    connected: "var(--status-success)",
    good: "var(--status-success)",
    warning: "var(--status-warning)",
    error: "var(--status-error)",
  };

  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <div className="flex items-center gap-2">
        {value && <span className="font-mono text-[var(--text-primary)]">{value}</span>}
        {status && (
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: statusColors[status] }} />
        )}
      </div>
    </div>
  );
}
