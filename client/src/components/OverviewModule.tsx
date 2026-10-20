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
  const [budget, setBudget] = useState(project.budget || '');
  const [businessContext, setBusinessContext] = useState(project.business_context || '');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = async (createCopy: boolean) => {
    setSavedSuccess(false);
    setSaveError(null);
    try {
      await onUpdateProject({ name, stage, industry, target_customers: targetCustomers, description, goals, budget, business_context: businessContext }, createCopy);
      setSavedSuccess(true);
    } catch (error: any) {
      setSaveError(error.message || 'The project could not be saved.');
    }

  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {saveError && <div role="alert" className="card" style={{ color: 'var(--danger-text)' }}>{saveError}</div>}
      <div className="card">
        <div className="card-header-row">
          <div className="card-title">
            <LayoutDashboard size={18} color="var(--primary-text)" />
            <span>Executive Business Overview</span>
          </div>
          {savedSuccess && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--primary-text)', fontSize: 13, fontWeight: 600 }}>
              <CheckCircle2 size={16} /> Saved Successfully
            </div>
          )}
        </div>

        <div className="overview-fields" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div className="form-group">
            <label htmlFor="overview-name" className="form-label">Project / Business Name</label>
            <input id="overview-name"
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="overview-stage" className="form-label">Business Stage</label>
            <select id="overview-stage"
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
            <label htmlFor="overview-industry" className="form-label">Industry & Sector</label>
            <input id="overview-industry"
              type="text"
              className="form-input"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="overview-target" className="form-label">Target ICP / Customer Segments</label>
            <input id="overview-target"
              type="text"
              className="form-input"
              value={targetCustomers}
              onChange={(e) => setTargetCustomers(e.target.value)}
            />
          </div>
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="overview-description" className="form-label">Business Description & Core Problem</label>
          <textarea id="overview-description"
            className="form-textarea"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="overview-goals" className="form-label">Strategic Objectives & Milestones</label>
          <textarea id="overview-goals"
            className="form-textarea"
            rows={3}
            value={goals}
            onChange={(e) => setGoals(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="project-budget" className="form-label">Budget & runway</label>
          <input id="project-budget" className="form-input" value={budget} onChange={e => setBudget(e.target.value)} placeholder="Amount, currency, and spending limits" />
        </div>
        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="project-business-context" className="form-label">Team, constraints & existing work</label>
          <textarea id="project-business-context" className="form-textarea" rows={3} value={businessContext} onChange={e => setBusinessContext(e.target.value)} />
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
                      background: 'rgb(69 60 55 / 0.15)',
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
            <AlertTriangle size={16} color="var(--primary-text)" />
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
              <GitFork size={14} /> Save as new project
            </button>

            {/* Option A: Replace */}
            <button
              onClick={() => handleSave(false)}
              className="btn-primary"
              disabled={isLoading}
              title="Replace existing project attributes in-place"
            >
              <Save size={14} /> Save project
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
