import React, { useState } from 'react';
import { Project, ModuleDetail, BMCData } from '../types';
import { RadialBMCInfographic } from './RadialBMCInfographic';
import { VersionToolbar } from './VersionToolbar';
import { ContextualAssistant } from './ContextualAssistant';
import { Compass, Sparkles, LayoutGrid, Eye, Loader2 } from 'lucide-react';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail<BMCData> | null;
  onGenerate: () => Promise<void>;
  onModify: (instruction: string) => Promise<void>;
  onRenameVersion: (newName: string) => Promise<void>;
  onDeleteVersion: (versionId: string) => Promise<void>;
  onRestoreVersion: (versionId: string) => Promise<void>;
  onExportPdf: () => void;
  isLoading: boolean;
  isGenerating?: boolean;
  generationProgress?: { stageText: string; progressPercent: number } | null;
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
  onExportPdf,
  isLoading,
  isGenerating = false,
  generationProgress = null,
  isGenerateDisabled = false
}) => {
  const [viewMode, setViewMode] = useState<'radial' | 'grid'>('radial');
  const bmcData = moduleDetail?.data;

  if (!bmcData) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#ede9fe', color: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
          <Compass size={28} />
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8 }}>
          Business Model Canvas Not Yet Generated
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 480, margin: '0 auto 20px auto' }}>
          Generate Alexander Osterwalder's 9-block Business Model Canvas synthesized specifically for {project.name}.
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
              {generationProgress ? `${generationProgress.stageText} (${generationProgress.progressPercent}%)` : 'Synthesizing Canvas...'}
            </>
          ) : (
            <>
              <Sparkles size={16} /> Generate Business Model Canvas
            </>
          )}
        </button>
      </div>
    );
  }

  const bmcBlocks = [
    { key: 'key_partnerships', title: '1. Key Partnerships', items: bmcData.key_partnerships, color: '#06b6d4' },
    { key: 'key_activities', title: '2. Key Activities', items: bmcData.key_activities, color: '#3b82f6' },
    { key: 'key_resources', title: '3. Key Resources', items: bmcData.key_resources, color: '#8b5cf6' },
    { key: 'value_propositions', title: '4. Value Propositions', items: bmcData.value_propositions, color: '#6366f1' },
    { key: 'customer_relationships', title: '5. Customer Relationships', items: bmcData.customer_relationships, color: '#ec4899' },
    { key: 'channels', title: '6. Channels', items: bmcData.channels, color: '#f43f5e' },
    { key: 'customer_segments', title: '7. Customer Segments', items: bmcData.customer_segments, color: '#fb7185' },
    { key: 'cost_structure', title: '8. Cost Structure', items: bmcData.cost_structure, color: '#f59e0b' },
    { key: 'revenue_streams', title: '9. Revenue Streams', items: bmcData.revenue_streams, color: '#10b981' }
  ];

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
        />
      </div>

      {/* Subtabs bar: Toggle View */}
      <div className="subtabs-bar">
        <button
          className={`subtab-pill ${viewMode === 'radial' ? 'active' : ''}`}
          onClick={() => setViewMode('radial')}
        >
          <Eye size={14} /> Radial Infographic View
        </button>
        <button
          className={`subtab-pill ${viewMode === 'grid' ? 'active' : ''}`}
          onClick={() => setViewMode('grid')}
        >
          <LayoutGrid size={14} /> 9-Block Grid View
        </button>
      </div>

      {/* 2-Column Grid: Infographic + Contextual Assistant */}
      <div className="workspace-grid">
        <div className="workspace-main-column">
          {viewMode === 'radial' ? (
            <RadialBMCInfographic
              projectName={project.name}
              stage={project.stage}
              data={bmcData}
            />
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
              {bmcBlocks.map((b) => (
                <div
                  key={b.key}
                  className="card"
                  style={{
                    padding: 16,
                    borderTop: `4px solid ${b.color}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 700, color: b.color, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>{b.title}</span>
                  </div>
                  <ul style={{ paddingLeft: 16, fontSize: 12.5, color: 'var(--text-main)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {(b.items || []).map((it, idx) => (
                      <li key={idx} style={{ lineHeight: 1.4 }}>{it}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Section-Specific Blueprint Assistant on the right */}
        <ContextualAssistant
          moduleTitle="Business Model Canvas"
          moduleType="bmc"
          onModify={onModify}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
};
