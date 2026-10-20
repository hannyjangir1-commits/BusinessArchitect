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
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: 'var(--primary-text)' }} />
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
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 4px' }}>
            Product Analytics & Conversion Funnel
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            End-to-end user journey analysis: registration to project creation, module adoption, and final blueprint export
          </p>
        </div>
        <button
          onClick={fetchAnalytics}
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600 }}
        >
          <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* 6-Step Conversion Funnel */}
      <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '24px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)', marginBottom: '28px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
          Platform Activation Funnel
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '20px' }}>
          Conversion across core architectural milestone steps
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {funnel.map((step: any) => {
            const widthPct = Math.max(8, step.conversion_rate);
            return (
              <div key={step.step}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', fontSize: '13px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                    {step.step}. {step.name}
                  </span>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>{step.count} users</span>
                    <span style={{ fontWeight: 700, color: 'var(--primary-text)', minWidth: '50px', textAlign: 'right' }}>
                      {step.conversion_rate}%
                    </span>
                  </div>
                </div>
                <div style={{ width: '100%', height: '14px', backgroundColor: 'var(--bg-subtle)', borderRadius: '6px', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${widthPct}%`,
                      height: '100%',
                      background: 'var(--primary-light)',
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
      <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '24px', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgb(69 60 55 / 0.05)', marginBottom: '28px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '16px' }}>
          Feature & Module Adoption
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          {Object.entries(moduleAdoption).map(([key, stat]: any) => (
            <div key={key} style={{ padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)', backgroundColor: 'var(--bg-subtle)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                {key.replace('_', ' ')}
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
                {stat.rate}%
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {stat.count} projects adopting
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Product Analytics Events */}
      <div style={{ backgroundColor: 'var(--bg-card)', borderRadius: '12px', padding: '20px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '14px' }}>
          Recent Telemetry Event Stream
        </h3>
        {events.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: 0 }}>No analytics events recorded yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {events.map((e: any) => (
              <div key={e.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--bg-subtle)', borderRadius: '6px', fontSize: '12px' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{e.event_name}</span>
                <span style={{ color: 'var(--text-muted)' }}>{new Date(e.created_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
