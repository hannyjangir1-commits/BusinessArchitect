import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  Sliders, Cpu, RefreshCw,
  Loader2, CheckCircle2, AlertTriangle, Save, Lock
} from 'lucide-react';

export const AdminConfigPage: React.FC = () => {
  const [runtimeSettings, setRuntimeSettings] = useState<any[]>([]);
  const [envStatus, setEnvStatus] = useState<any[]>([]);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await api.admin.config.get();
      setRuntimeSettings(res.runtime_settings || []);
      setEnvStatus(res.environment_status || []);

      const initialValues: Record<string, string> = {};
      (res.runtime_settings || []).forEach((s: any) => {
        initialValues[s.key] = s.value;
      });
      setFormValues(initialValues);
    } catch (e: any) {
      console.error(e);
      setStatusMsg({ type: 'error', text: e.message || 'Failed to load configuration' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleChange = (key: string, val: string) => {
    setFormValues((prev) => ({ ...prev, [key]: val }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setStatusMsg(null);
    try {
      const res = await api.admin.config.update(formValues);
      setStatusMsg({ type: 'success', text: res.message || 'Configuration saved successfully.' });
      fetchConfig();
    } catch (err: any) {
      setStatusMsg({ type: 'error', text: err.message || 'Failed to save configuration.' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sliders size={26} color="#6366f1" />
            Configuration Center
          </h1>
          <p style={{ margin: '6px 0 0', color: '#94a3b8', fontSize: '14px' }}>
            Manage safe runtime settings, processing service parameters, security limits, and inspect configuration status.
          </p>
        </div>
        <button
          onClick={() => fetchConfig()}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: '#1e293b',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '8px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            fontWeight: 500
          }}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {statusMsg && (
        <div
          style={{
            padding: '14px 18px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: statusMsg.type === 'success' ? '#064e3b33' : '#7f1d1d33',
            border: `1px solid ${statusMsg.type === 'success' ? '#059669' : '#dc2626'}`,
            color: statusMsg.type === 'success' ? '#34d399' : '#f87171'
          }}
        >
          {statusMsg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          {statusMsg.text}
        </div>
      )}

      {/* Secret / Environment Status (Non-editable, Safe Masked View) */}
      <div
        style={{
          backgroundColor: '#0f172a',
          borderRadius: '12px',
          border: '1px solid #1e293b',
          padding: '24px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <Lock size={20} color="#f59e0b" />
          <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc' }}>
            Deployment Environment & Secrets Verification
          </h2>
        </div>
        <p style={{ margin: '0 0 20px', color: '#94a3b8', fontSize: '13px' }}>
          Sensitive credentials are never displayed, committed, or returned through APIs. Status flags verify presence only.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
          {envStatus.map((item) => (
            <div
              key={item.name}
              style={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '10px',
                padding: '16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <div>
                <div style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '13px', color: '#f8fafc' }}>
                  {item.name}
                </div>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                  Category: {item.category}
                </div>
                {item.value && (
                  <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                    Active: {item.value}
                  </div>
                )}
              </div>
              <div>
                {item.configured ? (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '4px 10px',
                      borderRadius: '999px',
                      backgroundColor: '#065f46',
                      color: '#a7f3d0',
                      fontSize: '11px',
                      fontWeight: 600
                    }}
                  >
                    <CheckCircle2 size={12} /> Configured
                  </span>
                ) : (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '4px 10px',
                      borderRadius: '999px',
                      backgroundColor: '#7f1d1d',
                      color: '#fecaca',
                      fontSize: '11px',
                      fontWeight: 600
                    }}
                  >
                    <AlertTriangle size={12} /> Missing
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Runtime Settings Form */}
      <form onSubmit={handleSave}>
        <div
          style={{
            backgroundColor: '#0f172a',
            borderRadius: '12px',
            border: '1px solid #1e293b',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Cpu size={20} color="#6366f1" />
                Validated Runtime Parameters
              </h2>
              <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '13px' }}>
                Changes are applied immediately and recorded in the audit trail.
              </p>
            </div>
            <button
              type="submit"
              disabled={saving || loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 20px',
                backgroundColor: '#6366f1',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '13px',
                cursor: saving || loading ? 'not-allowed' : 'pointer'
              }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>

          {loading ? (
            <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
              <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
              Loading settings...
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {runtimeSettings.map((s) => (
                <div
                  key={s.key}
                  style={{
                    padding: '16px',
                    backgroundColor: '#1e293b',
                    borderRadius: '10px',
                    border: '1px solid #334155',
                    display: 'grid',
                    gridTemplateColumns: 'minmax(240px, 1fr) 200px',
                    gap: '16px',
                    alignItems: 'center'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '13px', color: '#f8fafc' }}>
                        {s.key}
                      </span>
                      <span
                        style={{
                          fontSize: '10px',
                          textTransform: 'uppercase',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: '#0f172a',
                          color: '#94a3b8',
                          border: '1px solid #334155'
                        }}
                      >
                        {s.category}
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                      {s.description}
                    </div>
                  </div>

                  <div>
                    {s.type === 'boolean' ? (
                      <select
                        value={formValues[s.key] || 'false'}
                        onChange={(e) => handleChange(s.key, e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          backgroundColor: '#0f172a',
                          border: '1px solid #334155',
                          borderRadius: '6px',
                          color: '#f8fafc',
                          fontSize: '13px',
                          outline: 'none'
                        }}
                      >
                        <option value="true">Enabled (true)</option>
                        <option value="false">Disabled (false)</option>
                      </select>
                    ) : (
                      <input
                        type={s.type === 'int' ? 'number' : 'text'}
                        value={formValues[s.key] !== undefined ? formValues[s.key] : ''}
                        onChange={(e) => handleChange(s.key, e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          backgroundColor: '#0f172a',
                          border: '1px solid #334155',
                          borderRadius: '6px',
                          color: '#f8fafc',
                          fontSize: '13px',
                          fontFamily: s.type === 'int' ? 'monospace' : 'inherit',
                          outline: 'none'
                        }}
                      />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </form>
    </div>
  );
};
