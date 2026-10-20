import React from 'react';
import { RoadmapSummary } from '../types';
import { Flag } from 'lucide-react';

interface Props {
  summary: RoadmapSummary;
}

export const MilestoneCards: React.FC<Props> = ({ summary }) => {
  return (
    <div className="milestones-grid">
      {/* 30-Day Milestone */}
      <div className="milestone-card">
        <div className="milestone-top">
          <div className="milestone-flag-title">
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="var(--danger-text)" />
            </div>
            <span>30-Day Milestone</span>
          </div>
          <span className="milestone-pct">{summary.milestone_30_progress}%</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_30_progress}%`, background: 'var(--danger-text)' }}
          />
        </div>
        <div className="milestone-count-text">
          {summary.milestone_30_completed} / {summary.milestone_30_total} tasks completed
        </div>
      </div>

      {/* 60-Day Milestone */}
      <div className="milestone-card">
        <div className="milestone-top">
          <div className="milestone-flag-title">
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="var(--text-muted)" />
            </div>
            <span>60-Day Milestone</span>
          </div>
          <span className="milestone-pct">{summary.milestone_60_progress}%</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_60_progress}%`, background: 'var(--bg-subtle)' }}
          />
        </div>
        <div className="milestone-count-text">
          {summary.milestone_60_completed} / {summary.milestone_60_total} tasks completed
        </div>
      </div>

      {/* 90-Day Milestone */}
      <div className="milestone-card">
        <div className="milestone-top">
          <div className="milestone-flag-title">
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="var(--primary-text)" />
            </div>
            <span>90-Day Milestone</span>
          </div>
          <span className="milestone-pct">{summary.milestone_90_progress}%</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_90_progress}%`, background: 'var(--bg-subtle)' }}
          />
        </div>
        <div className="milestone-count-text">
          {summary.milestone_90_completed} / {summary.milestone_90_total} tasks completed
        </div>
      </div>
    </div>
  );
};
