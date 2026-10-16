import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  UserCircle2, KeyRound, CheckCircle2, AlertTriangle, Loader2,
  LogOut, Users, Plus, Trash2, Ban,
  RefreshCw, Laptop, Globe, X
} from 'lucide-react';
import { AdminChangePasswordModal } from '../AdminChangePasswordModal';

export const AdminAccountPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'profile' | 'sessions' | 'admins'>('profile');
  const [adminUser, setAdminUser] = useState<any | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [showPasswordModal, setShowPasswordModal] = useState<boolean>(false);
  const [notificationMsg, setNotificationMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Sessions tab state
  const [sessions, setSessions] = useState<any[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState<boolean>(false);
  const [revokingSessionId, setRevokingSessionId] = useState<string | null>(null);

  // Admin accounts tab state
  const [adminAccounts, setAdminAccounts] = useState<any[]>([]);
  const [adminsLoading, setAdminsLoading] = useState<boolean>(false);
  const [showCreateAdminModal, setShowCreateAdminModal] = useState<boolean>(false);
  const [newAdminUsername, setNewAdminUsername] = useState<string>('');
  const [newAdminEmail, setNewAdminEmail] = useState<string>('');
  const [newAdminPassword, setNewAdminPassword] = useState<string>('');
  const [newAdminRole, setNewAdminRole] = useState<string>('operations_admin');
  const [createAdminLoading, setCreateAdminLoading] = useState<boolean>(false);

  // Edit role modal state
  const [editAdminUser, setEditAdminUser] = useState<any | null>(null);
  const [editRole, setEditRole] = useState<string>('operations_admin');
  const [editRoleLoading, setEditRoleLoading] = useState<boolean>(false);

  // Delete admin modal state
  const [deleteAdminUser, setDeleteAdminUser] = useState<any | null>(null);
  const [confirmAdminUsername, setConfirmAdminUsername] = useState<string>('');
  const [deleteAdminLoading, setDeleteAdminLoading] = useState<boolean>(false);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.admin.auth.getMe();
      setAdminUser(res.user);
      setPermissions(res.permissions || []);
    } catch (e: any) {
      setNotificationMsg({ type: 'error', text: e.message || 'Failed to load administrator profile' });
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const res = await api.admin.auth.getSessions();
      setSessions(Array.isArray(res) ? res : ((res as any)?.sessions || []));
    } catch (e: any) {
      setNotificationMsg({ type: 'error', text: e.message || 'Failed to load active sessions' });
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const fetchAdmins = useCallback(async () => {
    setAdminsLoading(true);
    try {
      const res = await api.admin.users.list({ role: 'admin', limit: 50 });
      setAdminAccounts(res.items || []);
    } catch (e: any) {
      setNotificationMsg({ type: 'error', text: e.message || 'Failed to load administrator accounts' });
    } finally {
      setAdminsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    if (activeTab === 'sessions') {
      fetchSessions();
    } else if (activeTab === 'admins') {
      fetchAdmins();
    }
  }, [activeTab, fetchSessions, fetchAdmins]);

  const handlePasswordSuccess = () => {
    setShowPasswordModal(false);
    setNotificationMsg({ type: 'success', text: 'Password successfully rotated. Current session remains active.' });
    fetchProfile();
  };

  const handleRevokeSingleSession = async (sessionId: string) => {
    if (!confirm('Revoke this active session? The user on that device will be signed out.')) return;
    setRevokingSessionId(sessionId);
    try {
      await api.admin.auth.revokeSession(sessionId);
      setNotificationMsg({ type: 'success', text: 'Session revoked successfully.' });
      fetchSessions();
    } catch (err: any) {
      setNotificationMsg({ type: 'error', text: err.message || 'Failed to revoke session' });
    } finally {
      setRevokingSessionId(null);
    }
  };

  const handleRevokeAllOtherSessions = async () => {
    if (!confirm('Revoke all other active sessions for your administrator account?')) return;
    try {
      const res = await api.admin.auth.revokeOtherSessions();
      setNotificationMsg({ type: 'success', text: res.message || 'All other administrator sessions have been terminated.' });
      fetchSessions();
    } catch (err: any) {
      setNotificationMsg({ type: 'error', text: err.message || 'Failed to revoke other sessions' });
    }
  };

  const handleCreateAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAdminUsername.trim() || !newAdminEmail.trim() || !newAdminPassword.trim()) {
      setNotificationMsg({ type: 'error', text: 'All fields are required.' });
      return;
    }
    setCreateAdminLoading(true);
    try {
      await api.admin.users.create({
        username: newAdminUsername.trim(),
        email: newAdminEmail.trim(),
        password: newAdminPassword,
        role: newAdminRole
      });
      setShowCreateAdminModal(false);
      setNewAdminUsername('');
      setNewAdminEmail('');
      setNewAdminPassword('');
      setNewAdminRole('operations_admin');
      setNotificationMsg({ type: 'success', text: 'Administrator account successfully created.' });
      fetchAdmins();
    } catch (err: any) {
      setNotificationMsg({ type: 'error', text: err.message || 'Failed to create administrator account' });
    } finally {
      setCreateAdminLoading(false);
    }
  };

  const handleUpdateAdminRole = async () => {
    if (!editAdminUser) return;
    setEditRoleLoading(true);
    try {
      await api.admin.users.update(editAdminUser.id, { role: editRole });
      setEditAdminUser(null);
      setNotificationMsg({ type: 'success', text: `Updated role for ${editAdminUser.username} to ${editRole}.` });
      fetchAdmins();
    } catch (err: any) {
      setNotificationMsg({ type: 'error', text: err.message || 'Failed to update administrator role' });
    } finally {
      setEditRoleLoading(false);
    }
  };

  const handleToggleSuspendAdmin = async (targetUser: any) => {
    const isSuspended = targetUser.is_suspended;
    const actionText = isSuspended ? 'reactivate' : 'suspend';
    if (!confirm(`Are you sure you want to ${actionText} administrator '${targetUser.username}'?`)) return;

    try {
      if (isSuspended) {
        await api.admin.users.reactivate(targetUser.id);
        setNotificationMsg({ type: 'success', text: `Reactivated administrator ${targetUser.username}.` });
      } else {
        await api.admin.users.suspend(targetUser.id, 'Administrative suspension');
        setNotificationMsg({ type: 'success', text: `Suspended administrator ${targetUser.username}.` });
      }
      fetchAdmins();
    } catch (err: any) {
      setNotificationMsg({ type: 'error', text: err.message || `Failed to ${actionText} administrator` });
    }
  };

  const handleDeleteAdmin = async () => {
    if (!deleteAdminUser) return;
    if (confirmAdminUsername.trim() !== deleteAdminUser.username) {
      alert('Confirmation username does not match');
      return;
    }
    setDeleteAdminLoading(true);
    try {
      await api.admin.users.delete(deleteAdminUser.id, confirmAdminUsername);
      setDeleteAdminUser(null);
      setConfirmAdminUsername('');
      setNotificationMsg({ type: 'success', text: `Deleted administrator account '${deleteAdminUser.username}'.` });
      fetchAdmins();
    } catch (err: any) {
      setNotificationMsg({ type: 'error', text: err.message || 'Failed to delete administrator account' });
    } finally {
      setDeleteAdminLoading(false);
    }
  };

  const isSuperAdmin = adminUser?.role === 'super_admin';

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <UserCircle2 size={26} color="#6366f1" />
          Administrator Account & Access Control
        </h1>
        <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: '13px' }}>
          Identity profile, role permissions, active session management, and multi-administrator governance.
        </p>
      </div>

      {notificationMsg && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: notificationMsg.type === 'success' ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${notificationMsg.type === 'success' ? '#bbf7d0' : '#fecaca'}`,
            color: notificationMsg.type === 'success' ? '#166534' : '#991b1b'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {notificationMsg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            <span>{notificationMsg.text}</span>
          </div>
          <button
            onClick={() => setNotificationMsg(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', gap: '24px' }}>
        <button
          onClick={() => setActiveTab('profile')}
          style={{
            padding: '12px 4px',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'profile' ? '2px solid #6366f1' : '2px solid transparent',
            color: activeTab === 'profile' ? '#6366f1' : '#64748b',
            fontWeight: activeTab === 'profile' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <UserCircle2 size={16} />
          Profile & Security
        </button>

        <button
          onClick={() => setActiveTab('sessions')}
          style={{
            padding: '12px 4px',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'sessions' ? '2px solid #6366f1' : '2px solid transparent',
            color: activeTab === 'sessions' ? '#6366f1' : '#64748b',
            fontWeight: activeTab === 'sessions' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Globe size={16} />
          Active Sessions
        </button>

        {isSuperAdmin && (
          <button
            onClick={() => setActiveTab('admins')}
            style={{
              padding: '12px 4px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'admins' ? '2px solid #6366f1' : '2px solid transparent',
              color: activeTab === 'admins' ? '#6366f1' : '#64748b',
              fontWeight: activeTab === 'admins' ? 700 : 500,
              fontSize: '14px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Users size={16} />
            Administrator Accounts
          </button>
        )}
      </div>

      {/* TAB 1: Profile & Security */}
      {activeTab === 'profile' && (
        <>
          {loading ? (
            <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
              <Loader2 size={32} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
              Loading administrator details...
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
              {/* Identity Card */}
              <div
                style={{
                  backgroundColor: '#ffffff',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '20px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div
                    style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '12px',
                      backgroundColor: '#e0e7ff',
                      border: '1px solid #c7d2fe',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#4338ca',
                      fontWeight: 800,
                      fontSize: '20px'
                    }}
                  >
                    {adminUser?.username?.[0]?.toUpperCase() || 'A'}
                  </div>
                  <div>
                    <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#0f172a' }}>
                      {adminUser?.username || 'Administrator'}
                    </h2>
                    <span
                      style={{
                        display: 'inline-block',
                        marginTop: '4px',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor: '#e0e7ff',
                        color: '#4338ca',
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase'
                      }}
                    >
                      {adminUser?.role?.replace('_', ' ') || 'Super Admin'}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: '#64748b' }}>Administrator ID</span>
                    <span style={{ fontFamily: 'monospace', color: '#0f172a', fontWeight: 600 }}>{adminUser?.id || '—'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: '#64748b' }}>Email</span>
                    <span style={{ color: '#0f172a', fontWeight: 500 }}>{adminUser?.email || 'N/A'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: '#64748b' }}>Account Created</span>
                    <span style={{ color: '#0f172a' }}>
                      {adminUser?.created_at ? new Date(adminUser.created_at).toLocaleString() : 'System Seed'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: '#64748b' }}>Last Active</span>
                    <span style={{ color: '#0f172a' }}>
                      {adminUser?.last_active_at ? new Date(adminUser.last_active_at).toLocaleString() : 'Current Session'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0' }}>
                    <span style={{ color: '#64748b' }}>Account Status</span>
                    <span style={{ color: '#16a34a', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={14} /> Active
                    </span>
                  </div>
                </div>

                <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid #f1f5f9' }}>
                  <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 700, textTransform: 'uppercase' }}>
                    Authorized Permissions ({permissions.length})
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                    {permissions.map((p) => (
                      <span
                        key={p}
                        style={{
                          padding: '3px 8px',
                          backgroundColor: '#f1f5f9',
                          border: '1px solid #e2e8f0',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontFamily: 'monospace',
                          color: '#475569'
                        }}
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Password & Security Card */}
              <div
                style={{
                  backgroundColor: '#ffffff',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '20px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                    <KeyRound size={20} color="#6366f1" />
                    <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#0f172a' }}>
                      Security & Password Rotation
                    </h2>
                  </div>

                  <div
                    style={{
                      padding: '14px',
                      backgroundColor: '#f8fafc',
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0',
                      marginBottom: '16px',
                      fontSize: '12px',
                      lineHeight: '1.5',
                      color: '#475569'
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                      Argon2id Secure Password Standard
                    </div>
                    Rotate your administrator password periodically. All operations require authenticated HTTP-only session tokens and double-submit CSRF defense.
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                      <span style={{ color: '#64748b' }}>Session Cookie</span>
                      <span style={{ color: '#16a34a', fontWeight: 600 }}>HTTP-only & SameSite</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f1f5f9' }}>
                      <span style={{ color: '#64748b' }}>CSRF Protection</span>
                      <span style={{ color: '#16a34a', fontWeight: 600 }}>Double-Submit Token Enforced</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0' }}>
                      <span style={{ color: '#64748b' }}>Password Hash Algorithm</span>
                      <span style={{ fontFamily: 'monospace', color: '#4338ca', fontWeight: 600 }}>Argon2id (RFC 9106)</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <button
                    onClick={() => setShowPasswordModal(true)}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      backgroundColor: '#6366f1',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '6px',
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
                    Change Administrator Password
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* TAB 2: Active Sessions */}
      {activeTab === 'sessions' && (
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: '0 0 4px' }}>
                Active Administrator Sessions
              </h3>
              <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
                Manage live authentication tokens registered to your account across browsers and devices.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={fetchSessions}
                style={{ padding: '6px 12px', background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600 }}
              >
                <RefreshCw size={13} className={sessionsLoading ? 'spin-animate' : ''} />
                Refresh
              </button>
              <button
                onClick={handleRevokeAllOtherSessions}
                style={{ padding: '6px 14px', background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600 }}
              >
                <LogOut size={13} />
                Terminate Other Sessions
              </button>
            </div>
          </div>

          {sessionsLoading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
              <Loader2 size={24} className="spin-animate" style={{ margin: '0 auto 8px', color: '#6366f1' }} />
              Loading active sessions...
            </div>
          ) : sessions.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '13px' }}>No active sessions found.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Device / Browser</th>
                  <th style={{ padding: '12px 16px' }}>IP Address</th>
                  <th style={{ padding: '12px 16px' }}>Created</th>
                  <th style={{ padding: '12px 16px' }}>Expires</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Laptop size={16} style={{ color: '#6366f1', flexShrink: 0 }} />
                        <span style={{ color: '#0f172a', fontWeight: 600, fontSize: '12px', maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.user_agent}>
                          {s.user_agent || 'Unknown Client'}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'monospace', color: '#475569' }}>
                      {s.ip_address || '127.0.0.1'}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b', fontSize: '12px' }}>
                      {new Date(s.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b', fontSize: '12px' }}>
                      {new Date(s.expires_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {s.is_current ? (
                        <span style={{ padding: '2px 8px', borderRadius: '4px', backgroundColor: '#dcfce7', color: '#15803d', fontSize: '11px', fontWeight: 700 }}>
                          Current Device
                        </span>
                      ) : (
                        <span style={{ padding: '2px 8px', borderRadius: '4px', backgroundColor: '#f1f5f9', color: '#475569', fontSize: '11px', fontWeight: 600 }}>
                          Active
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      {!s.is_current && (
                        <button
                          onClick={() => handleRevokeSingleSession(s.id)}
                          disabled={revokingSessionId === s.id}
                          style={{
                            padding: '4px 10px',
                            borderRadius: '4px',
                            border: '1px solid #fecaca',
                            backgroundColor: '#fff1f2',
                            color: '#b91c1c',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          {revokingSessionId === s.id ? 'Revoking...' : 'Revoke'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* TAB 3: Multiple Administrator Accounts (Super Admin only) */}
      {activeTab === 'admins' && isSuperAdmin && (
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: '0 0 4px' }}>
                Administrator Accounts Directory
              </h3>
              <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
                Provision, inspect, modify roles, or remove administrator staff accounts.
              </p>
            </div>
            <button
              onClick={() => setShowCreateAdminModal(true)}
              style={{
                padding: '8px 16px',
                backgroundColor: '#6366f1',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                fontWeight: 600,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Plus size={16} />
              Create Administrator
            </button>
          </div>

          {adminsLoading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
              <Loader2 size={24} className="spin-animate" style={{ margin: '0 auto 8px', color: '#6366f1' }} />
              Loading administrators...
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Administrator</th>
                  <th style={{ padding: '12px 16px' }}>Role</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                  <th style={{ padding: '12px 16px' }}>Created</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {adminAccounts.map(adm => (
                  <tr key={adm.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 700, color: '#0f172a' }}>{adm.username}</div>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>{adm.email}</div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: adm.role === 'super_admin' ? '#ede9fe' : '#e0e7ff',
                          color: adm.role === 'super_admin' ? '#6d28d9' : '#4338ca'
                        }}
                      >
                        {adm.role.replace('_', ' ').toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {adm.is_suspended ? (
                        <span style={{ color: '#ef4444', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}>
                          <Ban size={13} /> Suspended
                        </span>
                      ) : (
                        <span style={{ color: '#16a34a', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}>
                          <CheckCircle2 size={13} /> Active
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b', fontSize: '12px' }}>
                      {new Date(adm.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          onClick={() => {
                            setEditAdminUser(adm);
                            setEditRole(adm.role);
                          }}
                          style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            border: '1px solid #cbd5e1',
                            backgroundColor: '#ffffff',
                            color: '#334155',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          Role
                        </button>
                        <button
                          onClick={() => handleToggleSuspendAdmin(adm)}
                          style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            border: '1px solid #fde68a',
                            backgroundColor: adm.is_suspended ? '#ecfdf5' : '#fffbeb',
                            color: adm.is_suspended ? '#059669' : '#d97706',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          {adm.is_suspended ? 'Reactivate' : 'Suspend'}
                        </button>
                        <button
                          onClick={() => {
                            setDeleteAdminUser(adm);
                            setConfirmAdminUsername('');
                          }}
                          style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            border: '1px solid #fecaca',
                            backgroundColor: '#fff1f2',
                            color: '#b91c1c',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* MODAL: Create Administrator */}
      {showCreateAdminModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', width: '440px', maxWidth: '90%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#0f172a' }}>Create Administrator</h3>
              <button onClick={() => setShowCreateAdminModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateAdmin} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>Username</label>
                <input
                  type="text"
                  required
                  value={newAdminUsername}
                  onChange={e => setNewAdminUsername(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>Email</label>
                <input
                  type="email"
                  required
                  value={newAdminEmail}
                  onChange={e => setNewAdminEmail(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>Password (min 8 characters)</label>
                <input
                  type="password"
                  required
                  value={newAdminPassword}
                  onChange={e => setNewAdminPassword(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>Role</label>
                <select
                  value={newAdminRole}
                  onChange={e => setNewAdminRole(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                >
                  <option value="super_admin">Super Admin</option>
                  <option value="operations_admin">Operations Admin</option>
                  <option value="security_admin">Security Admin</option>
                  <option value="support_admin">Support Admin</option>
                  <option value="auditor">Auditor</option>
                </select>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateAdminModal(false)}
                  style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: 'pointer', fontSize: '13px' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createAdminLoading}
                  style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: '#6366f1', color: '#ffffff', fontWeight: 600, cursor: 'pointer', fontSize: '13px' }}
                >
                  {createAdminLoading ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Edit Admin Role */}
      {editAdminUser && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', width: '400px', maxWidth: '90%' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: '18px', fontWeight: 800, color: '#0f172a' }}>
              Change Role: {editAdminUser.username}
            </h3>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '6px' }}>Select New Role</label>
              <select
                value={editRole}
                onChange={e => setEditRole(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
              >
                <option value="super_admin">Super Admin</option>
                <option value="operations_admin">Operations Admin</option>
                <option value="security_admin">Security Admin</option>
                <option value="support_admin">Support Admin</option>
                <option value="auditor">Auditor</option>
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setEditAdminUser(null)}
                style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: 'pointer', fontSize: '13px' }}
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateAdminRole}
                disabled={editRoleLoading}
                style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: '#6366f1', color: '#ffffff', fontWeight: 600, cursor: 'pointer', fontSize: '13px' }}
              >
                {editRoleLoading ? 'Saving...' : 'Save Role'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Delete Admin Confirmation */}
      {deleteAdminUser && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', width: '420px', maxWidth: '90%' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: '18px', fontWeight: 800, color: '#dc2626' }}>
              Confirm Administrator Deletion
            </h3>
            <p style={{ fontSize: '13px', color: '#475569', lineHeight: 1.5, margin: '0 0 14px' }}>
              This will permanently revoke all access and delete administrator account <strong>{deleteAdminUser.username}</strong>.
            </p>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
                Type <strong>{deleteAdminUser.username}</strong> to confirm:
              </label>
              <input
                type="text"
                value={confirmAdminUsername}
                onChange={e => setConfirmAdminUsername(e.target.value)}
                placeholder={deleteAdminUser.username}
                style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setDeleteAdminUser(null)}
                style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: 'pointer', fontSize: '13px' }}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAdmin}
                disabled={deleteAdminLoading || confirmAdminUsername.trim() !== deleteAdminUser.username}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#dc2626',
                  color: '#ffffff',
                  fontWeight: 600,
                  cursor: deleteAdminLoading || confirmAdminUsername.trim() !== deleteAdminUser.username ? 'not-allowed' : 'pointer',
                  opacity: confirmAdminUsername.trim() !== deleteAdminUser.username ? 0.5 : 1,
                  fontSize: '13px'
                }}
              >
                {deleteAdminLoading ? 'Deleting...' : 'Delete Administrator'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Password Rotation Modal */}
      {showPasswordModal && (
        <AdminChangePasswordModal
          onClose={() => setShowPasswordModal(false)}
          onSuccess={handlePasswordSuccess}
        />
      )}
    </div>
  );
};
