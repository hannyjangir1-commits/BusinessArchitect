import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  FolderKanban, Search, Filter, Trash2, ArrowRightLeft,
  Loader2, RefreshCw, Layers, CheckSquare
} from 'lucide-react';

interface AdminProjectsPageProps {
  onSelectProject: (projectId: string) => void;
}

export const AdminProjectsPage: React.FC<AdminProjectsPageProps> = ({ onSelectProject }) => {
  const [projects, setProjects] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(15);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [transferModalProj, setTransferModalProj] = useState<any | null>(null);
  const [targetUsername, setTargetUsername] = useState<string>('');
  const [deleteModalProj, setDeleteModalProj] = useState<any | null>(null);
  const [confirmProjectName, setConfirmProjectName] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<boolean>(false);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.admin.projects.list({
        page,
        limit,
        search: search.trim() || undefined,
        stage: stageFilter !== 'all' ? stageFilter : undefined
      });
      setProjects(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch projects directory');
    } finally {
      setLoading(false);
    }
  }, [page, limit, search, stageFilter]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchProjects();
  };

  const handleTransfer = async () => {
    if (!transferModalProj || !targetUsername.trim()) return;
    setActionLoading(true);
    try {
      await api.admin.projects.transfer(transferModalProj.id, targetUsername.trim());
      setTransferModalProj(null);
      setTargetUsername('');
      fetchProjects();
    } catch (err: any) {
      alert(err.message || 'Failed to transfer project ownership');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteModalProj) return;
    if (confirmProjectName.trim() !== deleteModalProj.name) {
      alert('Confirmation project name does not match');
      return;
    }
    setActionLoading(true);
    try {
      await api.admin.projects.delete(deleteModalProj.id, confirmProjectName);
      setDeleteModalProj(null);
      setConfirmProjectName('');
      fetchProjects();
    } catch (err: any) {
      alert(err.message || 'Failed to delete project');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 4px' }}>
            Projects Console
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Inspect business architectures, module persistence, ownership transfers, and lifecycle governance
          </p>
        </div>
      </div>

      {error && (
        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--bg-subtle)', color: 'var(--danger-text)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* Toolbar */}
      <div style={{ background: 'var(--bg-card)', borderRadius: '10px', padding: '16px 20px', border: '1px solid var(--border-color)', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, maxWidth: '400px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search by project name or owner..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ width: '100%', padding: '8px 12px 8px 36px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', outline: 'none' }}
            />
          </div>
          <button type="submit" style={{ padding: '8px 14px', background: 'var(--bg-subtle)', color: 'var(--text-main)', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
            Search
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-muted)' }}>
            <Filter size={15} />
            <span>Stage:</span>
            <select
              value={stageFilter}
              onChange={e => {
                setStageFilter(e.target.value);
                setPage(1);
              }}
              style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', outline: 'none' }}
            >
              <option value="all">All Stages</option>
              <option value="Idea">Idea</option>
              <option value="MVP">MVP</option>
              <option value="Post-launch">Post-launch</option>
              <option value="Growth">Growth</option>
            </select>
          </div>

          <button
            onClick={fetchProjects}
            title="Refresh projects"
            style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
          >
            <RefreshCw size={15} style={{ color: 'var(--text-main)' }} />
          </button>
        </div>
      </div>

      {/* Projects Table */}
      <div style={{ background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: 'var(--primary-text)' }} />
            <p style={{ margin: 0 }}>Loading projects directory...</p>
          </div>
        ) : projects.length === 0 ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <FolderKanban size={32} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
            <p style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>No projects found matching criteria</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-main)', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                <th style={{ padding: '14px 18px' }}>Project Name</th>
                <th style={{ padding: '14px 18px' }}>Owner</th>
                <th style={{ padding: '14px 18px' }}>Stage</th>
                <th style={{ padding: '14px 18px' }}>Active Module</th>
                <th style={{ padding: '14px 18px' }}>Modules / Tasks</th>
                <th style={{ padding: '14px 18px' }}>Created</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {projects.map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--bg-subtle)' }}>
                  <td style={{ padding: '14px 18px' }}>
                    <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>{p.name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ID: {p.id}</div>
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{p.owner_username}</span>
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, backgroundColor: 'var(--bg-subtle)', color: 'var(--text-main)' }}>
                      {p.stage}
                    </span>
                  </td>
                  <td style={{ padding: '14px 18px', color: 'var(--text-muted)' }}>
                    {p.active_module}
                  </td>
                  <td style={{ padding: '14px 18px' }}>
                    <div style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                      <span title="Saved modules" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', color: 'var(--primary-text)' }}>
                        <Layers size={13} /> {p.modules_count}
                      </span>
                      <span>•</span>
                      <span title="Roadmap tasks" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', color: 'var(--text-muted)' }}>
                        <CheckSquare size={13} /> {p.tasks_count}
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '14px 18px', color: 'var(--text-muted)', fontSize: '12px' }}>
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        onClick={() => onSelectProject(p.id)}
                        style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--primary-text)', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}
                      >
                        Detail
                      </button>
                      <button
                        onClick={() => setTransferModalProj(p)}
                        title="Transfer Ownership"
                        style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)', cursor: 'pointer' }}
                      >
                        <ArrowRightLeft size={13} />
                      </button>
                      <button
                        onClick={() => setDeleteModalProj(p)}
                        title="Delete Project"
                        style={{ padding: '5px 8px', borderRadius: '4px', border: '1px solid var(--bg-subtle)', background: 'var(--bg-card)', color: 'var(--danger-text)', cursor: 'pointer' }}
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
        <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
          <div>Showing {projects.length} of {total} total projects</div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              style={{ padding: '5px 12px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-card)', cursor: page <= 1 ? 'not-allowed' : 'pointer', opacity: page <= 1 ? 0.5 : 1 }}
            >
              Previous
            </button>
            <span style={{ display: 'flex', alignItems: 'center', padding: '0 8px', fontWeight: 600 }}>
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              style={{ padding: '5px 12px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-card)', cursor: page >= totalPages ? 'not-allowed' : 'pointer', opacity: page >= totalPages ? 0.5 : 1 }}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Transfer Ownership Modal */}
      {transferModalProj && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgb(69 60 55 / 0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', width: '100%', maxWidth: '420px', padding: '24px', boxShadow: '0 20px 25px -5px rgb(69 60 55 / 0.1)' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px' }}>
              Transfer Ownership: {transferModalProj.name}
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
              Reassign project ownership to another existing user account.
            </p>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                New Owner Username
              </label>
              <input
                type="text"
                placeholder="Target username"
                value={targetUsername}
                onChange={e => setTargetUsername(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', outline: 'none' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button onClick={() => setTransferModalProj(null)} style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'var(--bg-card)', cursor: 'pointer' }}>
                Cancel
              </button>
              <button
                onClick={handleTransfer}
                disabled={actionLoading || !targetUsername.trim()}
                style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: 'var(--bg-subtle)', color: 'var(--text-main)', fontWeight: 600, cursor: 'pointer' }}
              >
                {actionLoading ? 'Transferring...' : 'Transfer Ownership'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Project Modal */}
      {deleteModalProj && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgb(69 60 55 / 0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', width: '100%', maxWidth: '440px', padding: '24px', boxShadow: '0 20px 25px -5px rgb(69 60 55 / 0.1)' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--danger-text)', marginBottom: '8px' }}>
              Permanently Delete Project
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-main)', marginBottom: '16px' }}>
              This will permanently delete project <strong>{deleteModalProj.name}</strong>, including all its modules, versions, and roadmap tasks.
            </p>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
                Type <strong>{deleteModalProj.name}</strong> to confirm:
              </label>
              <input
                type="text"
                value={confirmProjectName}
                onChange={e => setConfirmProjectName(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', outline: 'none' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button onClick={() => setDeleteModalProj(null)} style={{ padding: '8px 14px', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'var(--bg-card)', cursor: 'pointer' }}>
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={actionLoading || confirmProjectName !== deleteModalProj.name}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: confirmProjectName === deleteModalProj.name ? 'var(--danger-text)' : 'var(--border-color)',
                  color: 'var(--text-main)',
                  fontWeight: 600,
                  cursor: confirmProjectName === deleteModalProj.name ? 'pointer' : 'not-allowed'
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
