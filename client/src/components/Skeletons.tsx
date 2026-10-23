import React from 'react';

/**
 * Accessible skeleton for project grid cards in DashboardPage.
 */
export const ProjectGridSkeleton: React.FC<{ count?: number }> = ({ count = 3 }) => {
  return (
    <div
      className="project-grid"
      role="status"
      aria-busy="true"
      aria-label="Loading projects"
      style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 20 }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="card skeleton-card"
          style={{
            padding: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            border: '1px solid var(--border-color)',
            background: 'var(--bg-card)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="skeleton skeleton-pulse" style={{ width: '55%', height: 20, borderRadius: 6 }} />
            <div className="skeleton skeleton-pulse" style={{ width: 60, height: 22, borderRadius: 12 }} />
          </div>
          <div className="skeleton skeleton-pulse" style={{ width: '85%', height: 14, borderRadius: 4 }} />
          <div className="skeleton skeleton-pulse" style={{ width: '40%', height: 14, borderRadius: 4 }} />

          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <div className="skeleton skeleton-pulse" style={{ width: 80, height: 12, borderRadius: 4 }} />
              <div className="skeleton skeleton-pulse" style={{ width: 32, height: 12, borderRadius: 4 }} />
            </div>
            <div className="skeleton skeleton-pulse" style={{ width: '100%', height: 6, borderRadius: 4 }} />
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <div className="skeleton skeleton-pulse" style={{ width: 70, height: 26, borderRadius: 6 }} />
            <div className="skeleton skeleton-pulse" style={{ width: 70, height: 26, borderRadius: 6 }} />
            <div className="skeleton skeleton-pulse" style={{ width: 70, height: 26, borderRadius: 6 }} />
          </div>
        </div>
      ))}
    </div>
  );
};

/**
 * Accessible skeleton for active module views in Workspace.
 */
export const ModuleSkeleton: React.FC<{ moduleType?: string }> = ({ moduleType = 'module' }) => {
  return (
    <div
      className="module-skeleton"
      role="status"
      aria-busy="true"
      aria-label={`Loading ${moduleType} content`}
      style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}
    >
      {/* Module Header Bar Skeleton */}
      <div
        className="card"
        style={{
          padding: '16px 22px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          border: '1px solid var(--border-color)',
          background: 'var(--bg-card)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div className="skeleton skeleton-pulse" style={{ width: 40, height: 40, borderRadius: 10 }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="skeleton skeleton-pulse" style={{ width: 220, height: 22, borderRadius: 6 }} />
            <div className="skeleton skeleton-pulse" style={{ width: 140, height: 14, borderRadius: 4 }} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div className="skeleton skeleton-pulse" style={{ width: 90, height: 34, borderRadius: 8 }} />
          <div className="skeleton skeleton-pulse" style={{ width: 110, height: 34, borderRadius: 8 }} />
        </div>
      </div>

      {/* Content Grid Skeleton */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="card"
            style={{
              padding: 20,
              minHeight: 140,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)'
            }}
          >
            <div className="skeleton skeleton-pulse" style={{ width: '45%', height: 18, borderRadius: 4 }} />
            <div className="skeleton skeleton-pulse" style={{ width: '90%', height: 14, borderRadius: 4 }} />
            <div className="skeleton skeleton-pulse" style={{ width: '75%', height: 14, borderRadius: 4 }} />
            <div className="skeleton skeleton-pulse" style={{ width: '60%', height: 14, borderRadius: 4 }} />
          </div>
        ))}
      </div>
    </div>
  );
};
