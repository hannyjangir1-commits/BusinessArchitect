import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  ClipboardList, Search, RefreshCw, Loader2, CheckCircle2,
  XCircle, AlertTriangle, ChevronLeft, ChevronRight, Eye, Shield
} from 'lucide-react';

export const AdminAuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [outcomeFilter, setOutcomeFilter] = useState<string>('all');
  const [targetFilter, setTargetFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedLog, setSelectedLog] = useState<any | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.admin.audit.list({
        page,
        limit: 25,
        search: search.trim() || undefined,
        outcome: outcomeFilter !== 'all' ? outcomeFilter : undefined,
        target_type: targetFilter !== 'all' ? targetFilter : undefined
      });
      setLogs(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, search, outcomeFilter, targetFilter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLogs();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ClipboardList size={26} color="#6d855f" />
            Administrative Audit Trail
          </h1>
          <p style={{ margin: '6px 0 0', color: 'var(--text-muted)', fontSize: '14px' }}>
            Tamper-evident, server-side log of administrative actions, identity updates, and privilege changes.
          </p>
        </div>
        <button
          onClick={() => fetchLogs()}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: 'var(--bg-subtle)',
            color: 'var(--text-main)',
            border: '1px solid #687164',
            borderRadius: '8px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            fontWeight: 500
          }}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Filter / Search Bar */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          flexWrap: 'wrap',
          backgroundColor: 'var(--bg-subtle)',
          padding: '16px',
          borderRadius: '12px',
          border: '1px solid var(--border-color)'
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px', flex: 1, minWidth: '240px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search by action, reason, target ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px 9px 36px',
                backgroundColor: 'var(--bg-subtle)',
                border: '1px solid #687164',
                borderRadius: '8px',
                color: 'var(--text-main)',
                fontSize: '13px',
                outline: 'none'
              }}
            />
          </div>
          <button
            type="submit"
            style={{
              padding: '9px 18px',
              backgroundColor: '#6d855f',
              color: 'var(--text-main)',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 600
            }}
          >
            Filter
          </button>
        </form>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Target:</span>
          <select
            value={targetFilter}
            onChange={(e) => { setTargetFilter(e.target.value); setPage(1); }}
            style={{
              padding: '9px 12px',
              backgroundColor: 'var(--bg-subtle)',
              border: '1px solid #687164',
              borderRadius: '8px',
              color: 'var(--text-main)',
              fontSize: '13px'
            }}
          >
            <option value="all">All Targets</option>
            <option value="user">User</option>
            <option value="project">Project</option>
            <option value="system_setting">System Setting</option>
            <option value="maintenance">Maintenance</option>
            <option value="security">Security</option>
            <option value="ai_operation">Generation Operation</option>
            <option value="integrity">Integrity</option>
          </select>

          <span style={{ fontSize: '13px', color: 'var(--text-muted)', marginLeft: '6px' }}>Outcome:</span>
          <select
            value={outcomeFilter}
            onChange={(e) => { setOutcomeFilter(e.target.value); setPage(1); }}
            style={{
              padding: '9px 12px',
              backgroundColor: 'var(--bg-subtle)',
              border: '1px solid #687164',
              borderRadius: '8px',
              color: 'var(--text-main)',
              fontSize: '13px'
            }}
          >
            <option value="all">All Outcomes</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="denied">Denied</option>
          </select>
        </div>
      </div>

      {/* Audit Log Table */}
      <div
        style={{
          backgroundColor: 'var(--bg-subtle)',
          borderRadius: '12px',
          border: '1px solid var(--border-color)',
          overflow: 'hidden'
        }}
      >
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-main)' }}>
            Logged Audit Events ({total})
          </span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Page {page} of {totalPages || 1}
          </span>
        </div>

        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto 12px', color: '#6d855f' }} />
            Loading audit records...
          </div>
        ) : logs.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No audit records match the selected filter.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Timestamp</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Actor</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Action</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Target</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Outcome</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Reason / Note</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    style={{
                      borderBottom: '1px solid var(--border-color)',
                      color: '#dfe2d6',
                      transition: 'background-color 0.15s'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--border-color)55')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '14px 16px', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontSize: '12px' }}>
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td style={{ padding: '14px 16px', fontWeight: 500, color: 'var(--text-main)' }}>
                      {log.actor_username}
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          backgroundColor: 'var(--bg-subtle)',
                          border: '1px solid #687164',
                          fontSize: '12px',
                          fontFamily: 'monospace',
                          color: '#d6dccf'
                        }}
                      >
                        {log.action}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', color: 'var(--text-muted)' }}>
                      <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>
                        {log.target_type || '—'}:
                      </span>{' '}
                      <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                        {log.target_id ? log.target_id.slice(0, 16) : '—'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      {log.outcome === 'success' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#10b981', fontSize: '12px', fontWeight: 600 }}>
                          <CheckCircle2 size={14} /> Success
                        </span>
                      ) : log.outcome === 'failed' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#ef4444', fontSize: '12px', fontWeight: 600 }}>
                          <XCircle size={14} /> Failed
                        </span>
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#f59e0b', fontSize: '12px', fontWeight: 600 }}>
                          <AlertTriangle size={14} /> {log.outcome}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', color: 'var(--text-muted)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {log.reason || '—'}
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <button
                        onClick={() => setSelectedLog(log)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '6px 10px',
                          backgroundColor: 'var(--bg-subtle)',
                          border: '1px solid #687164',
                          borderRadius: '6px',
                          color: 'var(--text-muted)',
                          cursor: 'pointer',
                          fontSize: '12px'
                        }}
                      >
                        <Eye size={13} /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderTop: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Showing {logs.length} of {total} records
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 12px',
                backgroundColor: 'var(--bg-subtle)',
                color: page <= 1 ? '#687164' : '#f7f6ef',
                border: '1px solid #687164',
                borderRadius: '6px',
                cursor: page <= 1 ? 'not-allowed' : 'pointer',
                fontSize: '12px'
              }}
            >
              <ChevronLeft size={14} /> Prev
            </button>
            <span style={{ display: 'flex', alignItems: 'center', padding: '0 8px', fontSize: '13px', color: 'var(--text-muted)' }}>
              {page} / {totalPages || 1}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 12px',
                backgroundColor: 'var(--bg-subtle)',
                color: page >= totalPages ? '#687164' : '#f7f6ef',
                border: '1px solid #687164',
                borderRadius: '6px',
                cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                fontSize: '12px'
              }}
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Log Details Modal */}
      {selectedLog && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }}
          onClick={() => setSelectedLog(null)}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-subtle)',
              border: '1px solid #687164',
              borderRadius: '16px',
              padding: '28px',
              maxWidth: '650px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Shield size={20} color="#6d855f" />
                  Audit Event Payload
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                  Event ID: {selectedLog.id}
                </p>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  fontSize: '20px',
                  cursor: 'pointer',
                  padding: '4px'
                }}
              >
                &times;
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px', fontSize: '13px' }}>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>Timestamp</span>
                <div style={{ color: 'var(--text-main)', fontWeight: 500, marginTop: '2px' }}>
                  {new Date(selectedLog.timestamp).toLocaleString()}
                </div>
              </div>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>Actor</span>
                <div style={{ color: 'var(--text-main)', fontWeight: 500, marginTop: '2px' }}>
                  {selectedLog.actor_username} (ID: {selectedLog.actor_id || 'system'})
                </div>
              </div>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>Action</span>
                <div style={{ color: '#82936d', fontWeight: 600, fontFamily: 'monospace', marginTop: '2px' }}>
                  {selectedLog.action}
                </div>
              </div>
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>Outcome</span>
                <div style={{ color: selectedLog.outcome === 'success' ? '#10b981' : '#ef4444', fontWeight: 600, marginTop: '2px' }}>
                  {selectedLog.outcome}
                </div>
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Reason / Note</span>
              <div style={{ marginTop: '6px', padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px', color: 'var(--text-muted)', fontSize: '13px' }}>
                {selectedLog.reason || 'No supplementary reason specified.'}
              </div>
            </div>

            <div style={{ marginBottom: '24px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Structured Details / Metadata</span>
              <pre
                style={{
                  marginTop: '6px',
                  padding: '14px',
                  backgroundColor: 'var(--bg-subtle)',
                  borderRadius: '8px',
                  color: '#718765',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  overflowX: 'auto',
                  border: '1px solid var(--border-color)'
                }}
              >
                {JSON.stringify(selectedLog.details, null, 2)}
              </pre>
            </div>

            <button
              onClick={() => setSelectedLog(null)}
              style={{
                width: '100%',
                padding: '10px',
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-main)',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
