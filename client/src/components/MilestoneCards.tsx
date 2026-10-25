import React from 'react';
import { RoadmapSummary } from '../types';
import { Flag } from 'lucide-react';

interface Props {
  summary: RoadmapSummary;
}

export const MilestoneCards: React.FC<Props> = ({ summary }) => {
  return (
    <div className="milestones-grid">
      {/* 30-Day Cumulative Milestone */}
      <div className="milestone-card">
        <div className="milestone-top">
          <div className="milestone-flag-title">
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="var(--primary-text)" />
            </div>
            <span>Due by Day 30 (Cumulative)</span>
          </div>
          <span className="milestone-pct">{summary.milestone_30_total > 0 ? `${summary.milestone_30_progress}%` : '—'}</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_30_progress}%`, background: 'var(--primary)' }}
          />
        </div>
        <div className="milestone-count-text">
          {summary.milestone_30_total > 0
            ? `${summary.milestone_30_completed} of ${summary.milestone_30_total} tasks completed`
            : 'No tasks scheduled in this window'}
        </div>
      </div>

      {/* 60-Day Cumulative Milestone */}
      <div className="milestone-card">
        <div className="milestone-top">
          <div className="milestone-flag-title">
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="var(--primary-text)" />
            </div>
            <span>Due by Day 60 (Cumulative)</span>
          </div>
          <span className="milestone-pct">{summary.milestone_60_total > 0 ? `${summary.milestone_60_progress}%` : '—'}</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_60_progress}%`, background: 'var(--primary)' }}
          />
        </div>
        <div className="milestone-count-text">
          {summary.milestone_60_total > 0
            ? `${summary.milestone_60_completed} of ${summary.milestone_60_total} tasks completed`
            : 'No tasks scheduled in this window'}
        </div>
      </div>

      {/* 90-Day Cumulative Milestone */}
      <div className="milestone-card">
        <div className="milestone-top">
          <div className="milestone-flag-title">
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={14} color="var(--primary-text)" />
            </div>
            <span>Due by Day 90 (Cumulative)</span>
          </div>
          <span className="milestone-pct">{summary.milestone_90_total > 0 ? `${summary.milestone_90_progress}%` : '—'}</span>
        </div>
        <div className="milestone-track">
          <div
            className="milestone-fill"
            style={{ width: `${summary.milestone_90_progress}%`, background: 'var(--primary)' }}
          />
        </div>
        <div className="milestone-count-text">
          {summary.milestone_90_total > 0
            ? `${summary.milestone_90_completed} of ${summary.milestone_90_total} tasks completed`
            : 'No tasks scheduled in this window'}
        </div>
      </div>
    </div>
  );
};
