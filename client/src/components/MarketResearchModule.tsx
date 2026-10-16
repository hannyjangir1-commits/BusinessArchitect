import React from 'react';
import { Project, ModuleDetail, MarketResearchData } from '../types';
import { TrendingUp, Sparkles, Shield, Info, Download, Loader2 } from 'lucide-react';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail<MarketResearchData> | null;
  onGenerate: () => Promise<void>;
  onExportPdf: () => void;
  isLoading: boolean;
  isGenerating?: boolean;
  generationProgress?: { stageText: string; progressPercent: number } | null;
  isGenerateDisabled?: boolean;
}

export const MarketResearchModule: React.FC<Props> = ({
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
          <TrendingUp size={28} />
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>
          Market Research & Competitor Intelligence Not Yet Generated
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 480, margin: '0 auto 20px auto' }}>
          Analyze the competitive landscape, market dynamics, and competitive wedge for {project.name}.
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
              {generationProgress ? `${generationProgress.stageText} (${generationProgress.progressPercent}%)` : 'Synthesizing Market Intelligence...'}
            </>
          ) : (
            <>
              <Sparkles size={16} /> Generate Market Intelligence
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header Bar */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <TrendingUp size={22} />
          </div>
          <div className="module-titles">
            <h2>
              Market Research & Competitor Analysis
              <span className="version-pill-dropdown">
                {moduleDetail.active_version_name || 'V1'}
              </span>
            </h2>
            <p>TAM/SAM/SOM market estimation, competitor profiles, and positioning wedge</p>
          </div>
        </div>

        <button onClick={onExportPdf} className="btn-secondary">
          <Download size={14} color="#6366f1" /> Export This Module (PDF)
        </button>
      </div>

      {/* Provenance Notice */}
      <div style={{ padding: '10px 14px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: 8, border: '1px solid rgba(59, 130, 246, 0.25)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Info size={16} color="#3b82f6" />
        <span style={{ fontSize: 12, color: 'var(--text-main)' }}>
          <b>Provenance Note:</b> {data.provenance_note || 'Structured analytical market assessment based on industry benchmarks and disclosed business context.'}
        </span>
      </div>

      {/* Market Size & Positioning Banner */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div className="card">
          <div className="card-title" style={{ color: '#0ea5e9' }}>
            <TrendingUp size={16} /> Addressable Market Size (TAM / SAM / SOM)
          </div>
          <p style={{ fontSize: 13.5, color: '#1e293b', marginTop: 10, lineHeight: 1.5 }}>
            {data.target_market_size}
          </p>
        </div>

        <div className="card">
          <div className="card-title" style={{ color: '#6366f1' }}>
            <Shield size={16} /> Strategic Competitive Positioning
          </div>
          <p style={{ fontSize: 13.5, color: '#1e293b', marginTop: 10, lineHeight: 1.5 }}>
            {data.competitive_positioning}
          </p>
        </div>
      </div>

      {/* Competitor Profiles Cards */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 14 }}>
          Competitor Profiles & Market Share Estimates
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
          {(data.competitor_profiles || []).map((c, idx) => (
            <div key={idx} style={{ background: '#f8fafc', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h4 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>{c.name}</h4>
                <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: '#ede9fe', color: '#6366f1' }}>
                  {c.market_share_estimate}
                </span>
              </div>

              <div style={{ fontSize: 12, color: '#10b981' }}>
                <b>Strengths:</b> {c.strengths ? c.strengths.join(', ') : '—'}
              </div>

              <div style={{ fontSize: 12, color: '#ef4444' }}>
                <b>Weaknesses:</b> {c.weaknesses ? c.weaknesses.join(', ') : '—'}
              </div>

              <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 'auto', paddingTop: 6, borderTop: '1px solid #e2e8f0' }}>
                <b>Pricing Model:</b> {c.pricing_model}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Opportunities & Threats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card" style={{ borderLeft: '4px solid #10b981' }}>
          <div className="card-title" style={{ color: '#10b981' }}>
            Market Opportunities & Tailwinds
          </div>
          <ul style={{ paddingLeft: 18, fontSize: 12.5, color: '#334155', marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(data.opportunities || []).map((o, idx) => <li key={idx}>{o}</li>)}
          </ul>
        </div>

        <div className="card" style={{ borderLeft: '4px solid #ef4444' }}>
          <div className="card-title" style={{ color: '#ef4444' }}>
            Competitive Threats & Headwinds
          </div>
          <ul style={{ paddingLeft: 18, fontSize: 12.5, color: '#334155', marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(data.threats || []).map((t, idx) => <li key={idx}>{t}</li>)}
          </ul>
        </div>
      </div>
    </div>
  );
};
