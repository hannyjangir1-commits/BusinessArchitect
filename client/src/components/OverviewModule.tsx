import React, { useState } from 'react';
import { Project } from '../types';
import { LayoutDashboard, Save, GitFork, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface Props {
  project: Project;
  onUpdateProject: (data: any, createCopy: boolean) => Promise<void>;
  isLoading: boolean;
}

export const OverviewModule: React.FC<Props> = ({ project, onUpdateProject, isLoading }) => {
  const [name, setName] = useState(project.name);
  const [stage, setStage] = useState(project.stage);
  const [industry, setIndustry] = useState(project.industry || '');
  const [targetCustomers, setTargetCustomers] = useState(project.target_customers || '');
  const [description, setDescription] = useState(project.description || '');
  const [goals, setGoals] = useState(project.goals || '');
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = async (createCopy: boolean) => {
    setSavedSuccess(false);
    await onUpdateProject({
      name,
      stage,
      industry,
      target_customers: targetCustomers,
      description,
      goals
    }, createCopy);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card">
        <div className="card-header-row">
          <div className="card-title">
            <LayoutDashboard size={18} color="#6366f1" />
            <span>Executive Business Overview</span>
          </div>
          {savedSuccess && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontSize: 13, fontWeight: 600 }}>
              <CheckCircle2 size={16} /> Saved Successfully
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Project / Business Name</label>
            <input
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Business Stage</label>
            <select
              className="form-select"
              value={stage}
              onChange={(e) => setStage(e.target.value as any)}
            >
              <option value="Idea">Idea</option>
              <option value="MVP">MVP</option>
              <option value="Post-launch">Post-launch</option>
              <option value="Growth">Growth</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Industry & Sector</label>
            <input
              type="text"
              className="form-input"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Target ICP / Customer Segments</label>
            <input
              type="text"
              className="form-input"
              value={targetCustomers}
              onChange={(e) => setTargetCustomers(e.target.value)}
            />
          </div>
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label className="form-label">Business Description & Core Problem</label>
          <textarea
            className="form-textarea"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label className="form-label">Strategic Objectives & Milestones</label>
          <textarea
            className="form-textarea"
            rows={3}
            value={goals}
            onChange={(e) => setGoals(e.target.value)}
          />
        </div>

        {/* Existing Tech Stack summary if present */}
        {project.existing_stack && Object.keys(project.existing_stack).length > 0 && (
          <div style={{ marginTop: 18, padding: 14, background: 'var(--bg-subtle)', borderRadius: 8, border: '1px solid var(--border-color)' }}>
            <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8 }}>
              Active Technology Infrastructure
            </h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {Object.entries(project.existing_stack).flatMap(([cat, list]) =>
                list.map(t => (
                  <span
                    key={`${cat}-${t}`}
                    style={{
                      fontSize: 11.5,
                      fontWeight: 600,
                      background: 'rgba(99, 102, 241, 0.15)',
                      color: 'var(--primary)',
                      padding: '3px 8px',
                      borderRadius: 6
                    }}
                  >
                    {t} ({cat})
                  </span>
                ))
              )}
            </div>
          </div>
        )}

        {/* Option A vs Option B Confirmation Bar */}
        <div style={{ marginTop: 24, paddingTop: 18, borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 12.5 }}>
            <AlertTriangle size={16} color="#f59e0b" />
            <span>Select whether to update this project in-place or fork into a separate project.</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Option B: Fork */}
            <button
              onClick={() => handleSave(true)}
              className="btn-secondary"
              disabled={isLoading}
              title="Preserve this project and fork changes into a new project record"
            >
              <GitFork size={14} /> Option B: Fork New Project
            </button>

            {/* Option A: Replace */}
            <button
              onClick={() => handleSave(false)}
              className="btn-primary"
              disabled={isLoading}
              title="Replace existing project attributes in-place"
            >
              <Save size={14} /> Option A: Update This Project
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
