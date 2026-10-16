import React from 'react';
import { Project, ModuleDetail, IdeaValidatorData } from '../types';
import { CheckCircle2, Sparkles, AlertTriangle, FlaskConical, Target, Download, Loader2 } from 'lucide-react';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail<IdeaValidatorData> | null;
  onGenerate: () => Promise<void>;
  onExportPdf: () => void;
  isLoading: boolean;
  isGenerating?: boolean;
  generationProgress?: { stageText: string; progressPercent: number } | null;
  isGenerateDisabled?: boolean;
}

export const IdeaValidatorModule: React.FC<Props> = ({
  project,
  moduleDetail,
  onGenerate,
  onExportPdf,
  isLoading,
  isGenerating = false,
  generationProgress = null,
  isGenerateDisabled = false
}) => {
  const data = moduleDetail?.data;

  if (!data) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#ede9fe', color: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
          <CheckCircle2 size={28} />
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8 }}>
          Idea Validation Report Not Yet Generated
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 480, margin: '0 auto 20px auto' }}>
          Evaluate the market assumptions, ICP fit, differentiation moat, and risk mitigation roadmap for {project.name}.
        </p>
        <button
          onClick={onGenerate}
          className="btn-primary"
          disabled={isLoading || isGenerating || isGenerateDisabled}
          style={{ margin: '0 auto' }}
        >
          {isGenerating ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              {generationProgress ? `${generationProgress.stageText} (${generationProgress.progressPercent}%)` : 'Evaluating Feasibility...'}
            </>
          ) : (
            <>
              <Sparkles size={16} /> Run Idea Validator
            </>
          )}
        </button>
      </div>
    );
  }

  const score = data.overall_viability_score || 85;
  const scoreColor = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header bar without AI chat panel as per Rule #21 */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <CheckCircle2 size={22} />
          </div>
          <div className="module-titles">
            <h2>
              Idea Validator & Feasibility Report
              <span className="version-pill-dropdown">
                {moduleDetail.active_version_name || 'V1'}
              </span>
            </h2>
            <p>Empirical hypothesis testing, differentiation audit, and risk mitigation plan</p>
          </div>
        </div>

        <button onClick={onExportPdf} className="btn-secondary">
          <Download size={14} color="#6366f1" /> Export This Module (PDF)
        </button>
      </div>

      {/* Viability Score & Core Highlights Banner */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 28, padding: 24, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minWidth: 120 }}>
          <div style={{ fontSize: 36, fontWeight: 900, color: scoreColor }}>
            {score}<span style={{ fontSize: 18, color: '#94a3b8' }}>/100</span>
          </div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginTop: 2 }}>
            Viability Score
          </div>
        </div>

        <div style={{ flex: 1, minWidth: 260, borderLeft: '1px solid var(--border-color)', paddingLeft: 24 }}>
          <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)', marginBottom: 4 }}>
            Problem Urgency & Customer Fit
          </h4>
          <p style={{ fontSize: 13, color: 'var(--text-main)', lineHeight: 1.5 }}>
            {data.problem_clarity}
          </p>
          <div style={{ marginTop: 8, fontSize: 12, color: '#6366f1', fontWeight: 600 }}>
            ICP: {data.customer_fit}
          </div>
        </div>
      </div>

      {/* Key Strategic Pillars Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div className="card">
          <div className="card-title" style={{ color: '#6366f1' }}>
            <Target size={16} /> Value Proposition & Wedge
          </div>
          <p style={{ fontSize: 13, color: '#334155', marginTop: 10, lineHeight: 1.5 }}>
            {data.value_proposition}
          </p>
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #f1f5f9', fontSize: 12, color: '#64748b' }}>
            <b>Moat:</b> {data.differentiation}
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ color: '#0ea5e9' }}>
            <Sparkles size={16} /> Market Assumptions That Must Be True
          </div>
          <ul style={{ paddingLeft: 18, fontSize: 12.5, color: '#334155', marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(data.market_assumptions || []).map((assump, idx) => (
              <li key={idx} style={{ lineHeight: 1.4, color: 'var(--text-main)' }}>{assump}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* Risks & Mitigations Table */}
      <div className="card">
        <div className="card-title" style={{ color: '#ef4444', marginBottom: 14 }}>
          <AlertTriangle size={16} /> Critical Venture Risks & Mitigations
        </div>
        <div className="table-responsive">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th style={{ width: 280 }}>Risk Parameter</th>
                <th style={{ width: 100 }}>Severity</th>
                <th>Mitigation Strategy</th>
              </tr>
            </thead>
            <tbody>
              {(data.risks || []).map((r, idx) => (
                <tr key={idx}>
                  <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>{r.risk}</td>
                  <td>
                    <span className={`badge-priority ${r.severity.toLowerCase()}`}>
                      {r.severity}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-main)' }}>{r.mitigation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recommended Validation Experiments */}
      <div className="card">
        <div className="card-title" style={{ color: '#8b5cf6', marginBottom: 14 }}>
          <FlaskConical size={16} /> Actionable Validation Experiments
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
          {(data.validation_experiments || []).map((exp, idx) => (
            <div key={idx} style={{ background: 'var(--bg-subtle)', padding: 14, borderRadius: 8, border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>
                Experiment #{idx + 1}: {exp.experiment}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                <b>Metric:</b> {exp.metric}
              </div>
              <div style={{ fontSize: 12, color: '#10b981', fontWeight: 600, marginTop: 4 }}>
                <b>Target Criteria:</b> {exp.target_criteria}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
