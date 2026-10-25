import React, { useState } from 'react';
import { Loader2, Sparkles, ChevronDown, ChevronRight } from 'lucide-react';
import { TechStackPlanningInputs } from '../types';

interface Props {
  initialValues?: Partial<TechStackPlanningInputs>;
  isGenerating: boolean;
  isDisabled: boolean;
  progress?: { stageText: string; progressPercent?: number } | null;
  onSubmit: (inputs: TechStackPlanningInputs) => Promise<void>;
  onCancel?: () => void;
}

const split = (value: string) => value.split(',').map((item) => item.trim()).filter(Boolean);

export const TechStackPlanningForm: React.FC<Props> = ({
  initialValues,
  isGenerating,
  isDisabled,
  progress,
  onSubmit,
  onCancel
}) => {
  const [solutionType, setSolutionType] = useState(initialValues?.solution_type || '');
  const [currentStack, setCurrentStack] = useState(initialValues?.current_stack || '');
  const [budget, setBudget] = useState(initialValues?.budget_constraint || '');
  const [experience, setExperience] = useState(initialValues?.team_experience || '');
  const [constraints, setConstraints] = useState(initialValues?.constraints || '');

  // Advanced technical preferences (optional disclosure)
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [languages, setLanguages] = useState((initialValues?.preferred_languages || []).join(', '));
  const [frameworks, setFrameworks] = useState((initialValues?.preferred_frameworks || []).join(', '));
  const [platforms, setPlatforms] = useState((initialValues?.target_platforms || []).join(', '));
  const [deployment, setDeployment] = useState(initialValues?.deployment_preference || '');
  const [database, setDatabase] = useState(initialValues?.database_preference || '');
  const [scale, setScale] = useState(initialValues?.expected_scale || '');
  const [dataSensitivity, setDataSensitivity] = useState(initialValues?.data_sensitivity || '');
  const [integrations, setIntegrations] = useState((initialValues?.required_integrations || []).join(', '));
  const [mustUse, setMustUse] = useState((initialValues?.must_use || []).join(', '));
  const [avoid, setAvoid] = useState((initialValues?.avoid || []).join(', '));

  const isManualWorkflow = solutionType.includes('Existing tools') || solutionType.includes('no custom software');

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    await onSubmit({
      solution_type: solutionType,
      preferred_languages: split(languages),
      preferred_frameworks: split(frameworks),
      current_stack: currentStack,
      target_platforms: split(platforms),
      deployment_preference: deployment,
      database_preference: database,
      expected_scale: scale,
      data_sensitivity: dataSensitivity,
      compliance_requirements: [],
      required_integrations: split(integrations),
      budget_constraint: budget,
      team_experience: experience,
      must_use: split(mustUse),
      avoid: split(avoid),
      constraints
    });
  };

  return (
    <form className="card" onSubmit={submit} style={{ display: 'grid', gap: 16, padding: 20 }}>
      <div>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-main)' }}>
          Technology preferences
        </h3>
        <p style={{ color: 'var(--text-muted)', margin: '6px 0 0', fontSize: 13 }}>
          Specify your operational tools, constraints, or preferences. For non-software businesses, you can choose existing tools like WhatsApp or spreadsheets without custom code.
        </p>
      </div>

      {/* Primary Basic Questions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
        <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
          <span style={{ fontWeight: 600 }}>Operational or Solution Type</span>
          <select
            className="form-select"
            value={solutionType}
            disabled={isDisabled || isGenerating}
            onChange={(event) => setSolutionType(event.target.value)}
          >
            <option value="">Choose how work will be performed</option>
            <option value="Existing tools / no custom software">Existing tools / no custom software (e.g. WhatsApp, Sheets, manual)</option>
            <option value="Internal business tool">Internal business tool / automation</option>
            <option value="Web application">Web application</option>
            <option value="Mobile application">Mobile application</option>
            <option value="Desktop application">Desktop application</option>
            <option value="Hardware or embedded system">Hardware or embedded system</option>
            <option value="Hybrid product">Hybrid product</option>
          </select>
        </label>

        <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
          <span style={{ fontWeight: 600 }}>Current Tools or Existing Stack</span>
          <input
            className="form-input"
            value={currentStack}
            disabled={isDisabled || isGenerating}
            onChange={(event) => setCurrentStack(event.target.value)}
            placeholder="e.g. WhatsApp, Excel, Square POS, or existing React app"
          />
        </label>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
        <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
          <span style={{ fontWeight: 600 }}>Budget or Cost Limit</span>
          <input
            className="form-input"
            value={budget}
            disabled={isDisabled || isGenerating}
            onChange={(event) => setBudget(event.target.value)}
            placeholder="e.g. $500 total, Free-tier only, or $2k/mo budget"
          />
        </label>

        <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
          <span style={{ fontWeight: 600 }}>Team Experience & Staffing</span>
          <input
            className="form-input"
            value={experience}
            disabled={isDisabled || isGenerating}
            onChange={(event) => setExperience(event.target.value)}
            placeholder="e.g. Solo founder, non-technical, or 2 junior devs"
          />
        </label>
      </div>

      <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
        <span style={{ fontWeight: 600 }}>Key Constraints or Intended Workflows</span>
        <input
          className="form-input"
          value={constraints}
          disabled={isDisabled || isGenerating}
          onChange={(event) => setConstraints(event.target.value)}
          placeholder="e.g. Must work on mobile phones, no servers to maintain, strict privacy"
        />
      </label>

      {/* Advanced Technical Preferences Disclosure */}
      <div style={{ border: '1px solid var(--border-color)', borderRadius: 8, overflow: 'hidden' }}>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          style={{
            width: '100%',
            padding: '10px 14px',
            background: 'var(--bg-subtle)',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--text-main)',
            cursor: 'pointer'
          }}
        >
          <span>Advanced Technical Preferences (Languages, Database, Deployment)</span>
          {showAdvanced ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>

        {showAdvanced && (
          <div style={{ padding: 14, display: 'grid', gap: 14, background: 'var(--bg-card)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
              <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                <span>Database Preference</span>
                <select
                  className="form-select"
                  value={database}
                  disabled={isDisabled || isGenerating}
                  onChange={(event) => setDatabase(event.target.value)}
                >
                  <option value="">Choose database preference</option>
                  <option value="No separate database needed">No separate database needed (files / sheets)</option>
                  <option value="Relational">Relational (PostgreSQL, SQLite, MySQL)</option>
                  <option value="Document">Document (MongoDB, DynamoDB)</option>
                  <option value="Existing database">Existing database</option>
                </select>
              </label>

              <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                <span>Deployment Preference</span>
                <select
                  className="form-select"
                  value={deployment}
                  disabled={isDisabled || isGenerating}
                  onChange={(event) => setDeployment(event.target.value)}
                >
                  <option value="">Choose deployment</option>
                  <option value="Offline or local">Offline or local (no cloud host)</option>
                  <option value="Managed cloud">Managed cloud (Render, Vercel, Supabase)</option>
                  <option value="Self-hosted">Self-hosted / VPS</option>
                  <option value="Hybrid">Hybrid</option>
                </select>
              </label>
            </div>

            {!isManualWorkflow && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
                  <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                    <span>Preferred Languages</span>
                    <input
                      className="form-input"
                      value={languages}
                      disabled={isDisabled || isGenerating}
                      onChange={(event) => setLanguages(event.target.value)}
                      placeholder="e.g. TypeScript, Python"
                    />
                  </label>

                  <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                    <span>Preferred Frameworks & Tools</span>
                    <input
                      className="form-input"
                      value={frameworks}
                      disabled={isDisabled || isGenerating}
                      onChange={(event) => setFrameworks(event.target.value)}
                      placeholder="e.g. React, FastAPI, Tailwind"
                    />
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
                  <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                    <span>Target Platforms</span>
                    <input
                      className="form-input"
                      value={platforms}
                      disabled={isDisabled || isGenerating}
                      onChange={(event) => setPlatforms(event.target.value)}
                      placeholder="e.g. Web, iOS, Android"
                    />
                  </label>

                  <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                    <span>Expected Scale</span>
                    <select
                      className="form-select"
                      value={scale}
                      disabled={isDisabled || isGenerating}
                      onChange={(event) => setScale(event.target.value)}
                    >
                      <option value="">Choose expected scale</option>
                      <option value="Prototype or pilot">Prototype or pilot (&lt; 100 users)</option>
                      <option value="Small production">Small production (100 - 10k users)</option>
                      <option value="Enterprise production">Enterprise production</option>
                      <option value="High traffic or global">High traffic / Global scale</option>
                    </select>
                  </label>
                </div>
              </>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                <span>Must Use</span>
                <input
                  className="form-input"
                  value={mustUse}
                  disabled={isDisabled || isGenerating}
                  onChange={(event) => setMustUse(event.target.value)}
                  placeholder="e.g. Stripe, WhatsApp Business API"
                />
              </label>

              <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}>
                <span>Avoid</span>
                <input
                  className="form-input"
                  value={avoid}
                  disabled={isDisabled || isGenerating}
                  onChange={(event) => setAvoid(event.target.value)}
                  placeholder="e.g. Kubernetes, complex microservices"
                />
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Footer Controls */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={isGenerating}>
            Cancel
          </button>
        )}
        <button
          type="submit"
          className="btn-primary"
          disabled={isDisabled || isGenerating}
          aria-live="polite"
        >
          {isGenerating ? (
            <span role="status" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Loader2 size={15} className="animate-spin" />
              {progress?.stageText || 'Generating technology stack…'}
              {progress?.progressPercent ? ` ${progress.progressPercent}%` : ''}
            </span>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={15} />
              Generate technology stack
            </span>
          )}
        </button>
      </div>
    </form>
  );
};
