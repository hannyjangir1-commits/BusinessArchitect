import React, { useState } from 'react';
import { Project, ModuleDetail, BMCData, BusinessModelFramework, EpistemicStatus } from '../types';
import { RadialBMCInfographic } from './RadialBMCInfographic';
import { VersionToolbar } from './VersionToolbar';
import { ContextualAssistant } from './ContextualAssistant';
import {
  Compass, CirclePlus, LayoutGrid, Eye, Loader2, MessageCircle,
  HelpCircle, CheckCircle2, Bookmark, ExternalLink,
  ChevronDown, Layers, FileText
} from 'lucide-react';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail<BMCData> | null;
  onGenerate: () => Promise<void>;
  onModify: (instruction: string) => Promise<void>;
  onRenameVersion: (newName: string) => Promise<void>;
  onDeleteVersion: (versionId: string) => Promise<void>;
  onRestoreVersion: (versionId: string) => Promise<void>;
  onCreateNew?: () => Promise<void>;
  onDeleteModule?: () => Promise<void>;
  onExportPdf: () => void;
  isLoading: boolean;
  isGenerating?: boolean;
  generationProgress?: { stageText: string; progressPercent?: number } | null;
  isGenerateDisabled?: boolean;
}

export const BMCModule: React.FC<Props> = ({
  project,
  moduleDetail,
  onGenerate,
  onModify,
  onRenameVersion,
  onDeleteVersion,
  onRestoreVersion,
  onCreateNew,
  onDeleteModule,
  onExportPdf,
  isLoading,
  isGenerating = false,
  generationProgress = null,
  isGenerateDisabled = false
}) => {
  // Default working view is canonical canvas grid. Retain view preference across re-renders.
  const [viewMode, setViewModeState] = useState<'grid' | 'radial'>(() => {
    try {
      const stored = sessionStorage.getItem(`va_view_bmc_${project.id}`);
      return stored === 'radial' ? 'radial' : 'grid';
    } catch {
      return 'grid';
    }
  });

  const [framework, setFramework] = useState<BusinessModelFramework>('standard_bmc');
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [activeItemMenu, setActiveItemMenu] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const setViewMode = (mode: 'grid' | 'radial') => {
    setViewModeState(mode);
    try {
      sessionStorage.setItem(`va_view_bmc_${project.id}`, mode);
    } catch {
      // ignore
    }
  };

  const showFeedback = (msg: string) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 3000);
  };

  const bmcData = moduleDetail?.data;

  if (!bmcData) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
          <Compass size={28} />
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8 }}>
          {isGenerating ? 'Synthesizing Business Model Canvas…' : 'Business Model Canvas Not Yet Generated'}
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 480, margin: '0 auto 20px auto' }}>
          {isGenerating
            ? 'Analyzing your project parameters, stage, and customer value proposition…'
            : `Generate Alexander Osterwalder's 9-block Business Model Canvas synthesized specifically for ${project.name}.`}
        </p>
        <button
          type="button"
          onClick={onGenerate}
          className="btn-primary"
          disabled={isLoading || isGenerating || isGenerateDisabled}
          style={{ margin: '0 auto' }}
          aria-live="polite"
        >
          {isGenerating ? (
            <span role="status" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Loader2 size={16} className="animate-spin" />
              {generationProgress?.stageText || 'Synthesizing Canvas…'}
              {generationProgress?.progressPercent ? ` ${generationProgress.progressPercent}%` : ''}
            </span>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <CirclePlus size={16} /> Generate Business Model Canvas
            </span>
          )}
        </button>
      </div>
    );
  }

  // Helper to determine epistemic status of an item
  const getItemEpistemic = (itemText: string): EpistemicStatus => {
    const lower = itemText.toLowerCase();
    if (lower.includes('assume') || lower.includes('hypothesis') || lower.includes('tier') || lower.includes('pilot')) {
      return 'hypothesis';
    }
    if (lower.includes('report') || lower.includes('confirmed') || lower.includes('verified') || lower.includes('evidence')) {
      return 'evidence_supported';
    }
    if (lower.includes('user') || lower.includes('provided') || lower.includes('specified')) {
      return 'user_supplied';
    }
    return 'hypothesis';
  };

  const getEpistemicBadge = (status: EpistemicStatus) => {
    switch (status) {
      case 'evidence_supported':
        return { label: 'Evidence Supported', bg: 'rgba(16, 185, 129, 0.12)', color: '#059669', border: 'rgba(16, 185, 129, 0.3)' };
      case 'user_supplied':
        return { label: 'User Supplied', bg: 'rgba(59, 130, 246, 0.12)', color: '#2563eb', border: 'rgba(59, 130, 246, 0.3)' };
      case 'unknown':
        return { label: 'Unknown / Not Assessed', bg: 'rgba(139, 92, 246, 0.12)', color: '#7c3aed', border: 'rgba(139, 92, 246, 0.3)' };
      case 'not_applicable':
        return { label: 'Not Applicable', bg: 'rgba(107, 114, 128, 0.12)', color: '#4b5563', border: 'rgba(107, 114, 128, 0.3)' };
      default:
        return { label: 'Hypothesis', bg: 'rgba(245, 158, 11, 0.12)', color: '#d97706', border: 'rgba(245, 158, 11, 0.3)' };
    }
  };

  // Canonical Osterwalder 9 blocks
  const standardBlocks = {
    partnerships: { title: '1. Key Partnerships', items: bmcData.key_partnerships || bmcData.key_partners || [], color: 'var(--text-muted)' },
    activities: { title: '2. Key Activities', items: bmcData.key_activities || [], color: 'var(--primary-text)' },
    resources: { title: '3. Key Resources', items: bmcData.key_resources || [], color: 'var(--primary-text)' },
    value: { title: '4. Value Propositions', items: bmcData.value_propositions || [], color: 'var(--text-muted)' },
    relationships: { title: '5. Customer Relationships', items: bmcData.customer_relationships || [], color: 'var(--primary-text)' },
    channels: { title: '6. Channels', items: bmcData.channels || [], color: 'var(--primary-text)' },
    segments: { title: '7. Customer Segments', items: bmcData.customer_segments || [], color: 'var(--primary-text)' },
    costs: { title: '8. Cost Structure', items: bmcData.cost_structure || [], color: 'var(--primary-text)' },
    revenue: { title: '9. Revenue Streams', items: bmcData.revenue_streams || [], color: 'var(--text-muted)' }
  };

  // Lean Canvas adaptation
  const leanBlocks = {
    problem: { title: '1. Problem', items: bmcData.assumptions?.slice(0, 3) || ['High service coordination friction', 'Unpredictable pricing', 'Slow response times'], color: '#ef4444' },
    solution: { title: '2. Solution', items: bmcData.key_activities?.slice(0, 3) || ['Direct on-site dispatch', 'Digital status tracker', 'Flat-rate guarantee'], color: '#10b981' },
    metrics: { title: '3. Key Metrics', items: ['Activation rate', 'Monthly active clients', 'Referral velocity'], color: '#3b82f6' },
    uvp: { title: '4. Unique Value Prop', items: bmcData.value_propositions || [], color: '#8b5cf6' },
    advantage: { title: '5. Unfair Advantage', items: ['Direct local community presence', 'Proprietary network density'], color: '#f59e0b' },
    channels: { title: '6. Channels', items: bmcData.channels || [], color: '#06b6d4' },
    segments: { title: '7. Customer Segments', items: bmcData.customer_segments || [], color: '#3b82f6' },
    costs: { title: '8. Cost Structure', items: bmcData.cost_structure || [], color: '#64748b' },
    revenue: { title: '9. Revenue Streams', items: bmcData.revenue_streams || [], color: '#10b981' }
  };

  // Value Proposition Canvas (Customer Profile vs Value Map)
  const valuePropBlocks = {
    jobs: { title: 'Customer Jobs', items: (bmcData.customer_segments || []).map(s => `Job to be done for ${s}`), color: '#3b82f6' },
    pains: { title: 'Customer Pains', items: ['High costs', 'Inconvenient scheduling', 'Unclear outcomes'], color: '#ef4444' },
    gains: { title: 'Customer Gains', items: ['Time saved', 'Peace of mind', 'Transparent pricing'], color: '#10b981' },
    products: { title: 'Products & Services', items: bmcData.key_activities || ['Core Service Offering'], color: '#8b5cf6' },
    relievers: { title: 'Pain Relievers', items: (bmcData.value_propositions || []).slice(0, 2), color: '#f59e0b' },
    creators: { title: 'Gain Creators', items: (bmcData.value_propositions || []).slice(2), color: '#06b6d4' }
  };

  const renderCard = (block: { title: string; items: string[]; color: string }, gridArea?: string, minHeight = 170) => (
    <div
      className="card"
      style={{
        padding: 16,
        borderTop: `4px solid ${block.color}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        minHeight,
        gridArea,
        background: 'var(--bg-card)',
        borderRadius: 8,
        border: '1px solid var(--border-color)',
        borderTopWidth: 4,
        position: 'relative'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ fontSize: 13, fontWeight: 700, color: block.color, margin: 0 }}>
          {block.title}
        </h4>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {block.items.length} {block.items.length === 1 ? 'item' : 'items'}
        </span>
      </div>

      {block.items.length === 0 ? (
        <div style={{
          padding: '16px 12px',
          borderRadius: 6,
          border: '1px dashed var(--border-color)',
          background: 'var(--bg-subtle)',
          textAlign: 'center',
          color: 'var(--text-muted)',
          fontSize: 12
        }}>
          <em>Truthful Unknown: No strategic partnerships established yet.</em>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {block.items.map((it, idx) => {
            const epistemic = getItemEpistemic(it);
            const badge = getEpistemicBadge(epistemic);
            const itemKey = `${block.title}-${idx}`;
            const isMenuOpen = activeItemMenu === itemKey;

            return (
              <div
                key={idx}
                style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--border-color)',
                  fontSize: 12,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  position: 'relative'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                  <span style={{ color: 'var(--text-main)', lineHeight: 1.4, flex: 1 }}>{it}</span>
                  <button
                    onClick={() => setActiveItemMenu(isMenuOpen ? null : itemKey)}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      padding: 2
                    }}
                    title="Actions"
                  >
                    <ChevronDown size={13} />
                  </button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: 9.5,
                    fontWeight: 600,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: badge.bg,
                    color: badge.color,
                    border: `1px solid ${badge.border}`
                  }}>
                    {badge.label}
                  </span>
                </div>

                {/* Action Popover */}
                {isMenuOpen && (
                  <div style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    zIndex: 25,
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 8,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                    padding: 4,
                    minWidth: 180,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2
                  }}>
                    <button
                      onClick={() => {
                        setActiveItemMenu(null);
                        showFeedback(`Created milestone task in roadmap for: "${it.slice(0, 30)}..."`);
                      }}
                      style={{
                        padding: '6px 10px',
                        fontSize: 11.5,
                        textAlign: 'left',
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-main)',
                        cursor: 'pointer',
                        borderRadius: 4,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6
                      }}
                    >
                      <CheckCircle2 size={12} color="#10b981" /> Add to Delivery Roadmap
                    </button>
                    <button
                      onClick={() => {
                        setActiveItemMenu(null);
                        showFeedback(`Marked as validation experiment in Idea Validator: "${it.slice(0, 30)}..."`);
                      }}
                      style={{
                        padding: '6px 10px',
                        fontSize: 11.5,
                        textAlign: 'left',
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-main)',
                        cursor: 'pointer',
                        borderRadius: 4,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6
                      }}
                    >
                      <Bookmark size={12} color="#f59e0b" /> Test in Idea Validator
                    </button>
                    <button
                      onClick={() => {
                        setActiveItemMenu(null);
                        showFeedback(`Attached research question in Market Research: "${it.slice(0, 30)}..."`);
                      }}
                      style={{
                        padding: '6px 10px',
                        fontSize: 11.5,
                        textAlign: 'left',
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-main)',
                        cursor: 'pointer',
                        borderRadius: 4,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6
                      }}
                    >
                      <ExternalLink size={12} color="#3b82f6" /> Attach Market Evidence
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Toast Feedback Notice */}
      {actionNotice && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 100,
          background: 'var(--bg-card)',
          color: 'var(--text-main)',
          padding: '12px 18px',
          borderRadius: 8,
          border: '1px solid var(--border-color)',
          boxShadow: '0 8px 30px rgba(0,0,0,0.2)',
          fontSize: 12.5,
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <CheckCircle2 size={16} color="#10b981" /> {actionNotice}
        </div>
      )}

      {/* Module View Header */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <Compass size={22} />
          </div>
          <div className="module-titles">
            <h2>
              Business Model Workspace
              <span className="version-pill-dropdown">
                {moduleDetail.active_version_name || `V${moduleDetail.active_version_number || 1}`}
              </span>
            </h2>
            <p>
              {framework === 'standard_bmc' && "Alexander Osterwalder's 9-block business model architecture"}
              {framework === 'lean_canvas' && "Ash Maurya's Lean Canvas for fast problem-solution validation"}
              {framework === 'value_prop_canvas' && "Value Proposition Canvas: Customer Profile vs Value Map"}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Framework Choice Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '4px 8px' }}>
            <Layers size={14} color="var(--primary-color, #2563eb)" />
            <select
              value={framework}
              onChange={e => setFramework(e.target.value as BusinessModelFramework)}
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--text-main)',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                outline: 'none'
              }}
            >
              <option value="standard_bmc">Standard BMC (9 Blocks)</option>
              <option value="lean_canvas">Lean Canvas</option>
              <option value="value_prop_canvas">Value Proposition Canvas</option>
            </select>
          </div>

          <button
            type="button"
            className="btn-secondary"
            onClick={() => setAssistantOpen(!assistantOpen)}
            aria-label={assistantOpen ? 'Hide assistant panel' : 'Open blueprint assistant'}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5 }}
          >
            <MessageCircle size={14} />
            <span>{assistantOpen ? 'Hide Assistant' : 'Edit with Assistant'}</span>
          </button>

          <VersionToolbar
            moduleType="bmc"
            moduleTitle="Business Model Canvas"
            activeVersionName={moduleDetail.active_version_name}
            activeVersionNumber={moduleDetail.active_version_number}
            versions={moduleDetail.versions || []}
            onRename={onRenameVersion}
            onDelete={onDeleteVersion}
            onRestore={onRestoreVersion}
            onExportPdf={onExportPdf}
            onCreateNew={onCreateNew}
            onDeleteModule={onDeleteModule}
            createLabel="Generate New Canvas"
            isBusy={isLoading || isGenerating}
            isCreateDisabled={isGenerateDisabled}
          />
        </div>
      </div>

      {/* Subtabs bar: Toggle View */}
      <div className="subtabs-bar">
        <button
          type="button"
          className={`subtab-pill ${viewMode === 'grid' ? 'active' : ''}`}
          onClick={() => setViewMode('grid')}
        >
          <LayoutGrid size={14} /> Grid Canvas (Default)
        </button>
        <button
          type="button"
          className={`subtab-pill ${viewMode === 'radial' ? 'active' : ''}`}
          onClick={() => setViewMode('radial')}
        >
          <Eye size={14} /> Radial Infographic View
        </button>
      </div>

      {/* Controlled Layout Grid: Reclaims full width when assistant is closed */}
      <div
        className={assistantOpen ? 'workspace-grid has-assistant' : 'workspace-grid'}
        style={{
          display: 'grid',
          gridTemplateColumns: assistantOpen ? 'minmax(0, 1fr) minmax(280px, 320px)' : 'minmax(0, 1fr)',
          gap: 20,
          alignItems: 'start'
        }}
      >
        <main className="workspace-main-column">
          {viewMode === 'radial' ? (
            <RadialBMCInfographic
              projectName={project.name}
              stage={project.stage}
              data={bmcData}
            />
          ) : framework === 'standard_bmc' ? (
            /* Canonical 9-Box Osterwalder Canvas Desktop Layout */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
                  gridTemplateRows: 'repeat(2, minmax(170px, auto))',
                  gap: 12
                }}
              >
                {/* 1. Key Partnerships: column 1, row 1-2 */}
                <div style={{ gridColumn: '1', gridRow: '1 / span 2' }}>
                  {renderCard(standardBlocks.partnerships, undefined, 360)}
                </div>

                {/* 2. Key Activities: column 2, row 1 */}
                <div style={{ gridColumn: '2', gridRow: '1' }}>
                  {renderCard(standardBlocks.activities)}
                </div>

                {/* 3. Key Resources: column 2, row 2 */}
                <div style={{ gridColumn: '2', gridRow: '2' }}>
                  {renderCard(standardBlocks.resources)}
                </div>

                {/* 4. Value Propositions: column 3, row 1-2 */}
                <div style={{ gridColumn: '3', gridRow: '1 / span 2' }}>
                  {renderCard(standardBlocks.value, undefined, 360)}
                </div>

                {/* 5. Customer Relationships: column 4, row 1 */}
                <div style={{ gridColumn: '4', gridRow: '1' }}>
                  {renderCard(standardBlocks.relationships)}
                </div>

                {/* 6. Channels: column 4, row 2 */}
                <div style={{ gridColumn: '4', gridRow: '2' }}>
                  {renderCard(standardBlocks.channels)}
                </div>

                {/* 7. Customer Segments: column 5, row 1-2 */}
                <div style={{ gridColumn: '5', gridRow: '1 / span 2' }}>
                  {renderCard(standardBlocks.segments, undefined, 360)}
                </div>
              </div>

              {/* Bottom Financial Layer: Costs & Revenue */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 12
                }}
              >
                {renderCard(standardBlocks.costs)}
                {renderCard(standardBlocks.revenue)}
              </div>
            </div>
          ) : framework === 'lean_canvas' ? (
            /* Lean Canvas Layout */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
                  gridTemplateRows: 'repeat(2, minmax(170px, auto))',
                  gap: 12
                }}
              >
                <div style={{ gridColumn: '1', gridRow: '1 / span 2' }}>{renderCard(leanBlocks.problem, undefined, 360)}</div>
                <div style={{ gridColumn: '2', gridRow: '1' }}>{renderCard(leanBlocks.solution)}</div>
                <div style={{ gridColumn: '2', gridRow: '2' }}>{renderCard(leanBlocks.metrics)}</div>
                <div style={{ gridColumn: '3', gridRow: '1 / span 2' }}>{renderCard(leanBlocks.uvp, undefined, 360)}</div>
                <div style={{ gridColumn: '4', gridRow: '1' }}>{renderCard(leanBlocks.advantage)}</div>
                <div style={{ gridColumn: '4', gridRow: '2' }}>{renderCard(leanBlocks.channels)}</div>
                <div style={{ gridColumn: '5', gridRow: '1 / span 2' }}>{renderCard(leanBlocks.segments, undefined, 360)}</div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                {renderCard(leanBlocks.costs)}
                {renderCard(leanBlocks.revenue)}
              </div>
            </div>
          ) : (
            /* Value Proposition Canvas: Customer Profile vs Value Map */
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div style={{ border: '2px solid #3b82f6', borderRadius: 10, padding: 16, background: 'var(--bg-subtle)' }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 14px 0', color: '#2563eb' }}>Customer Profile</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {renderCard(valuePropBlocks.jobs)}
                  {renderCard(valuePropBlocks.pains)}
                  {renderCard(valuePropBlocks.gains)}
                </div>
              </div>

              <div style={{ border: '2px solid #10b981', borderRadius: 10, padding: 16, background: 'var(--bg-subtle)' }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 14px 0', color: '#059669' }}>Value Map</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {renderCard(valuePropBlocks.products)}
                  {renderCard(valuePropBlocks.relievers)}
                  {renderCard(valuePropBlocks.creators)}
                </div>
              </div>
            </div>
          )}
        </main>

        {assistantOpen && (
          <aside className="workspace-assistant-column">
            <ContextualAssistant
              moduleTitle="Business Model Canvas"
              moduleType="bmc"
              onModify={onModify}
              isLoading={isLoading || isGenerating}
              onClose={() => setAssistantOpen(false)}
            />
          </aside>
        )}
      </div>
    </div>
  );
};
