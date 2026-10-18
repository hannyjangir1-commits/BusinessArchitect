import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  Cpu, RotateCw, Filter, CheckCircle2,
  RefreshCw, Loader2, ShieldCheck
} from 'lucide-react';

export const AdminAIOperationsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'requests' | 'quality'>('requests');
  const [ops, setOps] = useState<any[]>([]);
  const [stats, setStats] = useState<any | null>(null);
  const [quality, setQuality] = useState<any | null>(null);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(20);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [moduleFilter, setModuleFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [listRes, statsRes, qualityRes] = await Promise.all([
        api.admin.aiOps.list({
          page,
          limit,
          status: statusFilter !== 'all' ? statusFilter : undefined,
          module: moduleFilter !== 'all' ? moduleFilter : undefined
        }),
        api.admin.aiOps.getStats(),
        api.admin.aiOps.getQuality()
      ]);
      setOps(listRes.items || []);
      setTotal(listRes.total || 0);
      setTotalPages(listRes.total_pages || 1);
      setStats(statsRes);
      setQuality(qualityRes);
    } catch (e: any) {
      setErrorMsg(e.message || 'Failed to load generation activity');
    } finally {
      setLoading(false);
    }
  }, [page, limit, statusFilter, moduleFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRetry = async (op: any) => {
    if (op.status === 'success') {
      alert('Operation already succeeded');
      return;
    }
    if (op.is_retryable === false) {
      alert('This operation is marked as non-retryable');
      return;
    }
    if (!confirm(`Execute controlled administrative retry for operation '${op.id}'?`)) return;

    setRetryingId(op.id);
    try {
      const res = await api.admin.aiOps.retry(op.id);
      alert(res.message || 'Retry initiated and executed successfully');
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 4px' }}>
            Generation Activity & Quality
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Inspect generation latency, error taxonomy, structured schema validation, and controlled retries.
          </p>
        </div>
        <button
          onClick={fetchData}
          title="Refresh metrics and operations"
          style={{ background: '#ffffff', border: '1px solid #d9ddcf', borderRadius: '6px', padding: '7px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--text-main)' }}
        >
          <RefreshCw size={13} className={loading ? 'spin-animate' : ''} />
          Refresh Data
        </button>
      </div>

      {errorMsg && (
        <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '13px' }}>
          {errorMsg}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #dfe2d6', gap: '24px', marginBottom: '24px' }}>
        <button
          onClick={() => setActiveTab('requests')}
          style={{
            padding: '12px 4px',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'requests' ? '2px solid #6d855f' : '2px solid transparent',
            color: activeTab === 'requests' ? '#6d855f' : '#687164',
            fontWeight: activeTab === 'requests' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Cpu size={16} />
          Requests & Telemetry
        </button>

        <button
          onClick={() => setActiveTab('quality')}
          style={{
            padding: '12px 4px',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'quality' ? '2px solid #6d855f' : '2px solid transparent',
            color: activeTab === 'quality' ? '#6d855f' : '#687164',
            fontWeight: activeTab === 'quality' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <ShieldCheck size={16} />
          Output Quality & Schema Validation
        </button>
      </div>

      {/* TAB 1: Requests & Telemetry */}
      {activeTab === 'requests' && (
        <>
          {/* KPI Stats Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #dfe2d6', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Processing Engine</div>
              <div style={{ fontSize: '16px', fontWeight: 800, color: '#5d7550', marginTop: '4px' }}>{stats?.configured_model || 'Gemini 2.5 Pro'}</div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #dfe2d6', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Success Rate</div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: (stats?.success_rate ?? 100) >= 80 ? '#16a34a' : '#ef4444', marginTop: '4px' }}>
                {stats?.success_rate ?? 100}%
              </div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #dfe2d6', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Latency (Median)</div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>{stats?.median_latency_ms || 0}ms</div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #dfe2d6', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Latency (p95)</div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>{stats?.p95_latency_ms || 0}ms</div>
            </div>
            <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #dfe2d6', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Total / Retried</div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
                {stats?.total_operations || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>({stats?.retried_operations || 0} retried)</span>
              </div>
            </div>
          </div>

          {/* Filter Toolbar */}
          <div style={{ background: '#ffffff', borderRadius: '10px', padding: '14px 18px', border: '1px solid #dfe2d6', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-muted)' }}>
                <Filter size={15} />
                <span>Status:</span>
                <select
                  value={statusFilter}
                  onChange={e => {
                    setStatusFilter(e.target.value);
                    setPage(1);
                  }}
                  style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #d9ddcf', fontSize: '13px' }}
                >
                  <option value="all">All Outcomes</option>
                  <option value="success">Success</option>
                  <option value="failed">Failed</option>
                  <option value="timeout">Timeout</option>
                  <option value="retried">Retried</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-muted)' }}>
                <span>Module:</span>
                <select
                  value={moduleFilter}
                  onChange={e => {
                    setModuleFilter(e.target.value);
                    setPage(1);
                  }}
                  style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #d9ddcf', fontSize: '13px' }}
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

            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              {total} operation{total !== 1 ? 's' : ''} recorded
            </div>
          </div>

          {/* Operations Table */}
          <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #dfe2d6', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
            {loading ? (
              <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6d855f' }} />
                <p style={{ margin: 0 }}>Loading operation telemetry...</p>
              </div>
            ) : ops.length === 0 ? (
              <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <Cpu size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
                <p style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>No generation operations recorded matching criteria</p>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>Generation requests will appear here once users create a blueprint or roadmap tasks.</p>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f7f6ef', borderBottom: '1px solid #dfe2d6', color: 'var(--text-main)', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
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
                    <tr key={o.id} style={{ borderBottom: '1px solid #f0f1e9' }}>
                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>{o.module_type?.replace('_', ' ').toUpperCase()}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>ID: {o.id}</div>
                      </td>
                      <td style={{ padding: '14px 18px', textTransform: 'capitalize', color: 'var(--text-main)', fontWeight: 500 }}>
                        {o.operation_type}
                      </td>
                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            padding: '3px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: o.status === 'success' ? '#dcfce7' : o.status === 'retried' ? '#e8ede2' : '#fee2e2',
                            color: o.status === 'success' ? '#15803d' : o.status === 'retried' ? '#5d7550' : '#b91c1c'
                          }}
                        >
                          {o.status.toUpperCase()}
                        </span>
                      </td>
                      <td style={{ padding: '14px 18px', fontWeight: 600, color: 'var(--text-main)' }}>
                        {o.duration_ms || 0}ms
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
                      <td style={{ padding: '14px 18px', color: 'var(--text-muted)', fontSize: '12px' }}>
                        {new Date(o.created_at).toLocaleTimeString()}
                      </td>
                      <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                        {o.status !== 'success' && o.is_retryable !== false && (
                          <button
                            onClick={() => handleRetry(o)}
                            disabled={retryingId === o.id}
                            title="Execute controlled administrative retry"
                            style={{
                              padding: '5px 10px',
                              borderRadius: '4px',
                              border: '1px solid #d9ddcf',
                              background: '#ffffff',
                              color: '#5d7550',
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
                        {o.status !== 'success' && o.is_retryable === false && (
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Non-retryable</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ padding: '14px 20px', borderTop: '1px solid #dfe2d6', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
                <div>Showing {ops.length} of {total} operations</div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    style={{ padding: '5px 12px', borderRadius: '4px', border: '1px solid #d9ddcf', background: '#ffffff', cursor: page <= 1 ? 'not-allowed' : 'pointer', opacity: page <= 1 ? 0.5 : 1 }}
                  >
                    Previous
                  </button>
                  <span style={{ display: 'flex', alignItems: 'center', padding: '0 8px', fontWeight: 600 }}>
                    Page {page} of {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    style={{ padding: '5px 12px', borderRadius: '4px', border: '1px solid #d9ddcf', background: '#ffffff', cursor: page >= totalPages ? 'not-allowed' : 'pointer', opacity: page >= totalPages ? 0.5 : 1 }}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* TAB 2: Output Quality & Schema Validation */}
      {activeTab === 'quality' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Quality Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px' }}>
            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #dfe2d6', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Validation Pass Rate</div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: '#16a34a', marginTop: '6px' }}>
                {quality?.structured_validation_rate ?? 100}%
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
                {quality?.structured_validation_passed || 0} of {quality?.total_evaluated_operations || 0} passed
              </div>
            </div>

            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #dfe2d6', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Parse Failures</div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: (quality?.parse_failures || 0) > 0 ? '#ef4444' : '#10b981', marginTop: '6px' }}>
                {quality?.parse_failures || 0}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
                JSON schema parse exceptions
              </div>
            </div>

            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #dfe2d6', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Persistence Failures</div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: (quality?.persistence_failures || 0) > 0 ? '#ef4444' : '#10b981', marginTop: '6px' }}>
                {quality?.persistence_failures || 0}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
                Database commit failures
              </div>
            </div>
          </div>

          {/* Module Performance Table */}
          <div style={{ background: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #dfe2d6', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', margin: '0 0 16px' }}>
              Module-Specific Performance & Reliability
            </h3>

            {(!stats?.module_performance || stats.module_performance.length === 0) ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: 0 }}>No module performance data available yet.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f7f6ef', borderBottom: '1px solid #dfe2d6', color: 'var(--text-main)', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                    <th style={{ padding: '12px 16px' }}>Module</th>
                    <th style={{ padding: '12px 16px' }}>Total Operations</th>
                    <th style={{ padding: '12px 16px' }}>Success Count</th>
                    <th style={{ padding: '12px 16px' }}>Success Rate</th>
                    <th style={{ padding: '12px 16px' }}>Avg Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.module_performance.map((m: any) => (
                    <tr key={m.module_type} style={{ borderBottom: '1px solid #f0f1e9' }}>
                      <td style={{ padding: '12px 16px', fontWeight: 700, color: 'var(--text-main)' }}>
                        {m.module_type.replace('_', ' ').toUpperCase()}
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-main)' }}>{m.total}</td>
                      <td style={{ padding: '12px 16px', color: '#16a34a', fontWeight: 600 }}>{m.success}</td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{ fontWeight: 700, color: (m.success_rate ?? 100) >= 80 ? '#16a34a' : '#ef4444' }}>
                          {m.success_rate != null ? `${m.success_rate}%` : 'N/A'}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>{m.avg_duration_ms}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Error Categories Breakdown */}
          {stats?.error_categories && Object.keys(stats.error_categories).length > 0 && (
            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #dfe2d6', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', margin: '0 0 16px' }}>
                Error Category Distribution
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                {Object.entries(stats.error_categories).map(([cat, count]: any) => (
                  <div key={cat} style={{ padding: '12px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: '#991b1b', fontWeight: 700, textTransform: 'uppercase' }}>{cat}</div>
                    <div style={{ fontSize: '20px', fontWeight: 800, color: '#dc2626', marginTop: '4px' }}>{count}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
