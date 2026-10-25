import React from 'react';
import { Project, ModuleDetail, MarketResearchData } from '../types';
import { TrendingUp, Sparkles, Shield, Info, Download, Loader2 } from 'lucide-react';
import { ModuleLifecycleActions } from './ModuleLifecycleActions';
import { isMeaninglessPlaceholder } from '../utils/researchPlaceholders';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail<MarketResearchData> | null;
  onGenerate: () => Promise<void>;
  onDeleteModule?: () => Promise<void>;
  onDeleteVersion?: (versionId: string) => Promise<void>;
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
  onDeleteModule,
  onDeleteVersion,
  onExportPdf,
  isLoading,
  isGenerating = false,
  generationProgress = null,
  isGenerateDisabled = false
}) => {
  const data = moduleDetail?.data;
  const meaningfulOpportunities = (data?.opportunities || []).filter(o => !isMeaninglessPlaceholder(o));
  const meaningfulThreats = (data?.threats || []).filter(t => !isMeaninglessPlaceholder(t));
  const meaningfulGaps = (data?.research_gaps || []).filter(g => !isMeaninglessPlaceholder(g));

  if (!data) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
          <TrendingUp size={28} />
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8 }}>
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
              {generationProgress ? `${generationProgress.stageText} ${generationProgress.progressPercent}%` : 'Synthesizing Market Intelligence...'}
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

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ModuleLifecycleActions
            moduleTitle="Market Research"
            onCreateNew={onGenerate}
            onDeleteModule={onDeleteModule}
            onDeleteVersion={onDeleteVersion}
            versions={moduleDetail.versions || []}
            createLabel="Run New Research"
            isBusy={isLoading || isGenerating}
            isCreateDisabled={isGenerateDisabled}
          />
          <button onClick={onExportPdf} className="btn-secondary">
            <Download size={14} color="var(--primary-text)" /> Export This Module (PDF)
          </button>
        </div>
      </div>

      {/* Provenance Notice */}
      <div style={{ padding: '10px 14px', background: 'rgb(69 60 55 / 0.1)', borderRadius: 8, border: '1px solid rgb(69 60 55 / 0.25)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Info size={16} color="var(--text-muted)" />
        <span style={{ fontSize: 12, color: 'var(--text-main)' }}>
          <b>Evidence status:</b> <span>{data.provenance_note || 'Review the source links and research gaps before relying on time-sensitive claims.'}</span>
        </span>
      </div>

      {/* Market Size & Positioning Banner */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div className="card">
          <div className="card-title" style={{ color: 'var(--text-muted)' }}>
            <TrendingUp size={16} /> Addressable Market Size (TAM / SAM / SOM)
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            TAM: total potential demand • SAM: serviceable segment reachable • SOM: realistic near-term target
          </div>
          <p style={{ fontSize: 13.5, color: 'var(--text-main)', marginTop: 8, lineHeight: 1.5 }}>
            {data.target_market_size}
          </p>
        </div>

        <div className="card">
          <div className="card-title" style={{ color: 'var(--primary-text)' }}>
            <Shield size={16} /> Strategic Competitive Positioning
          </div>
          <p style={{ fontSize: 13.5, color: 'var(--text-main)', marginTop: 10, lineHeight: 1.5 }}>
            {data.competitive_positioning}
          </p>
        </div>
      </div>

      {/* Competitor Profiles Cards */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 14 }}>
          Competitors Identified from Research
        </div>
        {(data.competitor_profiles || []).length === 0 ? (
          <div style={{ background: 'var(--bg-subtle)', padding: 14, borderRadius: 8, border: '1px solid var(--border-color)' }}>
            <p style={{ fontSize: 13, color: 'var(--text-main)', fontWeight: 600, margin: '0 0 6px 0' }}>
              Verified sources unavailable
            </p>
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
              This does not mean no competitors exist in your market. Rather, verifiable grounded sources were not returned for this run. Complete the manual validation checklist below to verify local and direct competitors.
            </p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
          {(data.competitor_profiles || []).map((c, idx) => (
            <div key={idx} style={{ background: 'var(--bg-subtle)', padding: 16, borderRadius: 10, border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)' }}>{c.name}</h4>
                <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-subtle)', color: 'var(--primary-text)' }}>
                  {c.market_share_estimate}
                </span>
              </div>

              <div style={{ fontSize: 12, color: 'var(--primary-text)' }}>
                <b>Strengths:</b> {c.strengths ? c.strengths.join(', ') : '—'}
              </div>

              <div style={{ fontSize: 12, color: 'var(--danger-text)' }}>
                <b>Weaknesses:</b> {c.weaknesses ? c.weaknesses.join(', ') : '—'}
              </div>

              <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 'auto', paddingTop: 6, borderTop: '1px solid var(--border-color)' }}>
                <b>Pricing Model:</b> {c.pricing_model}
              </div>
              {(c.sources || []).length > 0 && (
                <div style={{ fontSize: 11.5, color: 'var(--text-main)' }}>
                  <b>Sources:</b> {(c.sources || []).map((source, sourceIdx) => (
                    <span key={sourceIdx}>{sourceIdx > 0 ? ', ' : ' '}{source}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
          </div>
        )}
      </div>

      {/* Opportunities & Threats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card" style={{ borderLeft: '4px solid var(--primary-text)' }}>
          <div className="card-title" style={{ color: 'var(--primary-text)' }}>
            Market Opportunities & Tailwinds
          </div>
          {meaningfulOpportunities.length === 0 ? (
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', fontStyle: 'italic', marginTop: 10, marginBottom: 0 }}>
              No supported opportunities were identified in this result.
            </p>
          ) : (
            <ul style={{ paddingLeft: 18, fontSize: 12.5, color: 'var(--text-main)', marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {meaningfulOpportunities.map((o, idx) => <li key={idx}>{o}</li>)}
            </ul>
          )}
        </div>

        <div className="card" style={{ borderLeft: '4px solid var(--danger-text)' }}>
          <div className="card-title" style={{ color: 'var(--danger-text)' }}>
            Competitive Threats & Headwinds
          </div>
          {meaningfulThreats.length === 0 ? (
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', fontStyle: 'italic', marginTop: 10, marginBottom: 0 }}>
              No supported threats were identified in this result.
            </p>
          ) : (
            <ul style={{ paddingLeft: 18, fontSize: 12.5, color: 'var(--text-main)', marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {meaningfulThreats.map((t, idx) => <li key={idx}>{t}</li>)}
            </ul>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <section className="card" aria-labelledby="market-sources-title">
          <div className="card-title" id="market-sources-title">Sources used</div>
          {(data.source_references || []).length === 0 ? (
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', marginBottom: 0 }}>
              No verifiable web citations were returned for this analysis.
            </p>
          ) : (
            <ul style={{ paddingLeft: 18, fontSize: 12.5, margin: '10px 0 0' }}>
              {(data.source_references || []).map((source, idx) => (
                <li key={`${source.url}-${idx}`} style={{ marginBottom: 6 }}>
                  <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}</a>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card" aria-labelledby="market-gaps-title">
          <div className="card-title" id="market-gaps-title">Research gaps & validation checklist</div>
          {meaningfulGaps.length === 0 ? (
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', fontStyle: 'italic', margin: '10px 0 0' }}>
              No specific research gaps were provided.
            </p>
          ) : (
            <ul style={{ paddingLeft: 18, fontSize: 12.5, color: 'var(--text-main)', margin: '10px 0 0', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {meaningfulGaps.map((gap, idx) => <li key={idx}>{gap}</li>)}
            </ul>
          )}
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border-color)', fontSize: 12, color: 'var(--text-muted)' }}>
            <b>Practical manual validation steps:</b>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
              <span>1. Search maps, Google Business, and trade directories for local or niche providers.</span>
              <span>2. Conduct 5 customer discovery interviews focused on past purchase decisions.</span>
              <span>3. Obtain published or direct pricing quotes from at least 2 alternative options.</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
