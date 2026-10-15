import React, { useState } from 'react';
import { Project } from '../types';
import {
  Layers, ChevronLeft, ChevronRight, LayoutDashboard, Compass, Cpu, CheckCircle2,
  TrendingUp, Calendar, ListTodo, Bot, ArrowRight, Plus, Check
} from 'lucide-react';

interface Props {
  currentProject: Project;
  activeModule: string;
  onSelectModule: (module: string) => void;
  onBackToDashboard: () => void;
  onCreateNewProject: () => void;
  onExportFullPdf: () => void;
  moduleVersionBadges?: Record<string, { version: string; isGenerated: boolean }>;
}

export const Sidebar: React.FC<Props> = ({
  currentProject,
  activeModule,
  onSelectModule,
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
    { id: 'execution_roadmap', label: 'Execution Roadmap', icon: Calendar },
    { id: 'detailed_roadmap', label: 'Detailed Roadmap', icon: ListTodo },
    { id: 'blueprint_copilot', label: 'Planning Assistant', icon: Bot },
  ];

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Brand Header with Expand/Collapse Toggle */}
      <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="brand-logo">
          <div className="brand-icon-box" title="Business Architect">
            <Layers size={20} />
          </div>
          {!isCollapsed && (
            <div className="brand-titles">
              <h1>Business Architect</h1>
              <span>ENTERPRISE BLUEPRINT</span>
            </div>
          )}
        </div>

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#94a3b8',
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
                {currentProject.name}
              </span>
            </div>
            <span className="stage-pill-small">
              {currentProject.stage.includes('Growth') ? 'Growth' : currentProject.stage}
            </span>
          </div>
        </div>
      )}

      {/* Vertical Navigation Items without redundant sidebar version badges */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeModule === item.id;
          const badge = moduleVersionBadges[item.id] || { version: 'V1', isGenerated: true };

          return (
            <button
              key={item.id}
              data-module-id={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectModule(item.id)}
              title={item.label}
              aria-label={item.label}
            >
              <div className="nav-item-left">
                <Icon size={17} />
                {!isCollapsed && <span>{item.label}</span>}
              </div>
              {!isCollapsed && (
                <div className="nav-item-right">
                  {isActive ? (
                    <span className="status-dot-active" />
                  ) : badge.isGenerated ? (
                    <span className="status-dot-green"><Check size={10} strokeWidth={3} /></span>
                  ) : (
                    <span className="status-dot-gray" />
                  )}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer with Export PDF directly above Create New Project */}
      <div className="sidebar-footer">
        <button
          onClick={onExportFullPdf}
          className="export-project-btn"
          title="Export Project (PDF)"
        >
          <div className="export-project-btn-left">
            <div style={{ marginTop: 2, color: '#818cf8' }}>
              <Layers size={18} />
            </div>
            {!isCollapsed && (
              <div className="export-project-btn-titles">
                <h4>Export Project (PDF)</h4>
                <p>Complete multi-module PDF</p>
              </div>
            )}
          </div>
          {!isCollapsed && <ArrowRight size={15} color="#818cf8" />}
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
