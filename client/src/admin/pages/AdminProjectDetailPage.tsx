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
      <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
        <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
        <p style={{ margin: 0 }}>Loading project architecture diagnostics...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: '30px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '12px', color: '#991b1b' }}>
        <p>{error || 'Project not found'}</p>
        <button onClick={onBack} style={{ padding: '6px 12px', background: '#dc2626', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
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
        style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'none', border: 'none', color: '#6366f1', fontSize: '13px', fontWeight: 600, cursor: 'pointer', marginBottom: '20px' }}
      >
        <ArrowLeft size={16} /> Back to Projects Console
      </button>

      {/* Project Overview Card */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#0f172a', margin: 0 }}>{project.name}</h2>
              <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600, backgroundColor: '#f1f5f9', color: '#475569' }}>
                {project.stage}
              </span>
            </div>
            <div style={{ fontSize: '13px', color: '#64748b', marginTop: '6px' }}>
              Owner: <strong>{project.owner.username}</strong> ({project.owner.email || 'N/A'}) • Industry: {project.industry || 'General Tech'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '16px' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Active Module</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#6366f1' }}>{project.active_module}</div>
            </div>
          </div>
        </div>

        {project.description && (
          <p style={{ marginTop: '16px', fontSize: '13px', color: '#475569', lineHeight: 1.5, borderTop: '1px solid #f1f5f9', paddingTop: '16px', margin: '16px 0 0' }}>
            {project.description}
          </p>
        )}
      </div>

      {/* Modules Summary Grid */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={18} style={{ color: '#6366f1' }} />
          Saved Enterprise Modules ({modules.length})
        </h3>

        {modules.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>No modules have been generated for this project yet.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px' }}>
            {modules.map((m: any) => (
              <div key={m.id} style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px', backgroundColor: '#f8fafc' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                    {m.module_type.replace('_', ' ').toUpperCase()}
                  </span>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#6366f1', backgroundColor: '#e0e7ff', padding: '1px 6px', borderRadius: '4px' }}>
                    {m.version_count} / 5 vers
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>
                  Active: {m.latest_version_name || 'V1'}
                </div>
                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px' }}>
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
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckSquare size={16} style={{ color: '#0ea5e9' }} />
            Execution Roadmap Tasks ({task_stats.total})
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', textAlign: 'center' }}>
            <div style={{ padding: '12px', backgroundColor: '#fef3c7', borderRadius: '8px' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: '#b45309' }}>{task_stats.pending}</div>
              <div style={{ fontSize: '11px', color: '#92400e', fontWeight: 600 }}>Pending</div>
            </div>
            <div style={{ padding: '12px', backgroundColor: '#e0f2fe', borderRadius: '8px' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: '#0369a1' }}>{task_stats.in_progress}</div>
              <div style={{ fontSize: '11px', color: '#075985', fontWeight: 600 }}>In Progress</div>
            </div>
            <div style={{ padding: '12px', backgroundColor: '#dcfce7', borderRadius: '8px' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: '#15803d' }}>{task_stats.finished}</div>
              <div style={{ fontSize: '11px', color: '#166534', fontWeight: 600 }}>Finished</div>
            </div>
          </div>
        </div>

        {/* Copilot Activity */}
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageSquare size={16} style={{ color: '#8b5cf6' }} />
            Blueprint Copilot Chat
          </h4>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a' }}>
            {copilot_messages_count}
          </div>
          <p style={{ fontSize: '12px', color: '#64748b', margin: '4px 0 0' }}>
            Total interactive AI dialogue turns exchanged on this project
          </p>
        </div>
      </div>

      {/* Recent AI Operations */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
        <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={16} style={{ color: '#6366f1' }} />
          Recent AI Operations on this Project
        </h4>
        {recent_ai_operations.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>No AI generation operations recorded for this project.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {recent_ai_operations.map((op: any) => (
              <div key={op.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: '#f8fafc', borderRadius: '6px', fontSize: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontWeight: 700, color: '#0f172a' }}>{op.module_type.toUpperCase()}</span>
                  <span style={{ color: '#64748b' }}>({op.operation_type})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <span style={{ color: op.status === 'success' ? '#16a34a' : '#ef4444', fontWeight: 600 }}>{op.status}</span>
                  <span style={{ color: '#94a3b8' }}>{op.duration_ms}ms</span>
                  <span style={{ color: '#94a3b8' }}>{new Date(op.created_at).toLocaleTimeString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
