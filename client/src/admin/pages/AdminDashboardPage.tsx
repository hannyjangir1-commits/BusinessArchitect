import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  Users, FolderKanban, Cpu, AlertTriangle,
  Database, Loader2, RefreshCw
} from 'lucide-react';

interface AdminDashboardPageProps {
  onNavigate?: (path: string) => void;
}

export const AdminDashboardPage: React.FC<AdminDashboardPageProps> = ({ onNavigate }) => {
  const [range, setRange] = useState<string>('30d');
  const [customStart, setCustomStart] = useState<string>('');
  const [customEnd, setCustomEnd] = useState<string>('');
  const [stats, setStats] = useState<any>(null);
  const [trends, setTrends] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = { range };
      if (range === 'custom' && customStart && customEnd) {
        params.custom_start = customStart;
        params.custom_end = customEnd;
      }
      const [statsData, trendsData] = await Promise.all([
        api.admin.dashboard.getStats(params),
        api.admin.dashboard.getTrends(params)
      ]);
      setStats(statsData);
      setTrends(trendsData);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  }, [range, customStart, customEnd]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  if (loading && !stats) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', flexDirection: 'column', gap: '12px' }}>
        <Loader2 size={32} style={{ color: 'var(--primary-text)', animation: 'spin 1s linear infinite' }} />
        <span style={{ fontSize: '14px', color: 'var(--text-muted)', fontWeight: 500 }}>Aggregating live platform telemetry...</span>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div style={{ padding: '30px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--bg-subtle)', borderRadius: '12px', color: 'var(--danger-text)' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '8px' }}>Failed to load dashboard</h3>
        <p style={{ fontSize: '13px', marginBottom: '16px' }}>{error}</p>
        <button
          onClick={fetchDashboardData}
          style={{ padding: '8px 16px', background: 'var(--danger-text)', color: 'var(--text-main)', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '13px' }}
        >
          Retry
        </button>
      </div>
    );
  }

  const userStats = stats?.users || {};
  const projStats = stats?.projects || {};
  const aiStats = stats?.ai || {};
  const infraStats = stats?.infrastructure || {};
  const alerts = stats?.alerts || [];
  const trendPoints = trends?.points || [];

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      {/* Page Header with Time Filters */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 4px', letterSpacing: '-0.02em' }}>
            Enterprise Command Center
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Live platform metrics, generation observability, and operational governance
          </p>
        </div>

        {/* Date Filter Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'var(--bg-card)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-color)', boxShadow: '0 1px 2px rgb(69 60 55 / 0.05)' }}>
            {['24h', '7d', '30d', '90d', 'custom'].map(opt => (
              <button
                key={opt}
                onClick={() => setRange(opt)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  background: range === opt ? 'var(--primary-text)' : 'transparent',
                  color: range === opt ? 'var(--bg-card)' : 'var(--text-main)',
                  fontWeight: 600,
                  fontSize: '12px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {opt.toUpperCase()}
              </button>
            ))}
            <button
              onClick={fetchDashboardData}
              title="Refresh metrics"
              style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px', display: 'flex' }}
            >
              <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
            </button>
          </div>

          {range === 'custom' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-card)', padding: '4px 8px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <input
                type="date"
                value={customStart}
                onChange={e => setCustomStart(e.target.value)}
                style={{ border: '1px solid var(--border-color)', borderRadius: '4px', padding: '3px 6px', fontSize: '11px' }}
                title="Start Date"
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>to</span>
              <input
                type="date"
                value={customEnd}
                onChange={e => setCustomEnd(e.target.value)}
                style={{ border: '1px solid var(--border-color)', borderRadius: '4px', padding: '3px 6px', fontSize: '11px' }}
                title="End Date"
              />
            </div>
          )}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px', marginBottom: '28px' }}>
        {/* Total Users */}
        <div style={{ background: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Users</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Users size={16} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1 }}>{userStats.total || 0}</div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--primary-text)', fontWeight: 600 }}>+{userStats.new_in_period || 0} new</span>
            <span>•</span>
            <span>{userStats.active_in_period || 0} active</span>
            {userStats.suspended > 0 && <span style={{ color: 'var(--danger-text)', fontWeight: 600 }}>({userStats.suspended} suspended)</span>}
          </div>
        </div>

        {/* Total Projects */}
        <div style={{ background: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Projects</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FolderKanban size={16} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1 }}>{projStats.total || 0}</div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
            <span style={{ color: 'var(--primary-text)', fontWeight: 600 }}>+{projStats.new_in_period || 0} new</span>
            <span>•</span>
            <span>{projStats.with_saved_modules || 0} with modules</span>
          </div>
        </div>

        {/* Generation Operations */}
        <div style={{ background: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Generation Success Rate</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Cpu size={16} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1 }}>
            {aiStats.success_rate || 100}%
          </div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
            <span>{aiStats.total_operations || 0} ops</span>
            <span>•</span>
            <span style={{ color: 'var(--text-muted)' }}>p50: {aiStats.median_latency_ms || 0}ms</span>
            <span>•</span>
            <span style={{ color: 'var(--text-muted)' }}>p95: {aiStats.p95_latency_ms || 0}ms</span>
          </div>
        </div>

        {/* Database Health & Latency */}
        <div style={{ background: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Database Status</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Database size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--primary-text)', lineHeight: 1 }}>
            {infraStats.database_status === 'connected' ? 'Connected' : 'Degraded'}
          </div>
          <div style={{ marginTop: '14px', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
            <span>Ping: {infraStats.database_latency_ms || 0}ms</span>
            <span>•</span>
            <span>{infraStats.recent_24h_errors || 0} errors (24h)</span>
          </div>
        </div>
      </div>

      {/* Operational Alerts Banner */}
      {alerts.length > 0 && (
        <div style={{ marginBottom: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <AlertTriangle size={18} style={{ color: 'var(--primary-text)' }} />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              Active Operational Alerts ({alerts.length})
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {alerts.map((al: any) => (
              <div
                key={al.id}
                style={{
                  backgroundColor: al.severity === 'high' ? 'var(--bg-subtle)' : al.severity === 'medium' ? 'var(--bg-subtle)' : 'var(--bg-subtle)',
                  border: `1px solid ${al.severity === 'high' ? 'var(--bg-subtle)' : al.severity === 'medium' ? 'var(--border-color)' : 'var(--border-color)'}`,
                  borderRadius: '10px',
                  padding: '14px 18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '16px'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        backgroundColor: al.severity === 'high' ? 'var(--danger-text)' : 'var(--primary-text)',
                        color: 'var(--text-main)'
                      }}
                    >
                      {al.severity}
                    </span>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)' }}>{al.title}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-main)' }}>
                    <strong>{al.subsystem}:</strong> {al.evidence}
                  </div>
                </div>
                {al.link && (
                  <button
                    onClick={() => {
                      if (onNavigate) {
                        onNavigate(al.link === '/admin/security' ? '/admin/account' : al.link);
                      } else {
                        window.location.href = al.link;
                      }
                    }}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      backgroundColor: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-main)',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    Investigate →
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Visual Analytics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '24px', marginBottom: '28px' }}>
        {/* Trend Chart: Users & Projects */}
        <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '24px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', margin: '0 0 2px' }}>Platform Growth</h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>Daily new user registrations and project creation</p>
            </div>
            <div style={{ display: 'flex', gap: '14px', fontSize: '12px', fontWeight: 600 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: 'var(--bg-subtle)' }} />
                <span>Users</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: 'var(--bg-subtle)' }} />
                <span>Projects</span>
              </div>
            </div>
          </div>

          {/* SVG Trend Visualization */}
          {trendPoints.length > 0 ? (
            <div style={{ height: '200px', display: 'flex', alignItems: 'flex-end', gap: '6px', paddingTop: '20px' }}>
              {trendPoints.slice(-14).map((pt: any, idx: number) => {
                const maxVal = Math.max(...trendPoints.slice(-14).map((p: any) => Math.max(p.users || 0, p.projects || 0, 1)));
                const uHeight = Math.max(4, ((pt.users || 0) / maxVal) * 160);
                const pHeight = Math.max(4, ((pt.projects || 0) / maxVal) * 160);
                return (
                  <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                    <div style={{ width: '100%', display: 'flex', gap: '2px', alignItems: 'flex-end', justifyContent: 'center' }}>
                      <div
                        title={`${pt.date}: ${pt.users} users`}
                        style={{ width: '45%', height: `${uHeight}px`, backgroundColor: 'var(--bg-subtle)', borderRadius: '3px 3px 0 0' }}
                      />
                      <div
                        title={`${pt.date}: ${pt.projects} projects`}
                        style={{ width: '45%', height: `${pHeight}px`, backgroundColor: 'var(--bg-subtle)', borderRadius: '3px 3px 0 0' }}
                      />
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '6px', transform: 'rotate(-45deg)', whiteSpace: 'nowrap' }}>
                      {pt.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ height: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              No time-series points recorded in this window.
            </div>
          )}
        </div>

        {/* Generation Operations Breakdown */}
        <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '24px', border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ marginBottom: '18px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', margin: '0 0 2px' }}>Generation Operations by Module</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>Distribution of blueprint generation and section modification requests</p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {Object.keys(aiStats.operations_by_module || {}).length > 0 ? (
              Object.entries(aiStats.operations_by_module).map(([mod, count]: any) => {
                const total = aiStats.total_operations || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <div key={mod}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
                      <span>{mod.replace('_', ' ').toUpperCase()}</span>
                      <span>{count} ops ({pct}%)</span>
                    </div>
                    <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-subtle)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', backgroundColor: 'var(--bg-subtle)', borderRadius: '4px' }} />
                    </div>
                  </div>
                );
              })
            ) : (
              <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                No generation operations recorded in this period.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
