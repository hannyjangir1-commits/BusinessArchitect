import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  Users, FolderKanban, Cpu, AlertTriangle,
  Database, Loader2, RefreshCw
} from 'lucide-react';

export const AdminDashboardPage: React.FC = () => {
  const [range, setRange] = useState<string>('30d');
  const [stats, setStats] = useState<any>(null);
  const [trends, setTrends] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, trendsData] = await Promise.all([
        api.admin.dashboard.getStats({ range }),
        api.admin.dashboard.getTrends({ range })
      ]);
      setStats(statsData);
      setTrends(trendsData);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  if (loading && !stats) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', flexDirection: 'column', gap: '12px' }}>
        <Loader2 size={32} style={{ color: '#6366f1', animation: 'spin 1s linear infinite' }} />
        <span style={{ fontSize: '14px', color: '#64748b', fontWeight: 500 }}>Aggregating live platform telemetry...</span>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div style={{ padding: '30px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '12px', color: '#991b1b' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '8px' }}>Failed to load dashboard</h3>
        <p style={{ fontSize: '13px', marginBottom: '16px' }}>{error}</p>
        <button
          onClick={fetchDashboardData}
          style={{ padding: '8px 16px', background: '#dc2626', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '13px' }}
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
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: '0 0 4px', letterSpacing: '-0.02em' }}>
            Enterprise Command Center
          </h1>
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
            Live platform metrics, generation observability, and operational governance
          </p>
        </div>

        {/* Date Filter Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#ffffff', padding: '4px', borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          {['24h', '7d', '30d', '90d'].map(opt => (
            <button
              key={opt}
              onClick={() => setRange(opt)}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                border: 'none',
                background: range === opt ? '#6366f1' : 'transparent',
                color: range === opt ? '#ffffff' : '#64748b',
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
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: '6px', display: 'flex' }}
          >
            <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px', marginBottom: '28px' }}>
        {/* Total Users */}
        <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Users</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: '#e0e7ff', color: '#4f46e5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Users size={16} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#0f172a', lineHeight: 1 }}>{userStats.total || 0}</div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: '#64748b', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ color: '#16a34a', fontWeight: 600 }}>+{userStats.new_in_period || 0} new</span>
            <span>•</span>
            <span>{userStats.active_in_period || 0} active</span>
            {userStats.suspended > 0 && <span style={{ color: '#ef4444', fontWeight: 600 }}>({userStats.suspended} suspended)</span>}
          </div>
        </div>

        {/* Total Projects */}
        <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Projects</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: '#ede9fe', color: '#7c3aed', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FolderKanban size={16} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#0f172a', lineHeight: 1 }}>{projStats.total || 0}</div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: '#64748b', display: 'flex', gap: '8px' }}>
            <span style={{ color: '#16a34a', fontWeight: 600 }}>+{projStats.new_in_period || 0} new</span>
            <span>•</span>
            <span>{projStats.with_saved_modules || 0} with modules</span>
          </div>
        </div>

        {/* Generation Operations */}
        <div style={{ background: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Generation Success Rate</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: '#ecfdf5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Cpu size={16} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#0f172a', lineHeight: 1 }}>
            {aiStats.success_rate || 100}%
          </div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: '#64748b', display: 'flex', gap: '8px' }}>
            <span>{aiStats.total_operations || 0} ops</span>
            <span>•</span>
            <span style={{ color: '#64748b' }}>p50: {aiStats.median_latency_ms || 0}ms</span>
            <span>•</span>
            <span style={{ color: '#64748b' }}>p95: {aiStats.p95_latency_ms || 0}ms</span>
          </div>
        </div>

        {/* Database Health & Latency */}
        <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Database Status</span>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: '#f0fdf4', color: '#16a34a', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Database size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#16a34a', lineHeight: 1 }}>
            {infraStats.database_status === 'connected' ? 'Connected' : 'Degraded'}
          </div>
          <div style={{ marginTop: '14px', fontSize: '12px', color: '#64748b', display: 'flex', gap: '8px' }}>
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
            <AlertTriangle size={18} style={{ color: '#f59e0b' }} />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a', margin: 0 }}>
              Active Operational Alerts ({alerts.length})
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {alerts.map((al: any) => (
              <div
                key={al.id}
                style={{
                  backgroundColor: al.severity === 'high' ? '#fff1f2' : al.severity === 'medium' ? '#fffbeb' : '#f8fafc',
                  border: `1px solid ${al.severity === 'high' ? '#fecdd3' : al.severity === 'medium' ? '#fde68a' : '#e2e8f0'}`,
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
                        backgroundColor: al.severity === 'high' ? '#e11d48' : '#d97706',
                        color: '#ffffff'
                      }}
                    >
                      {al.severity}
                    </span>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>{al.title}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#475569' }}>
                    <strong>{al.subsystem}:</strong> {al.evidence}
                  </div>
                </div>
                {al.link && (
                  <a
                    href={al.link}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      backgroundColor: '#ffffff',
                      border: '1px solid #cbd5e1',
                      color: '#0f172a',
                      fontSize: '12px',
                      fontWeight: 600,
                      textDecoration: 'none',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    Investigate →
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Visual Analytics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '24px', marginBottom: '28px' }}>
        {/* Trend Chart: Users & Projects */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: '0 0 2px' }}>Platform Growth</h3>
              <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>Daily new user registrations and project creation</p>
            </div>
            <div style={{ display: 'flex', gap: '14px', fontSize: '12px', fontWeight: 600 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#6366f1' }} />
                <span>Users</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#0ea5e9' }} />
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
                        style={{ width: '45%', height: `${uHeight}px`, backgroundColor: '#6366f1', borderRadius: '3px 3px 0 0' }}
                      />
                      <div
                        title={`${pt.date}: ${pt.projects} projects`}
                        style={{ width: '45%', height: `${pHeight}px`, backgroundColor: '#0ea5e9', borderRadius: '3px 3px 0 0' }}
                      />
                    </div>
                    <span style={{ fontSize: '10px', color: '#94a3b8', marginTop: '6px', transform: 'rotate(-45deg)', whiteSpace: 'nowrap' }}>
                      {pt.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ height: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: '13px' }}>
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
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                      <span>{mod.replace('_', ' ').toUpperCase()}</span>
                      <span>{count} ops ({pct}%)</span>
                    </div>
                    <div style={{ width: '100%', height: '8px', backgroundColor: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', backgroundColor: '#6366f1', borderRadius: '4px' }} />
                    </div>
                  </div>
                );
              })
            ) : (
              <div style={{ padding: '30px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                No generation operations recorded in this period.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
