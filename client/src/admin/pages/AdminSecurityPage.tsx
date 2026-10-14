import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  ShieldCheck, ShieldAlert, KeyRound, Ban, RefreshCw,
  Loader2
} from 'lucide-react';

export const AdminSecurityPage: React.FC = () => {
  const [events, setEvents] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [totalEvents, setTotalEvents] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);

  const fetchSecurityData = useCallback(async () => {
    setLoading(true);
    try {
      const [eventsRes, sessionsRes] = await Promise.all([
        api.admin.security.listEvents({
          page,
          limit: 20,
          severity: severityFilter !== 'all' ? severityFilter : undefined
        }),
        api.admin.security.listSessions()
      ]);
      setEvents(eventsRes.items);
      setTotalEvents(eventsRes.total);
      setSessions(sessionsRes.sessions);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, severityFilter]);

  useEffect(() => {
    fetchSecurityData();
  }, [fetchSecurityData]);

  const handleRevokeSession = async (sessionId: string) => {
    if (!confirm('Revoke this session immediately?')) return;
    try {
      await api.admin.security.revokeSession(sessionId);
      fetchSecurityData();
    } catch (err: any) {
      alert(err.message || 'Failed to revoke session');
    }
  };

  const handleRevokeAllSessions = async () => {
    if (!confirm('Revoke all user sessions across the platform (except your current session)?')) return;
    try {
      const res = await api.admin.security.revokeAllSessions();
      alert(res.message || 'Sessions revoked');
      fetchSecurityData();
    } catch (err: any) {
      alert(err.message || 'Failed to revoke sessions');
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: '0 0 4px' }}>
            Security Center & Session Management
          </h1>
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
            Audit authentication attempts, CSRF validations, privilege access, and manage active sessions
          </p>
        </div>
        <button
          onClick={fetchSecurityData}
          style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600 }}
        >
          <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Active Sessions Card */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: '0 0 2px' }}>
              Active Authenticated Sessions ({sessions.length})
            </h3>
            <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>
              Live server-side sessions bound to HTTP-only cookies
            </p>
          </div>
          <button
            onClick={handleRevokeAllSessions}
            style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
          >
            Revoke All Other Sessions
          </button>
        </div>

        <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '10px 14px' }}>User</th>
                <th style={{ padding: '10px 14px' }}>Role</th>
                <th style={{ padding: '10px 14px' }}>Created</th>
                <th style={{ padding: '10px 14px' }}>Expires</th>
                <th style={{ padding: '10px 14px', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ fontWeight: 600, color: '#0f172a' }}>{s.username}</span>
                    {s.is_current && (
                      <span style={{ marginLeft: '8px', padding: '1px 6px', borderRadius: '4px', backgroundColor: '#e0e7ff', color: '#4338ca', fontSize: '10px', fontWeight: 700 }}>
                        CURRENT
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '10px 14px', textTransform: 'uppercase', color: '#64748b', fontSize: '11px', fontWeight: 600 }}>
                    {s.role}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#64748b' }}>{new Date(s.created_at).toLocaleString()}</td>
                  <td style={{ padding: '10px 14px', color: '#64748b' }}>{new Date(s.expires_at).toLocaleString()}</td>
                  <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                    {!s.is_current && (
                      <button
                        onClick={() => handleRevokeSession(s.id)}
                        style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #fecaca', background: '#ffffff', color: '#dc2626', cursor: 'pointer', fontSize: '11px', fontWeight: 600 }}
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Security Events Stream */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: 0 }}>
            Security Events & Incident Trail ({totalEvents})
          </h3>
          <select
            value={severityFilter}
            onChange={e => {
              setSeverityFilter(e.target.value);
              setPage(1);
            }}
            style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px' }}
          >
            <option value="all">All Severities</option>
            <option value="info">Info</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        {events.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
            No security incidents recorded.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                <th style={{ padding: '12px 18px' }}>Severity</th>
                <th style={{ padding: '12px 18px' }}>Event Type</th>
                <th style={{ padding: '12px 18px' }}>Request Path</th>
                <th style={{ padding: '12px 18px' }}>IP / Agent</th>
                <th style={{ padding: '12px 18px' }}>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {events.map(ev => (
                <tr key={ev.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '12px 18px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        backgroundColor: ev.severity === 'high' || ev.severity === 'critical' ? '#fee2e2' : ev.severity === 'medium' ? '#fef3c7' : '#f1f5f9',
                        color: ev.severity === 'high' || ev.severity === 'critical' ? '#b91c1c' : ev.severity === 'medium' ? '#b45309' : '#475569'
                      }}
                    >
                      {ev.severity}
                    </span>
                  </td>
                  <td style={{ padding: '12px 18px', fontWeight: 600, color: '#0f172a' }}>
                    {ev.event_type}
                  </td>
                  <td style={{ padding: '12px 18px', color: '#64748b', fontFamily: 'monospace', fontSize: '12px' }}>
                    {ev.request_path || 'N/A'}
                  </td>
                  <td style={{ padding: '12px 18px', color: '#64748b', fontSize: '12px' }}>
                    {ev.ip_address || 'unknown'}
                  </td>
                  <td style={{ padding: '12px 18px', color: '#64748b', fontSize: '12px' }}>
                    {new Date(ev.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
