import React, { useState } from 'react';
import { Project } from '../types';
import { LayoutDashboard, Save, Copy, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';

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
  const [isSaving, setIsSaving] = useState(false);

  const isDirty = (
    name !== project.name ||
    stage !== project.stage ||
    industry !== (project.industry || '') ||
    targetCustomers !== (project.target_customers || '') ||
    description !== (project.description || '') ||
    goals !== (project.goals || '') ||
    budget !== (project.budget || '') ||
    businessContext !== (project.business_context || '')
  );

  const handleFieldChange = <T,>(setter: React.Dispatch<React.SetStateAction<T>>, val: T) => {
    setter(val);
    setSavedSuccess(false);
    setSaveError(null);
  };

  const handleSave = async (createCopy: boolean) => {
    setSavedSuccess(false);
    setSaveError(null);
    setIsSaving(true);
    try {
      await onUpdateProject({
        name,
        stage,
        industry,
        target_customers: targetCustomers,
        description,
        goals,
        budget,
        business_context: businessContext
      }, createCopy);
      setSavedSuccess(true);
    } catch (error: any) {
      setSaveError(error.message || 'The project could not be saved.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {saveError && <div role="alert" className="card" style={{ color: 'var(--danger-text)' }}>{saveError}</div>}
      <div className="card">
        <div className="card-header-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <LayoutDashboard size={20} color="var(--primary-text)" />
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>Project Overview</h2>
          </div>
          <div>
            {isSaving ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)', fontSize: 13 }}>
                <Loader2 size={15} className="animate-spin" /> Saving changes...
              </div>
            ) : savedSuccess && !isDirty ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--primary-text)', fontSize: 13, fontWeight: 600 }}>
                <CheckCircle2 size={16} /> All changes saved
              </div>
            ) : isDirty ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)', fontSize: 13 }}>
                Unsaved changes
              </div>
            ) : null}
          </div>
        </div>

        <div className="overview-fields" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div className="form-group">
            <label htmlFor="overview-name" className="form-label">Project / Business Name</label>
            <input
              id="overview-name"
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => handleFieldChange(setName, e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="overview-stage" className="form-label">Business Stage</label>
            <select
              id="overview-stage"
              className="form-select"
              value={stage}
              onChange={(e) => handleFieldChange(setStage, e.target.value as any)}
            >
              <option value="Idea">Idea</option>
              <option value="MVP">MVP</option>
              <option value="Post-launch">Post-launch</option>
              <option value="Growth">Growth</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="overview-industry" className="form-label">Industry & Sector</label>
            <input
              id="overview-industry"
              type="text"
              className="form-input"
              value={industry}
              onChange={(e) => handleFieldChange(setIndustry, e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="overview-target" className="form-label">Target ICP / Customer Segments</label>
            <input
              id="overview-target"
              type="text"
              className="form-input"
              value={targetCustomers}
              onChange={(e) => handleFieldChange(setTargetCustomers, e.target.value)}
            />
          </div>
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="overview-description" className="form-label">Business Description & Core Problem</label>
          <textarea
            id="overview-description"
            className="form-textarea"
            rows={3}
            value={description}
            onChange={(e) => handleFieldChange(setDescription, e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="overview-goals" className="form-label">Strategic Objectives & Milestones</label>
          <textarea
            id="overview-goals"
            className="form-textarea"
            rows={3}
            value={goals}
            onChange={(e) => handleFieldChange(setGoals, e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="project-budget" className="form-label">Budget & Runway</label>
          <input
            id="project-budget"
            className="form-input"
            value={budget}
            onChange={(e) => handleFieldChange(setBudget, e.target.value)}
            placeholder="Amount, currency, and spending limits (e.g. $5,000 bootstrapped, or 10k EUR runway)"
          />
        </div>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label htmlFor="project-business-context" className="form-label">Team, Constraints & Existing Work</label>
          <textarea
            id="project-business-context"
            className="form-textarea"
            rows={3}
            value={businessContext}
            onChange={(e) => handleFieldChange(setBusinessContext, e.target.value)}
            placeholder="Operating constraints, solo founder vs team, current operational tools..."
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

        {/* Action Controls & Explanation */}
        <div style={{ marginTop: 24, paddingTop: 18, borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, color: 'var(--text-muted)', fontSize: 12.5, maxWidth: 480, lineHeight: 1.45 }}>
            <AlertTriangle size={16} color="var(--primary-text)" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>
              Saving updates this project directly. Creating a copy duplicates all project details, versions, and roadmap tasks into a new project while starting a fresh Copilot conversation.
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Secondary: Create a copy */}
            <button
              type="button"
              onClick={() => handleSave(true)}
              className="btn-secondary"
              disabled={isLoading || isSaving}
              title="Duplicate project details, versions, and tasks into a new project record"
            >
              <Copy size={14} /> Create a copy
            </button>

            {/* Primary: Save changes */}
            <button
              type="button"
              onClick={() => handleSave(false)}
              className="btn-primary"
              disabled={isLoading || isSaving || !isDirty}
              title="Save changes directly to this project"
            >
              {isSaving ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> Saving...
                </>
              ) : (
                <>
                  <Save size={14} /> Save changes
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
