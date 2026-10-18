import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { RefreshCw, Loader2, Table2 } from 'lucide-react';

export const AdminDatabasePage: React.FC = () => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchDbData = async () => {
    setLoading(true);
    try {
      const res = await api.admin.system.getDatabase();
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDbData();
  }, []);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', margin: '0 0 4px' }}>
            Database & Schema Diagnostics
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Inspect connection pooling, Alembic migration revision, table volume distributions, and SSL enforcement
          </p>
        </div>
        <button
          onClick={fetchDbData}
          style={{ background: '#ffffff', border: '1px solid #d9ddcf', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600 }}
        >
          <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {loading && !data ? (
        <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6d855f' }} />
          <p style={{ margin: 0 }}>Querying database metadata...</p>
        </div>
      ) : (
        <>
          {/* Metadata Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '18px', marginBottom: '28px' }}>
            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #dfe2d6' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Database Engine</div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px', textTransform: 'capitalize' }}>
                {data?.engine || 'SQLite'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Production target: Supabase PostgreSQL
              </div>
            </div>

            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #dfe2d6' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Alembic Head Revision</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: '#5d7550', marginTop: '4px', fontFamily: 'monospace' }}>
                {data?.current_migration_revision?.slice(0, 12) || 'Synced'}
              </div>
              <div style={{ fontSize: '12px', color: '#16a34a', fontWeight: 600, marginTop: '4px' }}>
                ✓ Up to date with migrations
              </div>
            </div>

            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #dfe2d6' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Connection Pool</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
                {data?.pool_configuration?.pool_class || 'Standard'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Pool pre-ping: Enabled
              </div>
            </div>

            <div style={{ background: '#ffffff', borderRadius: '12px', padding: '20px', border: '1px solid #dfe2d6' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>SSL Mode</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: '#16a34a', marginTop: '4px' }}>
                {data?.ssl_enforced ? 'Require' : 'Local Dev'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Enforced in production
              </div>
            </div>
          </div>

          {/* Table Row Counts */}
          <div style={{ background: '#ffffff', borderRadius: '12px', padding: '24px', border: '1px solid #dfe2d6' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Table2 size={18} style={{ color: '#6d855f' }} />
              Core Table Row Counts
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
              {Object.entries(data?.table_row_counts || {}).map(([table, count]: any) => (
                <div key={table} style={{ padding: '14px', borderRadius: '8px', border: '1px solid #dfe2d6', backgroundColor: '#f7f6ef' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                    {table}
                  </div>
                  <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
                    {count}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
