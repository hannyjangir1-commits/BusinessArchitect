import React from 'react';
import { Project, ModuleDetail, IdeaValidatorData } from '../types';
import { CheckCircle2, Sparkles, AlertTriangle, FlaskConical, Target, Download, Loader2 } from 'lucide-react';
import { ModuleLifecycleActions } from './ModuleLifecycleActions';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail<IdeaValidatorData> | null;
  onGenerate: () => Promise<void>;
  onDeleteModule?: () => Promise<void>;
  onDeleteVersion?: (versionId: string) => Promise<void>;
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
  onDeleteModule,
  onDeleteVersion,
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
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
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
              {generationProgress ? `${generationProgress.stageText} ${generationProgress.progressPercent}%` : 'Evaluating Feasibility...'}
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

  const score = data.overall_viability_score ?? 85;
  const scoreColor = score >= 80 ? 'var(--primary-text)' : score >= 60 ? 'var(--primary-text)' : 'var(--danger-text)';

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
            <p>Preliminary assessment and practical validation experiments</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ModuleLifecycleActions
            moduleTitle="Idea Validator"
            onCreateNew={onGenerate}
            onDeleteModule={onDeleteModule}
            onDeleteVersion={onDeleteVersion}
            versions={moduleDetail.versions || []}
            createLabel="Run New Validation"
            isBusy={isLoading || isGenerating}
            isCreateDisabled={isGenerateDisabled}
          />
          <button onClick={onExportPdf} className="btn-secondary">
            <Download size={14} color="var(--primary-text)" /> Export This Module (PDF)
          </button>
        </div>
      </div>

      {/* Viability Score & Core Highlights Banner */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 28, padding: 24, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minWidth: 140 }}>
          <div style={{ fontSize: 36, fontWeight: 900, color: scoreColor }}>
            {score}<span style={{ fontSize: 18, color: 'var(--text-muted)' }}>/100</span>
          </div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginTop: 2 }}>
            Viability Score
          </div>
          <span style={{ fontSize: 10.5, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-subtle)', color: 'var(--text-muted)', border: '1px solid var(--border-color)', marginTop: 6, textAlign: 'center' }}>
            Preliminary AI assessment — not market validation
          </span>
        </div>

        <div style={{ flex: 1, minWidth: 260, borderLeft: '1px solid var(--border-color)', paddingLeft: 24 }}>
          <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)', marginBottom: 4 }}>
            Problem Urgency & Customer Fit
          </h4>
          <p style={{ fontSize: 13, color: 'var(--text-main)', lineHeight: 1.5, margin: 0 }}>
            {data.problem_clarity}
          </p>
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--primary-text)', fontWeight: 600 }}>
            ICP: {data.customer_fit}
          </div>
          <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
            Score Rubric: Weighted across problem urgency (30%), customer willingness to pay (30%), feasibility & execution (25%), and practical differentiation (15%).
          </div>
        </div>
      </div>

      {(data.score_factors || data.evidence_note || (data.source_references || []).length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
          <section className="card" aria-labelledby="validator-score-breakdown-title">
            <div className="card-title" id="validator-score-breakdown-title">What the score reflects</div>
            {Object.entries(data.score_factors || {}).length > 0 ? (
              <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                {Object.entries(data.score_factors || {}).map(([factor, value]) => (
                  <div key={factor} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, fontSize: 12.5 }}>
                    <span style={{ color: 'var(--text-main)' }}>{factor.replaceAll('_', ' ')}</span>
                    <b style={{ color: 'var(--text-main)' }}>{value}/100</b>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 12.5, color: 'var(--text-muted)', marginBottom: 0 }}>No score factor breakdown was returned.</p>
            )}
          </section>
          <section className="card" aria-labelledby="validator-evidence-title">
            <div className="card-title" id="validator-evidence-title">Evidence and limitations</div>
            <p style={{ fontSize: 12.5, color: 'var(--text-main)', lineHeight: 1.5, marginTop: 10 }}>
              {data.evidence_note || 'Review the assumptions and source links before relying on the score.'}
            </p>
            {(data.source_references || []).length > 0 && (
              <ul style={{ paddingLeft: 18, fontSize: 12.5, marginBottom: 0 }}>
                {(data.source_references || []).map((source, idx) => (
                  <li key={`${source.url}-${idx}`} style={{ marginBottom: 6 }}>
                    <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}</a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {/* Key Strategic Pillars Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div className="card">
          <div className="card-title" style={{ color: 'var(--primary-text)' }}>
            <Target size={16} /> Value Proposition & Wedge
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-main)', marginTop: 10, lineHeight: 1.5 }}>
            {data.value_proposition}
          </p>
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--bg-subtle)', fontSize: 12, color: 'var(--text-muted)' }}>
            <b>Practical Differentiation / Advantage:</b> {data.differentiation}
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ color: 'var(--text-muted)' }}>
            <Sparkles size={16} /> Market Assumptions That Must Be True
          </div>
          <ul style={{ paddingLeft: 18, fontSize: 12.5, color: 'var(--text-main)', marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(data.market_assumptions || []).map((assump, idx) => (
              <li key={idx} style={{ lineHeight: 1.4, color: 'var(--text-main)' }}>{assump}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* Risks & Mitigations Table */}
      <div className="card">
        <div className="card-title" style={{ color: 'var(--danger-text)', marginBottom: 14 }}>
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
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
          <div className="card-title" style={{ color: 'var(--primary-text)', margin: 0 }}>
            <FlaskConical size={16} /> Actionable Validation Experiments
          </div>
          <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
            Ask about past actual behavior before hypothetical willingness to pay
          </span>
        </div>
        <p style={{ fontSize: 12.5, color: 'var(--text-muted)', marginBottom: 14 }}>
          Practical experiments to validate customer interest and behavior before committing significant capital.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
          {(data.validation_experiments || []).map((exp, idx) => (
            <div key={idx} style={{ background: 'var(--bg-subtle)', padding: 14, borderRadius: 8, border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)' }}>
                Experiment #{idx + 1}: {exp.experiment}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                <b>Metric:</b> {exp.metric}
              </div>
              <div style={{ fontSize: 12, color: 'var(--primary-text)', fontWeight: 600 }}>
                <b>Suggested threshold:</b> {exp.target_criteria}
              </div>
              {data.market_assumptions && data.market_assumptions[idx] && (
                <div style={{ fontSize: 11.5, color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', paddingTop: 6, marginTop: 4 }}>
                  <b>Assumption tested:</b> {data.market_assumptions[idx]}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
