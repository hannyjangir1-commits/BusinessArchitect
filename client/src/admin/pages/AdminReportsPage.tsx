import React from 'react';
import { api } from '../../services/api';
import {
  FileText, Download, ShieldCheck,
  Users, FolderKanban, Cpu, ClipboardList
} from 'lucide-react';

export const AdminReportsPage: React.FC = () => {
  const reports = [
    {
      id: 'users',
      title: 'Users Directory Export',
      desc: 'All registered users, emails, account status, roles, and registration dates.',
      format: 'CSV (Formula-Sanitized)',
      icon: Users,
      action: () => api.admin.reports.downloadCsv('users')
    },
    {
      id: 'projects',
      title: 'Projects Console Export',
      desc: 'All business architecture projects, stages, industries, and active modules.',
      format: 'CSV (Formula-Sanitized)',
      icon: FolderKanban,
      action: () => api.admin.reports.downloadCsv('projects')
    },
    {
      id: 'ai_operations',
      title: 'Generation Telemetry Operations Log',
      desc: 'Granular logs of all generation operations, latency (ms), processing engines, and error categories.',
      format: 'CSV (Formula-Sanitized)',
      icon: Cpu,
      action: () => api.admin.reports.downloadCsv('ai_operations')
    },
    {
      id: 'audit_logs',
      title: 'Administrative Audit Trail',
      desc: 'Complete immutable server-side audit logs for compliance and forensics.',
      format: 'CSV (Formula-Sanitized)',
      icon: ClipboardList,
      action: () => api.admin.reports.downloadCsv('audit_logs')
    },
    {
      id: 'summary_pdf',
      title: 'Executive Platform Status Brief',
      desc: 'Formatted multi-section PDF summary with KPIs, database health, and governance status.',
      format: 'PDF Document',
      icon: FileText,
      action: () => api.admin.reports.downloadPdf()
    }
  ];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: '0 0 4px' }}>
          Reports & Data Exports
        </h1>
        <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>
          Export operational datasets with verified spreadsheet formula injection protection
        </p>
      </div>

      {/* Security alert callout */}
      <div
        style={{
          backgroundColor: '#eff6ff',
          border: '1px solid #bfdbfe',
          borderRadius: '10px',
          padding: '14px 18px',
          marginBottom: '28px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#1e40af',
          fontSize: '13px'
        }}
      >
        <ShieldCheck size={20} style={{ flexShrink: 0, color: '#2563eb' }} />
        <div>
          <strong>Security Protection Enforced:</strong> All CSV exports are sanitized on the server against CSV/Formula Injection attacks. Any fields beginning with formula triggers (<code>=</code>, <code>+</code>, <code>-</code>, <code>@</code>) are safely prefixed with single quotes.
        </div>
      </div>

      {/* Report Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {reports.map(rep => {
          const Icon = rep.icon;
          return (
            <div
              key={rep.id}
              style={{
                backgroundColor: '#ffffff',
                borderRadius: '12px',
                padding: '24px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                  <div
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '10px',
                      backgroundColor: rep.id === 'summary_pdf' ? '#ede9fe' : '#e0e7ff',
                      color: rep.id === 'summary_pdf' ? '#7c3aed' : '#4338ca',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    <Icon size={20} />
                  </div>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      backgroundColor: '#f1f5f9',
                      color: '#475569'
                    }}
                  >
                    {rep.format}
                  </span>
                </div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', margin: '0 0 6px' }}>
                  {rep.title}
                </h3>
                <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.5, margin: 0 }}>
                  {rep.desc}
                </p>
              </div>

              <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid #f1f5f9' }}>
                <button
                  onClick={rep.action}
                  style={{
                    width: '100%',
                    padding: '9px 16px',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    backgroundColor: '#ffffff',
                    color: '#0f172a',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.backgroundColor = '#6366f1';
                    e.currentTarget.style.borderColor = '#6366f1';
                    e.currentTarget.style.color = '#ffffff';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.backgroundColor = '#ffffff';
                    e.currentTarget.style.borderColor = '#cbd5e1';
                    e.currentTarget.style.color = '#0f172a';
                  }}
                >
                  <Download size={15} />
                  <span>Download Report</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
