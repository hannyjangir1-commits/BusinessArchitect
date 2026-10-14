import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  Cpu, RotateCw, Filter, CheckCircle2,
  RefreshCw, Loader2
} from 'lucide-react';

export const AdminAIOperationsPage: React.FC = () => {
  const [ops, setOps] = useState<any[]>([]);
  const [stats, setStats] = useState<any | null>(null);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(20);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [moduleFilter, setModuleFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, statsRes] = await Promise.all([
        api.admin.aiOps.list({
          page,
          limit,
          status: statusFilter !== 'all' ? statusFilter : undefined,
          module: moduleFilter !== 'all' ? moduleFilter : undefined
        }),
        api.admin.aiOps.getStats()
      ]);
      setOps(listRes.items);
      setTotal(listRes.total);
      setTotalPages(listRes.total_pages);
      setStats(statsRes);
    } catch (e: any) {
      console.error('Failed to load AI operations data', e);
    } finally {
      setLoading(false);
    }
  }, [page, limit, statusFilter, moduleFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRetry = async (opId: string) => {
    if (!confirm('Execute controlled administrative retry for this failed operation?')) return;
    setRetryingId(opId);
    try {
      const res = await api.admin.aiOps.retry(opId);
      alert(res.message || 'Retry successful');
      fetchData();
    } catch (err: any) {
      alert(err.message || 'Retry failed');
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      {/* Page Title */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: '0 0 4px' }}>
            Gemini AI Operations Center
          </h1>
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
            Inspect generation latency percentiles, error classifications, retry rates, and execution telemetry
          </p>
        </div>
      </div>

      {/* KPI Stats Bar */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Configured Model</div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: '#4338ca', marginTop: '4px' }}>{stats.configured_model}</div>
          </div>
          <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Success Rate</div>
            <div style={{ fontSize: '22px', fontWeight: 800, color: stats.success_rate >= 80 ? '#16a34a' : '#ef4444', marginTop: '4px' }}>
              {stats.success_rate}%
            </div>
          </div>
          <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Latency (Median)</div>
            <div style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>{stats.median_latency_ms}ms</div>
          </div>
          <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Latency (p95)</div>
            <div style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>{stats.p95_latency_ms}ms</div>
          </div>
          <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Total / Retried</div>
            <div style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
              {stats.total_operations} <span style={{ fontSize: '13px', color: '#64748b', fontWeight: 500 }}>({stats.retried_operations} retried)</span>
            </div>
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div style={{ background: '#ffffff', borderRadius: '10px', padding: '14px 18px', border: '1px solid #e2e8f0', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#64748b' }}>
            <Filter size={15} />
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={e => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
            >
              <option value="all">All Outcomes</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="timeout">Timeout</option>
              <option value="retried">Retried</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#64748b' }}>
            <span>Module:</span>
            <select
              value={moduleFilter}
              onChange={e => {
                setModuleFilter(e.target.value);
                setPage(1);
              }}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
            >
              <option value="all">All Modules</option>
              <option value="bmc">BMC</option>
              <option value="tech_stack">Tech Stack</option>
              <option value="idea_validator">Idea Validator</option>
              <option value="market_research">Market Research</option>
              <option value="execution_roadmap">Roadmap</option>
              <option value="copilot">Copilot</option>
            </select>
          </div>
        </div>

        <button
          onClick={fetchData}
          title="Refresh operations"
          style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
        >
          <RefreshCw size={15} style={{ color: '#475569' }} />
        </button>
      </div>

      {/* Operations Table */}
      <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
            <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
            <p style={{ margin: 0 }}>Loading AI operation telemetry...</p>
          </div>
        ) : ops.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
            <Cpu size={32} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
            <p style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>No AI operations recorded matching criteria</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                <th style={{ padding: '14px 18px' }}>Operation / Module</th>
                <th style={{ padding: '14px 18px' }}>Type</th>
                <th style={{ padding: '14px 18px' }}>Status</th>
                <th style={{ padding: '14px 18px' }}>Duration</th>
                <th style={{ padding: '14px 18px' }}>Validation / Diagnostics</th>
                <th style={{ padding: '14px 18px' }}>Timestamp</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {ops.map(o => (
                <tr key={o.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '14px 18px' }}>
                    <div style={{ fontWeight: 700, color: '#0f172a' }}>{o.module_type.replace('_', ' ').toUpperCase()}</div>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>ID: {o.id}</div>
                  </td>
                  <td style={{ padding: '14px 18px', textTransform: 'capitalize', color: '#475569', fontWeight: 500 }}>
                    {o.operation_type}
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: o.status === 'success' ? '#dcfce7' : o.status === 'retried' ? '#e0e7ff' : '#fee2e2',
                        color: o.status === 'success' ? '#15803d' : o.status === 'retried' ? '#4338ca' : '#b91c1c'
                      }}
                    >
                      {o.status.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '14px 18px', fontWeight: 600, color: '#334155' }}>
                    {o.duration_ms}ms
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    {o.error_message ? (
                      <span title={o.error_message} style={{ color: '#ef4444', fontSize: '12px' }}>
                        {o.error_category || 'Error'}: {o.error_message.slice(0, 45)}...
                      </span>
                    ) : (
                      <span style={{ color: '#16a34a', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle2 size={13} /> Schema Validated
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                    {new Date(o.created_at).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                    {o.status !== 'success' && (
                      <button
                        onClick={() => handleRetry(o.id)}
                        disabled={retryingId === o.id}
                        title="Retry failed generation"
                        style={{
                          padding: '5px 10px',
                          borderRadius: '4px',
                          border: '1px solid #cbd5e1',
                          background: '#ffffff',
                          color: '#4338ca',
                          cursor: 'pointer',
                          fontSize: '12px',
                          fontWeight: 600,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        {retryingId === o.id ? (
                          <Loader2 size={13} className="spin-animate" />
                        ) : (
                          <RotateCw size={13} />
                        )}
                        <span>Retry</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        <div style={{ padding: '14px 20px', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: '#64748b' }}>
          <div>Showing {ops.length} of {total} operations</div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              style={{ padding: '5px 12px', borderRadius: '4px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: page <= 1 ? 'not-allowed' : 'pointer', opacity: page <= 1 ? 0.5 : 1 }}
            >
              Previous
            </button>
            <span style={{ display: 'flex', alignItems: 'center', padding: '0 8px', fontWeight: 600 }}>
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              style={{ padding: '5px 12px', borderRadius: '4px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: page >= totalPages ? 'not-allowed' : 'pointer', opacity: page >= totalPages ? 0.5 : 1 }}
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
