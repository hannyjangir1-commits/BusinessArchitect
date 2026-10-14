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
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="#ef4444" />
            </div>
            <span>30-Day Milestone</span>
          </div>
          <span className="milestone-pct">{summary.milestone_30_progress}%</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_30_progress}%`, background: '#ef4444' }}
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
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#dbeafe', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="#3b82f6" />
            </div>
            <span>60-Day Milestone</span>
          </div>
          <span className="milestone-pct">{summary.milestone_60_progress}%</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_60_progress}%`, background: '#3b82f6' }}
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
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="#eab308" />
            </div>
            <span>90-Day Milestone</span>
          </div>
          <span className="milestone-pct">{summary.milestone_90_progress}%</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_90_progress}%`, background: '#eab308' }}
          />
        </div>
        <div className="milestone-count-text">
          {summary.milestone_90_completed} / {summary.milestone_90_total} tasks completed
        </div>
      </div>
    </div>
  );
};
