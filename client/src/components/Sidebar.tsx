import React, { useState } from 'react';
import { Project } from '../types';
import {
  Layers, ChevronLeft, ChevronRight, LayoutDashboard, Compass, Cpu, CheckCircle2,
  TrendingUp, Calendar, Bot, ArrowRight, Plus, Check, Calculator
} from 'lucide-react';

export type ModuleBadgeStatus = 'unknown' | 'loading' | 'generated' | 'not-generated' | 'error';

interface Props {
  currentProject: Project | null;
  activeModule: string;
  onSelectModule: (module: string) => void;
  onPrefetchModule?: (module: string) => void;
  onBackToDashboard: () => void;
  onCreateNewProject: () => void;
  onExportFullPdf: () => void;
  moduleVersionBadges?: Record<string, { version?: string; isGenerated?: boolean; status?: ModuleBadgeStatus }>;
}

export const Sidebar: React.FC<Props> = ({
  currentProject,
  activeModule,
  onSelectModule,
  onPrefetchModule,
  onBackToDashboard,
  onCreateNewProject,
  onExportFullPdf,
  moduleVersionBadges = {}
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'bmc', label: 'Business Model Canvas', icon: Compass },
    { id: 'tech_stack', label: 'Technology Stack', icon: Cpu },
    { id: 'idea_validator', label: 'Idea Validator', icon: CheckCircle2 },
    { id: 'market_research', label: 'Market Research', icon: TrendingUp },
    { id: 'financials', label: 'Financial Worksheet', icon: Calculator },
    { id: 'execution_roadmap', label: 'Roadmap & Execution Plan', icon: Calendar },
    { id: 'blueprint_copilot', label: 'Planning Copilot', icon: Bot },
  ];

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Brand Header with Expand/Collapse Toggle */}
      <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="brand-logo">
          <div className="brand-icon-box" title="Venture Atlas">
            <Layers size={20} />
          </div>
          {!isCollapsed && (
            <div className="brand-titles">
              <h1>Venture Atlas</h1>
              <span>ENTERPRISE BLUEPRINT</span>
            </div>
          )}
        </div>

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: 4,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 4
          }}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Back to Dashboard */}
      <button
        onClick={onBackToDashboard}
        className="back-to-dashboard-btn"
        title="Back to Dashboard"
      >
        <ChevronLeft size={16} />
        {!isCollapsed && <span>Back to Dashboard</span>}
      </button>

      {/* Current Project Summary Header */}
      {!isCollapsed && (
        <div className="project-summary-card" style={{ padding: '10px 14px' }}>
          <div className="project-summary-header" style={{ marginBottom: 0 }}>
            <div className="project-name-edit">
              <span style={{ maxWidth: 170, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 600 }}>
                {currentProject?.id ? currentProject.name : 'Loading project…'}
              </span>
            </div>
            {currentProject?.stage ? (
              <span className="stage-pill-small">
                {currentProject.stage.includes('Growth') ? 'Growth' : currentProject.stage}
              </span>
            ) : null}
          </div>
        </div>
      )}

      {/* Vertical Navigation Items without redundant sidebar version badges */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeModule === item.id || (item.id === 'execution_roadmap' && activeModule === 'detailed_roadmap');
          const badge = moduleVersionBadges[item.id];
          const isCopilot = item.id === 'blueprint_copilot';
          const isOverview = item.id === 'overview';
          const isFinancials = item.id === 'financials';

          let status: ModuleBadgeStatus = 'unknown';
          if (isOverview || isFinancials) {
            status = 'generated';
          } else if (badge?.status) {
            status = badge.status;
          } else if (badge?.isGenerated === true) {
            status = 'generated';
          } else if (badge?.isGenerated === false) {
            status = 'not-generated';
          }

          let statusLabel = '';
          if (isActive) {
            statusLabel = 'Currently open';
          } else if (isCopilot) {
            statusLabel = 'Interactive assistant';
          } else if (status === 'generated') {
            statusLabel = 'Generated';
          } else if (status === 'not-generated') {
            statusLabel = 'Not generated';
          } else if (status === 'error') {
            statusLabel = 'Status check failed';
          } else if (status === 'loading') {
            statusLabel = 'Checking status';
          }

          const accessibilityTitle = statusLabel ? `${item.label} · ${statusLabel}` : item.label;
          const accessibilityLabel = statusLabel ? `${item.label}, ${statusLabel}` : item.label;

          return (
            <button
              key={item.id}
              data-module-id={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectModule(item.id)}
              onPointerEnter={() => onPrefetchModule?.(item.id)}
              onFocus={() => onPrefetchModule?.(item.id)}
              title={accessibilityTitle}
              aria-label={accessibilityLabel}
            >
              <div className="nav-item-left">
                <Icon size={17} />
                {!isCollapsed && <span>{item.label}</span>}
              </div>
              {!isCollapsed && (
                <div className="nav-item-right">
                  {isActive ? (
                    <span className="status-dot-active" aria-hidden="true" />
                  ) : isCopilot ? (
                    <span style={{ display: 'inline-flex', opacity: 0.7 }} aria-hidden="true"><Bot size={12} /></span>
                  ) : status === 'generated' ? (
                    <span className="status-dot-green" aria-hidden="true"><Check size={10} strokeWidth={3} /></span>
                  ) : status === 'not-generated' ? (
                    <span className="status-dot-gray" aria-hidden="true" />
                  ) : null}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer with Export PDF directly above Create New Project */}
      <div className="sidebar-footer">
        <button
          onClick={currentProject?.id ? onExportFullPdf : undefined}
          disabled={!currentProject?.id}
          className="export-project-btn"
          title="Export Project (PDF)"
        >
          <div className="export-project-btn-left">
            <div style={{ marginTop: 2, color: 'var(--text-muted)' }}>
              <Layers size={18} />
            </div>
            {!isCollapsed && (
              <div className="export-project-btn-titles">
                <h4>Export Project (PDF)</h4>
                <p>Complete multi-module PDF</p>
              </div>
            )}
          </div>
          {!isCollapsed && <ArrowRight size={15} color="var(--text-muted)" />}
        </button>

        <button
          onClick={onCreateNewProject}
          className="create-project-btn"
          title="Create New Project"
        >
          <Plus size={16} />
          {!isCollapsed && <span>Create New Project</span>}
        </button>
      </div>
    </aside>
  );
};
