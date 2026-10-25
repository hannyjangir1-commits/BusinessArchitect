import React, { useState, useEffect } from 'react';
import { Project, ModuleDetail, BMCData } from '../types';
import { RadialBMCInfographic } from './RadialBMCInfographic';
import { VersionToolbar } from './VersionToolbar';
import { ContextualAssistant } from './ContextualAssistant';
import { Compass, CirclePlus, LayoutGrid, Eye, Loader2, Sparkles, MessageCircle } from 'lucide-react';

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

  const [assistantOpen, setAssistantOpen] = useState(false);

  const setViewMode = (mode: 'grid' | 'radial') => {
    setViewModeState(mode);
    try {
      sessionStorage.setItem(`va_view_bmc_${project.id}`, mode);
    } catch {
      // ignore
    }
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

  // Canonical Osterwalder 9 blocks
  const blocks = {
    partnerships: { title: '1. Key Partnerships', items: bmcData.key_partnerships || [], color: 'var(--text-muted)' },
    activities: { title: '2. Key Activities', items: bmcData.key_activities || [], color: 'var(--primary-text)' },
    resources: { title: '3. Key Resources', items: bmcData.key_resources || [], color: 'var(--primary-text)' },
    value: { title: '4. Value Propositions', items: bmcData.value_propositions || [], color: 'var(--text-muted)' },
    relationships: { title: '5. Customer Relationships', items: bmcData.customer_relationships || [], color: 'var(--primary-text)' },
    channels: { title: '6. Channels', items: bmcData.channels || [], color: 'var(--primary-text)' },
    segments: { title: '7. Customer Segments', items: bmcData.customer_segments || [], color: 'var(--primary-text)' },
    costs: { title: '8. Cost Structure', items: bmcData.cost_structure || [], color: 'var(--primary-text)' },
    revenue: { title: '9. Revenue Streams', items: bmcData.revenue_streams || [], color: 'var(--text-muted)' }
  };

  const renderCard = (block: { title: string; items: string[]; color: string }, gridArea?: string, minHeight = 160) => (
    <div
      className="card"
      style={{
        padding: 16,
        borderTop: `4px solid ${block.color}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        minHeight,
        gridArea
      }}
    >
      <h4 style={{ fontSize: 13, fontWeight: 700, color: block.color, margin: 0 }}>
        {block.title}
      </h4>
      {block.items.length === 0 ? (
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No specific points identified.
        </span>
      ) : (
        <ul style={{ paddingLeft: 16, margin: 0, fontSize: 12.5, color: 'var(--text-main)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {block.items.map((it, idx) => (
            <li key={idx} style={{ lineHeight: 1.4 }}>{it}</li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Module View Header */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <Compass size={22} />
          </div>
          <div className="module-titles">
            <h2>
              Business Model Canvas
              <span className="version-pill-dropdown">
                {moduleDetail.active_version_name || `V${moduleDetail.active_version_number || 1}`}
              </span>
            </h2>
            <p>Alexander Osterwalder's 9-block business model architecture</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
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
          <LayoutGrid size={14} /> 9-Block Canvas (Default)
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
          ) : (
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
                  {renderCard(blocks.partnerships, undefined, 360)}
                </div>

                {/* 2. Key Activities: column 2, row 1 */}
                <div style={{ gridColumn: '2', gridRow: '1' }}>
                  {renderCard(blocks.activities)}
                </div>

                {/* 3. Key Resources: column 2, row 2 */}
                <div style={{ gridColumn: '2', gridRow: '2' }}>
                  {renderCard(blocks.resources)}
                </div>

                {/* 4. Value Propositions: column 3, row 1-2 */}
                <div style={{ gridColumn: '3', gridRow: '1 / span 2' }}>
                  {renderCard(blocks.value, undefined, 360)}
                </div>

                {/* 5. Customer Relationships: column 4, row 1 */}
                <div style={{ gridColumn: '4', gridRow: '1' }}>
                  {renderCard(blocks.relationships)}
                </div>

                {/* 6. Channels: column 4, row 2 */}
                <div style={{ gridColumn: '4', gridRow: '2' }}>
                  {renderCard(blocks.channels)}
                </div>

                {/* 7. Customer Segments: column 5, row 1-2 */}
                <div style={{ gridColumn: '5', gridRow: '1 / span 2' }}>
                  {renderCard(blocks.segments, undefined, 360)}
                </div>
              </div>

              {/* Bottom Row across full width: Cost Structure & Revenue Streams */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 12
                }}
              >
                {/* 8. Cost Structure */}
                <div>
                  {renderCard(blocks.costs, undefined, 140)}
                </div>

                {/* 9. Revenue Streams */}
                <div>
                  {renderCard(blocks.revenue, undefined, 140)}
                </div>
              </div>
            </div>
          )}
        </main>

        {/* Contextual Assistant: Rendered only when active and controlled */}
        {assistantOpen && (
          <ContextualAssistant
            moduleTitle="Business Model Canvas"
            moduleType="bmc"
            onModify={onModify}
            onClose={() => setAssistantOpen(false)}
            isLoading={isLoading}
          />
        )}
      </div>
    </div>
  );
};
