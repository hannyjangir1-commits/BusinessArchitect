import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  Wrench, CheckCircle2, AlertTriangle,
  RefreshCw, Loader2, Power, Trash2, Calendar
} from 'lucide-react';

export const AdminMaintenancePage: React.FC = () => {
  const [status, setStatus] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [reason, setReason] = useState<string>('Scheduled system maintenance and upgrade');
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.admin.maintenance.getStatus();
      setStatus(res);
    } catch (e: any) {
      console.error(e);
      setMsg({ type: 'error', text: e.message || 'Failed to load maintenance status' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleToggle = async (enable: boolean) => {
    const actionText = enable ? 'ENABLE' : 'DISABLE';
    if (!confirm(`Are you sure you want to ${actionText} maintenance mode?`)) return;

    setActionLoading(true);
    setMsg(null);
    try {
      const res = await api.admin.maintenance.toggle(enable, reason);
      setMsg({ type: 'success', text: res.message });
      fetchStatus();
    } catch (err: any) {
      setMsg({ type: 'error', text: err.message || 'Failed to toggle maintenance mode' });
    } finally {
      setActionLoading(false);
    }
  };

  const handlePruneSessions = async () => {
    if (!confirm('Clean up and delete all expired user session records from the database?')) return;

    setActionLoading(true);
    setMsg(null);
    try {
      const res = await api.admin.maintenance.pruneSessions();
      setMsg({ type: 'success', text: res.message });
      fetchStatus();
    } catch (err: any) {
      setMsg({ type: 'error', text: err.message || 'Failed to prune expired sessions' });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Wrench size={26} color="#6366f1" />
            Maintenance Center
          </h1>
          <p style={{ margin: '6px 0 0', color: '#94a3b8', fontSize: '14px' }}>
            Control platform availability, trigger housekeeping routines, and clean up expired session artifacts safely.
          </p>
        </div>
        <button
          onClick={() => fetchStatus()}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: '#1e293b',
            color: '#f8fafc',
            border: '1px solid #334155',
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

      {msg && (
        <div
          style={{
            padding: '14px 18px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: msg.type === 'success' ? '#064e3b33' : '#7f1d1d33',
            border: `1px solid ${msg.type === 'success' ? '#059669' : '#dc2626'}`,
            color: msg.type === 'success' ? '#34d399' : '#f87171'
          }}
        >
          {msg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          {msg.text}
        </div>
      )}

      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
          <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
          Loading maintenance status...
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
          {/* Card 1: Maintenance Mode Switch */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '12px',
              border: '1px solid #1e293b',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Power size={20} color={status?.maintenance_mode_active ? '#ef4444' : '#10b981'} />
                  <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc' }}>
                    Platform Maintenance Mode
                  </h2>
                </div>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 12px',
                    borderRadius: '999px',
                    backgroundColor: status?.maintenance_mode_active ? '#7f1d1d33' : '#064e3b33',
                    border: `1px solid ${status?.maintenance_mode_active ? '#dc2626' : '#059669'}`,
                    color: status?.maintenance_mode_active ? '#f87171' : '#34d399',
                    fontSize: '11px',
                    fontWeight: 700,
                    textTransform: 'uppercase'
                  }}
                >
                  {status?.maintenance_mode_active ? 'ACTIVE' : 'NORMAL OPERATION'}
                </span>
              </div>

              <p style={{ margin: '0 0 16px', color: '#94a3b8', fontSize: '13px', lineHeight: '1.5' }}>
                When enabled, ordinary non-administrator requests are put on hold while system upgrades take place. Administrators retain full, uninterrupted access.
              </p>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px', fontWeight: 500 }}>
                  Reason / Announcement Note:
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f8fafc',
                    fontSize: '13px',
                    outline: 'none'
                  }}
                />
              </div>

              {status?.last_updated && (
                <div style={{ fontSize: '12px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Calendar size={13} />
                  Status Last Changed: {new Date(status.last_updated).toLocaleString()}
                </div>
              )}
            </div>

            <div style={{ marginTop: '24px' }}>
              {status?.maintenance_mode_active ? (
                <button
                  onClick={() => handleToggle(false)}
                  disabled={actionLoading}
                  style={{
                    width: '100%',
                    padding: '12px',
                    backgroundColor: '#059669',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    fontWeight: 600,
                    fontSize: '13px',
                    cursor: actionLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px'
                  }}
                >
                  {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Power size={16} />}
                  Disable Maintenance Mode (Resume Service)
                </button>
              ) : (
                <button
                  onClick={() => handleToggle(true)}
                  disabled={actionLoading}
                  style={{
                    width: '100%',
                    padding: '12px',
                    backgroundColor: '#dc2626',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    fontWeight: 600,
                    fontSize: '13px',
                    cursor: actionLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px'
                  }}
                >
                  {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Power size={16} />}
                  Enable Maintenance Mode
                </button>
              )}
            </div>
          </div>

          {/* Card 2: Session Pruning & Housekeeping */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '12px',
              border: '1px solid #1e293b',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Trash2 size={20} color="#f59e0b" />
                <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc' }}>
                  Expired Session Housekeeping
                </h2>
              </div>

              <p style={{ margin: '0 0 20px', color: '#94a3b8', fontSize: '13px', lineHeight: '1.5' }}>
                User sessions that have exceeded their designated expiration window are safely pruned from the database. Active and valid sessions are untouched.
              </p>

              <div
                style={{
                  padding: '20px',
                  backgroundColor: '#1e293b',
                  borderRadius: '10px',
                  border: '1px solid #334155',
                  textAlign: 'center',
                  marginBottom: '20px'
                }}
              >
                <div style={{ fontSize: '32px', fontWeight: 800, color: '#f8fafc', fontFamily: 'monospace' }}>
                  {status?.expired_sessions_pending_cleanup ?? 0}
                </div>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                  Expired Sessions Pending Deletion
                </div>
              </div>
            </div>

            <div>
              <button
                onClick={handlePruneSessions}
                disabled={actionLoading || (status?.expired_sessions_pending_cleanup ?? 0) === 0}
                style={{
                  width: '100%',
                  padding: '12px',
                  backgroundColor: (status?.expired_sessions_pending_cleanup ?? 0) === 0 ? '#334155' : '#f59e0b',
                  color: (status?.expired_sessions_pending_cleanup ?? 0) === 0 ? '#64748b' : '#000000',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: (status?.expired_sessions_pending_cleanup ?? 0) === 0 || actionLoading ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                Prune Expired Sessions Now
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
