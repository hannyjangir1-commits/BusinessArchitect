import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  UserCircle2, ShieldCheck, KeyRound, Clock,
  Calendar, CheckCircle2, AlertTriangle, Loader2, LogOut, Lock
} from 'lucide-react';
import { AdminChangePasswordModal } from '../AdminChangePasswordModal';

export const AdminAccountPage: React.FC = () => {
  const [adminUser, setAdminUser] = useState<any | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [showPasswordModal, setShowPasswordModal] = useState<boolean>(false);
  const [notificationMsg, setNotificationMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const res = await api.admin.auth.getMe();
      setAdminUser(res.user);
      setPermissions(res.permissions || []);
    } catch (e: any) {
      console.error(e);
      setNotificationMsg({ type: 'error', text: e.message || 'Failed to load administrator profile' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handlePasswordSuccess = () => {
    setShowPasswordModal(false);
    setNotificationMsg({ type: 'success', text: 'Password successfully rotated. Current session remains authenticated.' });
    fetchProfile();
  };

  const handleRevokeAllSessions = async () => {
    if (!confirm('Revoke all other active sessions for your administrator account?')) return;
    try {
      await api.admin.security.revokeAllSessions();
      setNotificationMsg({ type: 'success', text: 'All other administrator sessions have been terminated.' });
    } catch (err: any) {
      setNotificationMsg({ type: 'error', text: err.message || 'Failed to revoke other sessions' });
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <UserCircle2 size={26} color="#6366f1" />
          Administrator Account Profile
        </h1>
        <p style={{ margin: '6px 0 0', color: '#94a3b8', fontSize: '14px' }}>
          Identity details, role authorizations, session lifecycle, and credential rotation controls.
        </p>
      </div>

      {notificationMsg && (
        <div
          style={{
            padding: '14px 18px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: notificationMsg.type === 'success' ? '#064e3b33' : '#7f1d1d33',
            border: `1px solid ${notificationMsg.type === 'success' ? '#059669' : '#dc2626'}`,
            color: notificationMsg.type === 'success' ? '#34d399' : '#f87171'
          }}
        >
          {notificationMsg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          {notificationMsg.text}
        </div>
      )}

      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
          <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
          Loading administrator details...
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
          {/* Identity Card */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '12px',
              border: '1px solid #1e293b',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  backgroundColor: '#6366f122',
                  border: '1px solid #6366f144',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#818cf8',
                  fontWeight: 700,
                  fontSize: '20px'
                }}
              >
                {adminUser?.username?.[0]?.toUpperCase() || 'A'}
              </div>
              <div>
                <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>
                  {adminUser?.username || 'Administrator'}
                </h2>
                <span
                  style={{
                    display: 'inline-block',
                    marginTop: '4px',
                    padding: '2px 8px',
                    borderRadius: '999px',
                    backgroundColor: '#6366f122',
                    border: '1px solid #6366f155',
                    color: '#c7d2fe',
                    fontSize: '11px',
                    fontWeight: 600,
                    textTransform: 'uppercase'
                  }}
                >
                  Role: {adminUser?.role || 'super_admin'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #1e293b' }}>
                <span style={{ color: '#94a3b8' }}>Administrator ID</span>
                <span style={{ fontFamily: 'monospace', color: '#f8fafc' }}>{adminUser?.id || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #1e293b' }}>
                <span style={{ color: '#94a3b8' }}>Account Created</span>
                <span style={{ color: '#f8fafc' }}>
                  {adminUser?.created_at ? new Date(adminUser.created_at).toLocaleString() : 'Bootstrap'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #1e293b' }}>
                <span style={{ color: '#94a3b8' }}>Last Active</span>
                <span style={{ color: '#f8fafc' }}>
                  {adminUser?.last_active_at ? new Date(adminUser.last_active_at).toLocaleString() : 'Current Session'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0' }}>
                <span style={{ color: '#94a3b8' }}>Account Status</span>
                <span style={{ color: '#10b981', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <CheckCircle2 size={14} /> Active & Verified
                </span>
              </div>
            </div>

            <div style={{ marginTop: 'auto', paddingTop: '10px' }}>
              <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>
                Authorized Permissions ({permissions.length})
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                {permissions.map((p) => (
                  <span
                    key={p}
                    style={{
                      padding: '3px 8px',
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontFamily: 'monospace',
                      color: '#a5b4fc'
                    }}
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Security & Credential Rotation Card */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '12px',
              border: '1px solid #1e293b',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '20px'
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <KeyRound size={20} color="#f59e0b" />
                <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc' }}>
                  Security & Password Rotation
                </h2>
              </div>

              <div
                style={{
                  padding: '14px',
                  backgroundColor: '#1e293b',
                  borderRadius: '10px',
                  border: '1px solid #334155',
                  marginBottom: '16px',
                  fontSize: '12px',
                  lineHeight: '1.5',
                  color: '#cbd5e1'
                }}
              >
                <div style={{ fontWeight: 600, color: '#f8fafc', marginBottom: '4px' }}>
                  Argon2id Password Security Policy
                </div>
                Rotating your password will invalidate all other active sessions across browsers. Always ensure passwords meet complexity requirements (min 8 characters, letters & numbers).
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #1e293b' }}>
                  <span style={{ color: '#94a3b8' }}>Session Token</span>
                  <span style={{ color: '#10b981', fontWeight: 500 }}>HTTP-only Cookie (Secure)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #1e293b' }}>
                  <span style={{ color: '#94a3b8' }}>CSRF Defense</span>
                  <span style={{ color: '#10b981', fontWeight: 500 }}>Double-Submit Header Validated</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0' }}>
                  <span style={{ color: '#94a3b8' }}>Password Hashing</span>
                  <span style={{ fontFamily: 'monospace', color: '#c7d2fe' }}>Argon2id (RFC 9106)</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button
                onClick={() => setShowPasswordModal(true)}
                style={{
                  width: '100%',
                  padding: '11px',
                  backgroundColor: '#6366f1',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                <KeyRound size={16} />
                Rotate Administrator Password
              </button>

              <button
                onClick={handleRevokeAllSessions}
                style={{
                  width: '100%',
                  padding: '11px',
                  backgroundColor: '#1e293b',
                  color: '#ef4444',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
              >
                <LogOut size={16} />
                Terminate All Other Active Sessions
              </button>
            </div>
          </div>
        </div>
      )}

      {showPasswordModal && (
        <AdminChangePasswordModal
          onClose={() => setShowPasswordModal(false)}
          onSuccess={handlePasswordSuccess}
        />
      )}
    </div>
  );
};
