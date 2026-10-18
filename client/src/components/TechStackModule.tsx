import React from 'react';
import { Project, ModuleDetail, TechStackData } from '../types';
import { VersionToolbar } from './VersionToolbar';
import { ContextualAssistant } from './ContextualAssistant';
import { ArchitectureInfographic } from './ArchitectureInfographic';
import { Cpu, Sparkles, Layers, ShieldCheck, Server, Database, Cloud, Terminal, Loader2 } from 'lucide-react';

interface Props {
  project: Project;
  moduleDetail: ModuleDetail<TechStackData> | null;
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
  generationProgress?: { stageText: string; progressPercent: number } | null;
  isGenerateDisabled?: boolean;
}

export const TechStackModule: React.FC<Props> = ({
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
  const techData = moduleDetail?.data;

  const handleDownloadSvg = () => {
    const svgEl = document.querySelector('.workspace-main-column svg');
    if (!svgEl) return;
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgEl);
    const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${project.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}_tech_stack_architecture.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (!techData) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#e8ede2', color: '#6d855f', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
          <Cpu size={28} />
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8 }}>
          Technology Stack Architecture Not Yet Generated
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 480, margin: '0 auto 20px auto' }}>
          Synthesize an enterprise-ready technology stack blueprint evaluated for {project.name}'s stage ({project.stage}) and existing technical assets.
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
              {generationProgress ? `${generationProgress.stageText} (${generationProgress.progressPercent}%)` : 'Synthesizing Architecture...'}
            </>
          ) : (
            <>
              <Sparkles size={16} /> Generate Technology Stack Blueprint
            </>
          )}
        </button>
      </div>
    );
  }

  const categoryIcons: Record<string, any> = {
    Frontend: Layers,
    Backend: Server,
    Database: Database,
    'Cloud/Hosting': Cloud,
    Cloud: Cloud,
    Storage: Server,
    Security: ShieldCheck,
    DevOps: Terminal,
    Services: Cpu
  };
  const stackEvaluation = techData.existing_stack_evaluation || {};
  const stackEvaluationStatus = stackEvaluation.evaluation_status;
  const statusMessage = stackEvaluationStatus === 'not_verified_offline'
    ? 'Your current components were captured, but compatibility and migration risk could not be verified in offline mode.'
    : stackEvaluationStatus === 'no_existing_stack'
      ? 'No existing stack was supplied for compatibility review.'
      : 'Review the current components, compatibility notes, and migration trade-offs below.';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Module Header */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <Cpu size={22} />
          </div>
          <div className="module-titles">
            <h2>
              Technology Stack Architecture
              <span className="version-pill-dropdown">
                {moduleDetail.active_version_name || `V${moduleDetail.active_version_number || 1}`}
              </span>
            </h2>
            <p>Production architectural pattern, service tiers, and component suitability</p>
          </div>
        </div>

        <VersionToolbar
          moduleType="tech_stack"
          moduleTitle="Technology Stack"
          activeVersionName={moduleDetail.active_version_name}
          activeVersionNumber={moduleDetail.active_version_number}
          versions={moduleDetail.versions || []}
          onRename={onRenameVersion}
          onDelete={onDeleteVersion}
          onRestore={onRestoreVersion}
          onExportPdf={onExportPdf}
          onExportSvg={handleDownloadSvg}
          onCreateNew={onCreateNew}
          onDeleteModule={onDeleteModule}
          createLabel="Create New Stack"
          isBusy={isLoading || isGenerating}
          isCreateDisabled={isGenerateDisabled}
        />
      </div>

      <div className="workspace-grid">
        <div className="workspace-main-column">
          {/* Dedicated Vector SVG Architecture Blueprint Infographic */}
          <ArchitectureInfographic
            techData={techData}
            projectName={project.name}
            versionName={moduleDetail.active_version_name}
            onDownloadSvg={handleDownloadSvg}
          />

          {/* Architectural Summary Banner */}
          <div className="card" style={{ background: 'var(--bg-card)', borderLeft: '4px solid #6d855f' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, color: '#6d855f' }}>
                Architectural Blueprint
              </span>
              <span className="stage-badge-purple">
                Pattern: {techData?.architecture_pattern || 'Modular Monolith'}
              </span>
            </div>
            <p style={{ fontSize: 13.5, color: 'var(--text-main)', lineHeight: 1.5 }}>
              {techData?.summary || 'Production architectural blueprint.'}
            </p>
          </div>

          <section className="card" aria-labelledby="existing-stack-review-title">
            <div className="card-title" id="existing-stack-review-title">
              <Layers size={16} /> Existing Stack Compatibility Review
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5, marginTop: 8 }}>
              {statusMessage}
            </p>
            {(stackEvaluation.existing_components || []).length > 0 && (
              <div style={{ marginTop: 10, fontSize: 12.5, color: 'var(--text-main)' }}>
                <b>Current components supplied:</b> {(stackEvaluation.existing_components as string[]).join(', ')}
              </div>
            )}
            {(stackEvaluation.compatible_elements || []).length > 0 && (
              <div style={{ marginTop: 10, fontSize: 12.5, color: 'var(--text-main)' }}>
                <b>Compatible or planned to retain:</b> {(stackEvaluation.compatible_elements as string[]).join(', ')}
              </div>
            )}
            {(stackEvaluation.incompatible_or_redundant || []).length > 0 && (
              <div style={{ marginTop: 10, fontSize: 12.5, color: 'var(--text-main)' }}>
                <b>Potential conflicts or redundancy:</b> {(stackEvaluation.incompatible_or_redundant as string[]).join(', ')}
              </div>
            )}
            {stackEvaluation.migration_trade_offs && (
              <p style={{ fontSize: 12.5, color: 'var(--text-main)', lineHeight: 1.5, margin: '10px 0 0' }}>
                <b>Migration trade-offs:</b> {stackEvaluation.migration_trade_offs}
              </p>
            )}
          </section>

          {/* Tiered Architectural Infographic Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
            {(techData?.recommendations || []).map((item, idx) => {
              if (!item) return null;
              const Icon = categoryIcons[item.category] || Cpu;
              return (
                <div key={idx} className="card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 30, height: 30, borderRadius: 6, background: 'rgba(109, 133, 95, 0.15)', color: '#6d855f', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Icon size={16} />
                      </div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)' }}>{item.technology}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>{item.category}</div>
                      </div>
                    </div>
                    {item.migration_risk && (
                      <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4, background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
                        Risk: {item.migration_risk}
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: 12.5, color: 'var(--text-main)', lineHeight: 1.4 }}>
                    <b>Purpose:</b> {item.purpose}
                  </div>

                  <div style={{ fontSize: 12, color: 'var(--text-muted)', background: 'var(--bg-subtle)', padding: 8, borderRadius: 6, border: '1px solid var(--border-color)' }}>
                    <b>Suitability:</b> {item.suitability}
                  </div>

                  {item.trade_offs && (
                    <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                      <i>Trade-offs: {item.trade_offs}</i>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Section-Specific Blueprint Assistant on the right */}
        <ContextualAssistant
          moduleTitle="Technology Stack"
          moduleType="tech_stack"
          onModify={onModify}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
};
