import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  ArrowLeft, Layers, CheckSquare, MessageSquare,
  Cpu, Loader2
} from 'lucide-react';

interface AdminProjectDetailPageProps {
  projectId: string;
  onBack: () => void;
}

export const AdminProjectDetailPage: React.FC<AdminProjectDetailPageProps> = ({
  projectId,
  onBack
}) => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProject = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.admin.projects.get(projectId);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch project details');
      } finally {
        setLoading(false);
      }
    };
    fetchProject();
  }, [projectId]);

  if (loading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: 'var(--primary-text)' }} />
        <p style={{ margin: 0 }}>Loading project architecture diagnostics...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: '30px', backgroundColor: 'var(--bg-subtle)', border: '1px solid var(--bg-subtle)', borderRadius: '12px', color: 'var(--danger-text)' }}>
        <p>{error || 'Project not found'}</p>
        <button onClick={onBack} style={{ padding: '6px 12px', background: 'var(--danger-text)', color: 'var(--text-main)', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
          Back to Projects Console
        </button>
      </div>
    );
  }

  const { project, modules, task_stats, copilot_messages_count, recent_ai_operations } = data;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <button
        onClick={onBack}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'none', border: 'none', color: 'var(--primary-text)', fontSize: '13px', fontWeight: 600, cursor: 'pointer', marginBottom: '20px' }}
      >
        <ArrowLeft size={16} /> Back to Projects Console
      </button>

      {/* Project Overview Card */}
      <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '24px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>{project.name}</h2>
              <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, backgroundColor: 'var(--bg-subtle)', color: 'var(--text-main)' }}>
                {project.stage}
              </span>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '6px' }}>
              Owner: <strong>{project.owner.username}</strong> ({project.owner.email || 'N/A'}) • Industry: {project.industry || 'General Tech'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '16px' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Active Module</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--primary-text)' }}>{project.active_module}</div>
            </div>
          </div>
        </div>

        {project.description && (
          <p style={{ marginTop: '16px', fontSize: '13px', color: 'var(--text-main)', lineHeight: 1.5, borderTop: '1px solid var(--bg-subtle)', paddingTop: '16px', margin: '16px 0 0' }}>
            {project.description}
          </p>
        )}
      </div>

      {/* Modules Summary Grid */}
      <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '24px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={18} style={{ color: 'var(--primary-text)' }} />
          Saved Enterprise Modules ({modules.length})
        </h3>

        {modules.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: 0 }}>No modules have been generated for this project yet.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px' }}>
            {modules.map((m: any) => (
              <div key={m.id} style={{ border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px', backgroundColor: 'var(--bg-subtle)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-main)' }}>
                    {m.module_type.replace('_', ' ').toUpperCase()}
                  </span>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--primary-text)', backgroundColor: 'var(--bg-subtle)', padding: '1px 6px', borderRadius: '4px' }}>
                    {m.version_count} / 5 vers
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Active: {m.latest_version_name || 'V1'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Updated: {new Date(m.updated_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Roadmap & Copilot Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px', marginBottom: '24px' }}>
        {/* Task Breakdown */}
        <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckSquare size={16} style={{ color: 'var(--text-muted)' }} />
            Execution Roadmap Tasks ({task_stats.total})
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', textAlign: 'center' }}>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--primary-text)' }}>{task_stats.pending}</div>
              <div style={{ fontSize: '11px', color: 'var(--primary-text)', fontWeight: 600 }}>Pending</div>
            </div>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--primary-text)' }}>{task_stats.in_progress}</div>
              <div style={{ fontSize: '11px', color: 'var(--primary-text)', fontWeight: 600 }}>In Progress</div>
            </div>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: '8px' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--primary-text)' }}>{task_stats.finished}</div>
              <div style={{ fontSize: '11px', color: 'var(--primary-text)', fontWeight: 600 }}>Finished</div>
            </div>
          </div>
        </div>

        {/* Copilot Activity */}
        <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageSquare size={16} style={{ color: 'var(--primary-text)' }} />
            Blueprint Copilot Chat
          </h4>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)' }}>
            {copilot_messages_count}
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '4px 0 0' }}>
            Total interactive planning dialogue turns exchanged on this project
          </p>
        </div>
      </div>

      {/* Recent Generation Operations */}
      <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)' }}>
        <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={16} style={{ color: 'var(--primary-text)' }} />
          Recent Generation Operations on this Project
        </h4>
        {recent_ai_operations.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '12px', margin: 0 }}>No generation operations recorded for this project.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {recent_ai_operations.map((op: any) => (
              <div key={op.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--bg-subtle)', borderRadius: '6px', fontSize: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>{op.module_type.toUpperCase()}</span>
                  <span style={{ color: 'var(--text-muted)' }}>({op.operation_type})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <span style={{ color: op.status === 'success' ? 'var(--primary-text)' : 'var(--danger-text)', fontWeight: 600 }}>{op.status}</span>
                  <span style={{ color: 'var(--text-muted)' }}>{op.duration_ms}ms</span>
                  <span style={{ color: 'var(--text-muted)' }}>{new Date(op.created_at).toLocaleTimeString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
