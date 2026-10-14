import React from 'react';
import { Project } from '../types';
import {
  Layers, ChevronLeft, Edit2, LayoutDashboard, Compass, Cpu, CheckCircle2,
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
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'bmc', label: 'Business Model Canvas', icon: Compass },
    { id: 'tech_stack', label: 'Technology Stack', icon: Cpu },
    { id: 'idea_validator', label: 'Idea Validator', icon: CheckCircle2 },
    { id: 'market_research', label: 'Market Research', icon: TrendingUp },
    { id: 'execution_roadmap', label: 'Execution Roadmap', icon: Calendar },
    { id: 'detailed_roadmap', label: 'Detailed Roadmap', icon: ListTodo },
    { id: 'blueprint_copilot', label: 'Blueprint Copilot', icon: Bot },
  ];

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand-logo">
          <div className="brand-icon-box">
            <Layers size={20} />
          </div>
          <div className="brand-titles">
            <h1>AI Business Architect</h1>
            <span>ENTERPRISE BLUEPRINT</span>
          </div>
        </div>
      </div>

      {/* Back to Dashboard */}
      <button onClick={onBackToDashboard} className="back-to-dashboard-btn">
        <ChevronLeft size={16} />
        <span>Back to Dashboard</span>
      </button>

      {/* Current Project Summary Pill Card */}
      <div className="project-summary-card">
        <div className="project-summary-header">
          <div className="project-name-edit">
            <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentProject.name}
            </span>
            <Edit2 size={12} color="#94a3b8" />
          </div>
          <span className="stage-pill-small">
            {currentProject.stage.includes('Growth') ? 'Growth Stage' : currentProject.stage}
          </span>
        </div>
        <div className="project-progress-bar-container">
          <div className="project-progress-track">
            <div
              className="project-progress-fill"
              style={{ width: `${currentProject.progress_percentage || 50}%` }}
            />
          </div>
          <span className="project-progress-text">
            {currentProject.progress_percentage || 50}%
          </span>
        </div>
      </div>

      {/* Vertical Navigation Items */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeModule === item.id;
          const badge = moduleVersionBadges[item.id] || { version: 'V1', isGenerated: true };

          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectModule(item.id)}
            >
              <div className="nav-item-left">
                <Icon size={17} />
                <span>{item.label}</span>
              </div>
              <div className="nav-item-right">
                <span className="version-badge">{badge.version}</span>
                {isActive ? (
                  <span className="status-dot-active" />
                ) : badge.isGenerated ? (
                  <span className="status-dot-green"><Check size={10} strokeWidth={3} /></span>
                ) : (
                  <span className="status-dot-gray" />
                )}
              </div>
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer with Export PDF directly above Create New Project */}
      <div className="sidebar-footer">
        <button onClick={onExportFullPdf} className="export-project-btn">
          <div className="export-project-btn-left">
            <div style={{ marginTop: 2, color: '#818cf8' }}>
              <Layers size={18} />
            </div>
            <div className="export-project-btn-titles">
              <h4>Export Project (PDF)</h4>
              <p>Export all modules (except history, copilot chat and audit)</p>
            </div>
          </div>
          <ArrowRight size={15} color="#818cf8" />
        </button>

        <button onClick={onCreateNewProject} className="create-project-btn">
          <Plus size={16} />
          <span>Create New Project</span>
        </button>
      </div>
    </aside>
  );
};
