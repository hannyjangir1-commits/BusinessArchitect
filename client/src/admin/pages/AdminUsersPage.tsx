import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  Users, Search, Filter, Shield, AlertTriangle, CheckCircle,
  Ban, RotateCcw, Key, Trash2, ExternalLink, Loader2, RefreshCw
} from 'lucide-react';

interface AdminUsersPageProps {
  onSelectUser: (userId: string) => void;
}

export const AdminUsersPage: React.FC<AdminUsersPageProps> = ({ onSelectUser }) => {
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(15);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [suspendModalUser, setSuspendModalUser] = useState<any | null>(null);
  const [suspendReason, setSuspendReason] = useState<string>('');
  const [deleteModalUser, setDeleteModalUser] = useState<any | null>(null);
  const [confirmUsername, setConfirmUsername] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<boolean>(false);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.admin.users.list({
        page,
        limit,
        search: search.trim() || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined
      });
      setUsers(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch users directory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [page, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchUsers();
  };

  const handleSuspend = async () => {
    if (!suspendModalUser) return;
    setActionLoading(true);
    try {
      await api.admin.users.suspend(suspendModalUser.id, suspendReason || 'Administrative suspension');
      setSuspendModalUser(null);
      setSuspendReason('');
      fetchUsers();
    } catch (err: any) {
      alert(err.message || 'Failed to suspend user');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReactivate = async (user: any) => {
    if (!confirm(`Reactivate user account for '${user.username}'?`)) return;
    try {
      await api.admin.users.reactivate(user.id);
      fetchUsers();
    } catch (err: any) {
      alert(err.message || 'Failed to reactivate user');
    }
  };

  const handleRevokeSessions = async (user: any) => {
    if (!confirm(`Revoke all active sessions for '${user.username}'?`)) return;
    try {
      await api.admin.users.revokeSessions(user.id);
      alert(`Sessions revoked for ${user.username}`);
      fetchUsers();
    } catch (err: any) {
      alert(err.message || 'Failed to revoke sessions');
    }
  };

  const handleDelete = async () => {
    if (!deleteModalUser) return;
    if (confirmUsername.trim() !== deleteModalUser.username) {
      alert('Confirmation username does not match');
      return;
    }
    setActionLoading(true);
    try {
      await api.admin.users.delete(deleteModalUser.id, confirmUsername);
      setDeleteModalUser(null);
      setConfirmUsername('');
      fetchUsers();
    } catch (err: any) {
      alert(err.message || 'Failed to delete user');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: '0 0 4px' }}>
            User Management Directory
          </h1>
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
            Inspect accounts, manage administrative roles, enforce suspensions, and audit activity
          </p>
        </div>
      </div>

      {/* Toolbar: Search, Filters, Refresh */}
      <div style={{ background: '#ffffff', borderRadius: '10px', padding: '16px 20px', border: '1px solid #e2e8f0', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, maxWidth: '400px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Search by username or email..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px 8px 36px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '13px',
                outline: 'none'
              }}
            />
          </div>
          <button
            type="submit"
            style={{ padding: '8px 14px', background: '#6366f1', color: '#ffffff', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
          >
            Search
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#64748b' }}>
            <Filter size={15} />
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={e => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px', outline: 'none' }}
            >
              <option value="all">All Accounts</option>
              <option value="active">Active Only</option>
              <option value="suspended">Suspended Only</option>
            </select>
          </div>

          <button
            onClick={fetchUsers}
            title="Refresh users"
            style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
          >
            <RefreshCw size={15} style={{ color: '#475569' }} />
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div style={{ background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
            <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
            <p style={{ margin: 0, fontSize: '13px' }}>Loading user directory...</p>
          </div>
        ) : users.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
            <Users size={32} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
            <p style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>No users found matching query</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                <th style={{ padding: '14px 18px' }}>User</th>
                <th style={{ padding: '14px 18px' }}>Role</th>
                <th style={{ padding: '14px 18px' }}>Status</th>
                <th style={{ padding: '14px 18px' }}>Projects</th>
                <th style={{ padding: '14px 18px' }}>Last Active</th>
                <th style={{ padding: '14px 18px' }}>Created</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid #f1f5f9', transition: 'background-color 0.1s' }}>
                  <td style={{ padding: '14px 18px' }}>
                    <div style={{ fontWeight: 600, color: '#0f172a' }}>{u.username}</div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>{u.email}</div>
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: u.role === 'super_admin' ? '#ede9fe' : u.role.includes('admin') ? '#e0e7ff' : '#f1f5f9',
                        color: u.role === 'super_admin' ? '#6d28d9' : u.role.includes('admin') ? '#4338ca' : '#475569'
                      }}
                    >
                      {u.role.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    {u.is_suspended ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#ef4444', fontWeight: 600, fontSize: '12px' }}>
                        <Ban size={14} /> Suspended
                      </span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#16a34a', fontWeight: 600, fontSize: '12px' }}>
                        <CheckCircle size={14} /> Active
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '14px 18px', fontWeight: 600, color: '#334155' }}>
                    {u.projects_count}
                  </td>
                  <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                    {u.last_active_at ? new Date(u.last_active_at).toLocaleDateString() : 'Never'}
                  </td>
                  <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        onClick={() => onSelectUser(u.id)}
                        title="View user details"
                        style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', background: '#ffffff', color: '#4338ca', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}
                      >
                        Detail
                      </button>

                      {u.is_suspended ? (
                        <button
                          onClick={() => handleReactivate(u)}
                          title="Reactivate account"
                          style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid #bbf7d0', background: '#f0fdf4', color: '#16a34a', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}
                        >
                          Reactivate
                        </button>
                      ) : (
                        <button
                          onClick={() => setSuspendModalUser(u)}
                          title="Suspend account"
                          style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}
                        >
                          Suspend
                        </button>
                      )}

                      <button
                        onClick={() => handleRevokeSessions(u)}
                        title="Revoke active sessions"
                        style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', background: '#ffffff', color: '#475569', cursor: 'pointer' }}
                      >
                        <Key size={13} />
                      </button>

                      <button
                        onClick={() => setDeleteModalUser(u)}
                        title="Delete user permanently"
                        style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid #fecaca', background: '#ffffff', color: '#dc2626', cursor: 'pointer' }}
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

        {/* Pagination Footer */}
        <div style={{ padding: '14px 20px', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: '#64748b' }}>
          <div>
            Showing {users.length} of {total} registered users
          </div>
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

      {/* Suspend User Modal */}
      {suspendModalUser && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', width: '100%', maxWidth: '420px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
              Suspend User: {suspendModalUser.username}
            </h3>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px' }}>
              Suspending this user will immediately revoke all active sessions and block them from signing in or generating AI modules.
            </p>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                Suspension Reason
              </label>
              <input
                type="text"
                placeholder="e.g. Terms violation or suspicious activity"
                value={suspendReason}
                onChange={e => setSuspendReason(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px', outline: 'none' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setSuspendModalUser(null)}
                style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSuspend}
                disabled={actionLoading}
                style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: '#dc2626', color: '#ffffff', fontWeight: 600, cursor: 'pointer' }}
              >
                {actionLoading ? 'Suspending...' : 'Confirm Suspension'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete User Modal */}
      {deleteModalUser && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', width: '100%', maxWidth: '440px', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#dc2626', marginBottom: '8px' }}>
              Permanently Delete User Account
            </h3>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '16px' }}>
              This will permanently delete user <strong>{deleteModalUser.username}</strong>, including all projects, saved module versions, and sessions. This action cannot be undone.
            </p>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                Type <strong>{deleteModalUser.username}</strong> to confirm:
              </label>
              <input
                type="text"
                value={confirmUsername}
                onChange={e => setConfirmUsername(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px', outline: 'none' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setDeleteModalUser(null)}
                style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={actionLoading || confirmUsername !== deleteModalUser.username}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: confirmUsername === deleteModalUser.username ? '#dc2626' : '#cbd5e1',
                  color: '#ffffff',
                  fontWeight: 600,
                  cursor: confirmUsername === deleteModalUser.username ? 'pointer' : 'not-allowed'
                }}
              >
                {actionLoading ? 'Deleting...' : 'Permanently Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
