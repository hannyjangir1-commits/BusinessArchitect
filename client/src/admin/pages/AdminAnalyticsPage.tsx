import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { RefreshCw, Loader2 } from 'lucide-react';

export const AdminAnalyticsPage: React.FC = () => {
  const [data, setData] = useState<any | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const [overviewRes, eventsRes] = await Promise.all([
        api.admin.analytics.getOverview(),
        api.admin.analytics.listEvents({ limit: 15 })
      ]);
      setData(overviewRes);
      setEvents(eventsRes.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading && !data) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
        <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
        <p style={{ margin: 0 }}>Compiling conversion funnel and product adoption analytics...</p>
      </div>
    );
  }

  const funnel = data?.funnel || [];
  const moduleAdoption = data?.module_adoption || {};

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: '0 0 4px' }}>
            Product Analytics & Conversion Funnel
          </h1>
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
            End-to-end user journey analysis: registration to project creation, module adoption, and final blueprint export
          </p>
        </div>
        <button
          onClick={fetchAnalytics}
          style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600 }}
        >
          <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* 6-Step Conversion Funnel */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '28px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
          Platform Activation Funnel
        </h3>
        <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '20px' }}>
          Conversion across core architectural milestone steps
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {funnel.map((step: any, idx: number) => {
            const widthPct = Math.max(8, step.conversion_rate);
            return (
              <div key={step.step}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', fontSize: '13px' }}>
                  <span style={{ fontWeight: 600, color: '#0f172a' }}>
                    {step.step}. {step.name}
                  </span>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: '#334155' }}>{step.count} users</span>
                    <span style={{ fontWeight: 700, color: '#6366f1', minWidth: '50px', textAlign: 'right' }}>
                      {step.conversion_rate}%
                    </span>
                  </div>
                </div>
                <div style={{ width: '100%', height: '14px', backgroundColor: '#f1f5f9', borderRadius: '6px', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${widthPct}%`,
                      height: '100%',
                      background: `linear-gradient(90deg, #6366f1 0%, ${idx === 5 ? '#10b981' : '#818cf8'} 100%)`,
                      borderRadius: '6px',
                      transition: 'width 0.4s ease'
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Module Adoption Grid */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '28px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '16px' }}>
          Feature & Module Adoption
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          {Object.entries(moduleAdoption).map(([key, stat]: any) => (
            <div key={key} style={{ padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700, textTransform: 'uppercase' }}>
                {key.replace('_', ' ')}
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                {stat.rate}%
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                {stat.count} projects adopting
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Product Analytics Events */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a', marginBottom: '14px' }}>
          Recent Telemetry Event Stream
        </h3>
        {events.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>No analytics events recorded yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {events.map((e: any) => (
              <div key={e.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: '#f8fafc', borderRadius: '6px', fontSize: '12px' }}>
                <span style={{ fontWeight: 600, color: '#0f172a' }}>{e.event_name}</span>
                <span style={{ color: '#64748b' }}>{new Date(e.created_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
