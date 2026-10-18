import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  RefreshCw, Loader2, Search
} from 'lucide-react';

export const AdminSystemHealthPage: React.FC = () => {
  const [health, setHealth] = useState<any | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [logSearch, setLogSearch] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [subsystemFilter, setSubsystemFilter] = useState<string>('all');

  const fetchSystemData = useCallback(async () => {
    setLoading(true);
    try {
      const [hRes, lRes] = await Promise.all([
        api.admin.system.getHealth(),
        api.admin.system.getLogs({
          search: logSearch.trim() || undefined,
          severity: severityFilter !== 'all' ? severityFilter : undefined,
          subsystem: subsystemFilter !== 'all' ? subsystemFilter : undefined
        })
      ]);
      setHealth(hRes);
      setLogs(lRes.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [logSearch, severityFilter, subsystemFilter]);

  useEffect(() => {
    fetchSystemData();
  }, [fetchSystemData]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchSystemData();
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 4px' }}>
            System Observability & Unified Log Explorer
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Real-time liveness, readiness, database round-trip latency, Alembic revision, and diagnostic log stream
          </p>
        </div>
        <button
          onClick={fetchSystemData}
          style={{ background: '#ffffff', border: '1px solid #d9ddcf', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600 }}
        >
          <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Component Status Grid */}
      {health && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginBottom: '28px' }}>
          {(health.components || []).map((c: any, idx: number) => {
            const isOk = c.status === 'healthy';
            return (
              <div key={idx} style={{ backgroundColor: 'var(--bg-card)', borderRadius: '10px', padding: '18px', border: '1px solid #dfe2d6', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)' }}>{c.name}</span>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '9999px',
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor: isOk ? '#dcfce7' : '#fee2e2',
                      color: isOk ? '#15803d' : '#b91c1c'
                    }}
                  >
                    {c.status.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>{c.details}</div>
                {c.latency_ms > 0 && (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
                    Latency: {c.latency_ms}ms
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Unified Log Explorer */}
      <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', border: '1px solid #dfe2d6', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #dfe2d6', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, maxWidth: '380px' }}>
            <div style={{ position: 'relative', width: '100%' }}>
              <Search size={15} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Filter logs..."
                value={logSearch}
                onChange={e => setLogSearch(e.target.value)}
                style={{ width: '100%', padding: '6px 10px 6px 32px', borderRadius: '6px', border: '1px solid #d9ddcf', fontSize: '13px', outline: 'none' }}
              />
            </div>
            <button type="submit" style={{ padding: '6px 12px', background: '#6d855f', color: 'var(--text-main)', border: 'none', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
              Filter
            </button>
          </form>

          <div style={{ display: 'flex', gap: '12px' }}>
            <select
              value={severityFilter}
              onChange={e => setSeverityFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #d9ddcf', fontSize: '12px' }}
            >
              <option value="all">All Severities</option>
              <option value="info">Info</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>

            <select
              value={subsystemFilter}
              onChange={e => setSubsystemFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #d9ddcf', fontSize: '12px' }}
            >
              <option value="all">All Subsystems</option>
              <option value="security">Security</option>
              <option value="audit">Audit</option>
              <option value="ai_ops">Generation Operations</option>
            </select>
          </div>
        </div>

        {/* Logs List */}
        <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <Loader2 size={24} className="spin-animate" style={{ margin: '0 auto 8px', color: '#6d855f' }} />
              <span style={{ fontSize: '13px' }}>Streaming logs...</span>
            </div>
          ) : logs.length === 0 ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              No operational events recorded matching query.
            </div>
          ) : (
            logs.map(log => (
              <div
                key={log.id}
                style={{
                  padding: '12px 20px',
                  borderBottom: '1px solid #f0f1e9',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '14px',
                  fontSize: '12px',
                  fontFamily: 'monospace'
                }}
              >
                <span
                  style={{
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    backgroundColor: log.severity === 'high' || log.severity === 'critical' ? '#fee2e2' : log.severity === 'medium' ? '#fef3c7' : '#f0f1e9',
                    color: log.severity === 'high' || log.severity === 'critical' ? '#b91c1c' : log.severity === 'medium' ? '#b45309' : '#687164',
                    flexShrink: 0
                  }}
                >
                  {log.severity}
                </span>

                <div style={{ flex: 1 }}>
                  <div style={{ color: 'var(--text-main)', fontWeight: 600 }}>{log.message}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '2px' }}>
                    Subsystem: {log.subsystem} • Event: {log.event_type}
                  </div>
                </div>

                <div style={{ color: 'var(--text-muted)', fontSize: '11px', flexShrink: 0 }}>
                  {new Date(log.timestamp).toLocaleTimeString()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
