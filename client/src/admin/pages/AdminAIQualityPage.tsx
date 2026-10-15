import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { RefreshCw, Loader2 } from 'lucide-react';

export const AdminAIQualityPage: React.FC = () => {
  const [quality, setQuality] = useState<any | null>(null);
  const [stats, setStats] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchQuality = async () => {
    setLoading(true);
    try {
      const [qRes, sRes] = await Promise.all([
        api.admin.aiOps.getQuality(),
        api.admin.aiOps.getStats()
      ]);
      setQuality(qRes);
      setStats(sRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuality();
  }, []);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 4px' }}>
            Output Quality & Reliability Observability
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Application-level schema validation tracking, structured output parsing integrity, and module performance
          </p>
        </div>
        <button
          onClick={fetchQuality}
          style={{ background: 'var(--bg-card)', color: 'var(--text-main)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600 }}
        >
          <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {loading && !quality ? (
        <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: 'var(--primary)' }} />
          <p style={{ margin: 0 }}>Evaluating output quality validation metrics...</p>
        </div>
      ) : (
        <>
          {/* Quality Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px', marginBottom: '28px' }}>
            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Validation Pass Rate</div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: '#16a34a', marginTop: '6px' }}>
                {quality?.structured_validation_rate || 100}%
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
                {quality?.structured_validation_passed || 0} of {quality?.total_evaluated_operations || 0} passed
              </div>
            </div>

            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Parse Failures</div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: quality?.parse_failures > 0 ? '#ef4444' : '#10b981', marginTop: '6px' }}>
                {quality?.parse_failures || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
                JSON schema parse exceptions
              </div>
            </div>

            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Persistence Failures</div>
              <div style={{ fontSize: '28px', fontWeight: 800, color: quality?.persistence_failures > 0 ? '#ef4444' : '#10b981', marginTop: '6px' }}>
                {quality?.persistence_failures || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
                Database commit failures
              </div>
            </div>
          </div>

          {/* Module-by-Module Reliability Breakdown */}
          <div style={{ background: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '16px' }}>
              Module-Specific Performance & Reliability
            </h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700, fontSize: '11px', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 16px' }}>Module</th>
                  <th style={{ padding: '12px 16px' }}>Total Operations</th>
                  <th style={{ padding: '12px 16px' }}>Success Rate</th>
                  <th style={{ padding: '12px 16px' }}>Average Duration</th>
                </tr>
              </thead>
              <tbody>
                {(stats?.module_performance || []).map((m: any) => (
                  <tr key={m.module_type} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0f172a' }}>
                      {m.module_type.replace('_', ' ').toUpperCase()}
                    </td>
                    <td style={{ padding: '12px 16px', color: '#334155' }}>{m.total}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ fontWeight: 700, color: m.success_rate >= 80 ? '#16a34a' : '#ef4444' }}>
                        {m.success_rate}%
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b' }}>{m.avg_duration_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
