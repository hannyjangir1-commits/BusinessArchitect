import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  ShieldAlert, CheckCircle2, AlertTriangle, Wrench, RefreshCw,
  Loader2, ShieldCheck, ArrowRight
} from 'lucide-react';

export const AdminDataIntegrityPage: React.FC = () => {
  const [scanResult, setScanResult] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [repairingAction, setRepairingAction] = useState<string | null>(null);

  const runScan = async () => {
    setLoading(true);
    try {
      const res = await api.admin.integrity.scan();
      setScanResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runScan();
  }, []);

  const handleRepair = async (action: string) => {
    if (!confirm(`Execute safe transactional repair: '${action}'?`)) return;
    setRepairingAction(action);
    try {
      const res = await api.admin.integrity.repair(action, true);
      alert(res.message || 'Repair executed successfully');
      runScan();
    } catch (err: any) {
      alert(err.message || 'Repair failed');
    } finally {
      setRepairingAction(null);
    }
  };

  const findings = scanResult?.findings || [];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: '0 0 4px' }}>
            Data Integrity & Automated Safe Repair
          </h1>
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
            Read-only relational invariant scanning, orphan record detection, and auditable atomic repairs
          </p>
        </div>
        <button
          onClick={runScan}
          disabled={loading}
          style={{ background: '#6366f1', color: '#ffffff', border: 'none', borderRadius: '6px', padding: '8px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600 }}
        >
          <RefreshCw size={14} className={loading ? 'spin-animate' : ''} />
          <span>Run Integrity Scan</span>
        </button>
      </div>

      {loading && !scanResult ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
          <Loader2 size={28} className="spin-animate" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
          <p style={{ margin: 0 }}>Scanning relational invariants...</p>
        </div>
      ) : findings.length === 0 ? (
        <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', padding: '48px 24px', textAlign: 'center', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '50%', backgroundColor: '#f0fdf4', color: '#16a34a', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <ShieldCheck size={32} />
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '0 0 6px' }}>
            All Invariants Passed — System Integrity 100% Clean
          </h3>
          <p style={{ fontSize: '13px', color: '#64748b', margin: '0 auto 16px', maxWidth: '500px' }}>
            No orphaned projects, dangling module contents, missing active versions, or circular dependencies detected.
          </p>
          <div style={{ fontSize: '12px', color: '#94a3b8' }}>
            Last scan: {new Date(scanResult?.scanned_at || Date.now()).toLocaleTimeString()}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {findings.map((f: any) => (
            <div
              key={f.code}
              style={{
                backgroundColor: '#ffffff',
                borderRadius: '12px',
                padding: '20px 24px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '16px'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      backgroundColor: f.severity === 'high' ? '#fee2e2' : f.severity === 'medium' ? '#fef3c7' : '#f1f5f9',
                      color: f.severity === 'high' ? '#b91c1c' : f.severity === 'medium' ? '#b45309' : '#475569'
                    }}
                  >
                    {f.severity}
                  </span>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                    {f.title}
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
                  {f.description}
                </p>
              </div>

              {f.repairable && f.repair_action && (
                <button
                  onClick={() => handleRepair(f.repair_action)}
                  disabled={repairingAction === f.repair_action}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: '#6366f1',
                    color: '#ffffff',
                    fontWeight: 600,
                    fontSize: '13px',
                    cursor: repairingAction === f.repair_action ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  {repairingAction === f.repair_action ? (
                    <Loader2 size={14} className="spin-animate" />
                  ) : (
                    <Wrench size={14} />
                  )}
                  <span>Execute Safe Repair</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
