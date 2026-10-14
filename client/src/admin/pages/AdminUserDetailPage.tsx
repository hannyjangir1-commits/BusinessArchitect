import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  ArrowLeft, FolderKanban, ShieldAlert,
  ClipboardList, CheckCircle, Ban, Loader2
} from 'lucide-react';

interface AdminUserDetailPageProps {
  userId: string;
  onBack: () => void;
  onSelectProject: (projectId: string) => void;
}

export const AdminUserDetailPage: React.FC<AdminUserDetailPageProps> = ({
  userId,
  onBack,
  onSelectProject
}) => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUser = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.admin.users.get(userId);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch user details');
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, [userId]);

  if (loading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
        <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
        <p style={{ margin: 0 }}>Loading user diagnostics...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: '30px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '12px', color: '#991b1b' }}>
        <p>{error || 'User not found'}</p>
        <button onClick={onBack} style={{ padding: '6px 12px', background: '#dc2626', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
          Back to Directory
        </button>
      </div>
    );
  }

  const { user, projects, security_events, audit_logs } = data;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      {/* Top back navigation */}
      <button
        onClick={onBack}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          background: 'none',
          border: 'none',
          color: '#6366f1',
          fontSize: '13px',
          fontWeight: 600,
          cursor: 'pointer',
          marginBottom: '20px'
        }}
      >
        <ArrowLeft size={16} /> Back to Users Directory
      </button>

      {/* User Header Profile Card */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                backgroundColor: '#e0e7ff',
                color: '#4338ca',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '22px',
                fontWeight: 800
              }}
            >
              {user.username.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#0f172a', margin: 0 }}>{user.username}</h2>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: user.role === 'super_admin' ? '#ede9fe' : '#e0e7ff',
                    color: user.role === 'super_admin' ? '#6d28d9' : '#4338ca'
                  }}
                >
                  {user.role.toUpperCase()}
                </span>
                {user.is_suspended ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#ef4444', fontSize: '12px', fontWeight: 600 }}>
                    <Ban size={14} /> Suspended
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#16a34a', fontSize: '12px', fontWeight: 600 }}>
                    <CheckCircle size={14} /> Active
                  </span>
                )}
              </div>
              <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>
                {user.email} • ID: <code style={{ backgroundColor: '#f1f5f9', padding: '1px 4px', borderRadius: '4px' }}>{user.id}</code>
              </div>
            </div>
          </div>
        </div>

        {/* Metadata Details Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginTop: '24px', paddingTop: '20px', borderTop: '1px solid #f1f5f9' }}>
          <div>
            <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Registered Date</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginTop: '2px' }}>{new Date(user.created_at).toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Last Active</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginTop: '2px' }}>
              {user.last_active_at ? new Date(user.last_active_at).toLocaleString() : 'Never'}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Active Sessions</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginTop: '2px' }}>{user.sessions_count} session(s)</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Total AI Operations</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginTop: '2px' }}>{user.ai_ops_count} operations</div>
          </div>
        </div>
      </div>

      {/* Projects Owned Card */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FolderKanban size={18} style={{ color: '#6366f1' }} />
          Projects Owned ({projects.length})
        </h3>

        {projects.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>This user has not created any business architecture projects yet.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
            {projects.map((p: any) => (
              <div
                key={p.id}
                onClick={() => onSelectProject(p.id)}
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  padding: '16px',
                  cursor: 'pointer',
                  transition: 'border-color 0.15s, box-shadow 0.15s'
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = '#6366f1';
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(99, 102, 241, 0.08)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = '#e2e8f0';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>{p.name}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#64748b' }}>
                  <span style={{ backgroundColor: '#f1f5f9', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>{p.stage}</span>
                  <span>•</span>
                  <span>Active: {p.active_module}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Security & Audit Events Side-by-Side */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px' }}>
        {/* Recent Security Incidents */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldAlert size={16} style={{ color: '#f59e0b' }} />
            Security Events
          </h4>
          {security_events.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>No security events recorded for this account.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {security_events.map((s: any) => (
                <div key={s.id} style={{ padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: '6px', fontSize: '12px', borderLeft: `3px solid ${s.severity === 'high' ? '#ef4444' : '#6366f1'}` }}>
                  <div style={{ fontWeight: 600, color: '#334155' }}>{s.event_type}</div>
                  <div style={{ color: '#94a3b8', fontSize: '11px' }}>{new Date(s.created_at).toLocaleString()} • IP: {s.ip_address || 'unknown'}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Administrative Audit Actions */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ClipboardList size={16} style={{ color: '#6366f1' }} />
            Admin Action History
          </h4>
          {audit_logs.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>No admin interventions recorded on this account.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {audit_logs.map((a: any) => (
                <div key={a.id} style={{ padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: '6px', fontSize: '12px' }}>
                  <div style={{ fontWeight: 600, color: '#334155' }}>{a.action} ({a.outcome})</div>
                  <div style={{ color: '#64748b', fontSize: '11px' }}>{a.reason || 'No reason provided'}</div>
                  <div style={{ color: '#94a3b8', fontSize: '10px', marginTop: '2px' }}>{new Date(a.created_at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
