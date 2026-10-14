import React, { useState } from 'react';
import { VersionItem } from '../types';
import { ChevronDown, Download, Edit3, Trash2, GitCompare, RotateCcw } from 'lucide-react';

interface Props {
  moduleType: string;
  moduleTitle: string;
  activeVersionName?: string;
  activeVersionNumber?: number;
  versions: VersionItem[];
  onRename: (newName: string) => Promise<void>;
  onDelete: (versionId: string) => Promise<void>;
  onRestore: (versionId: string) => Promise<void>;
  onExportPdf: () => void;
  onExportSvg?: () => void;
}

export const VersionToolbar: React.FC<Props> = ({
  moduleType: _moduleType,
  moduleTitle,
  activeVersionName,
  activeVersionNumber,
  versions,
  onRename,
  onDelete,
  onRestore,
  onExportPdf,
  onExportSvg
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [newName, setNewName] = useState(activeVersionName || '');

  const activeVersion = versions.find(v => v.is_active) || versions[versions.length - 1];

  const handleOpenRename = () => {
    setNewName(activeVersion?.version_name || '');
    setRenameModalOpen(true);
  };

  const handleSaveRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await onRename(newName.trim());
    setRenameModalOpen(false);
  };

  const handleDeleteActive = async () => {
    if (!activeVersion) return;
    if (versions.length <= 1) {
      alert('Cannot delete the only saved version of this module.');
      return;
    }
    if (window.confirm(`Are you sure you want to delete ${activeVersion.version_name}?`)) {
      await onDelete(activeVersion.id);
    }
  };

  return (
    <div className="module-toolbar" style={{ position: 'relative' }}>
      {/* Export This Module Dropdown */}
      <div style={{ position: 'relative' }}>
        <button
          className="btn-secondary"
          onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
        >
          <Download size={14} color="#6366f1" />
          <span>Export This Module</span>
          <ChevronDown size={14} />
        </button>

        {exportDropdownOpen && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 4,
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
              width: 180,
              zIndex: 100,
              overflow: 'hidden'
            }}
          >
            <button
              onClick={() => { setExportDropdownOpen(false); onExportPdf(); }}
              style={{
                width: '100%',
                padding: '9px 12px',
                textAlign: 'left',
                border: 'none',
                background: 'transparent',
                fontSize: 12.5,
                color: '#0f172a',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}
            >
              📄 Download PDF
            </button>
            {onExportSvg && (
              <button
                onClick={() => { setExportDropdownOpen(false); onExportSvg(); }}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  textAlign: 'left',
                  border: 'none',
                  background: 'transparent',
                  fontSize: 12.5,
                  color: '#0f172a',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  borderTop: '1px solid #f1f5f9'
                }}
              >
                🎨 Download Vector SVG
              </button>
            )}
          </div>
        )}
      </div>

      {/* Version Selector Pill */}
      <div style={{ position: 'relative' }}>
        <button
          style={{
            background: '#1e293b',
            color: '#ffffff',
            border: 'none',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: 12.5,
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            cursor: 'pointer'
          }}
          onClick={() => setDropdownOpen(!dropdownOpen)}
        >
          <span>Version: {activeVersionName || (activeVersionNumber ? `V${activeVersionNumber}` : 'V1')}</span>
          <ChevronDown size={14} />
        </button>

        {dropdownOpen && (
          <div
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 4,
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
              minWidth: 220,
              zIndex: 100,
              padding: 4
            }}
          >
            <div style={{ padding: '6px 10px', fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
              Saved Versions ({versions.length}/5)
            </div>
            {versions.map((v) => (
              <div
                key={v.id}
                style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: v.is_active ? '#f5f3ff' : 'transparent',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  setDropdownOpen(false);
                  if (!v.is_active) onRestore(v.id);
                }}
              >
                <div>
                  <div style={{ fontSize: 12.5, fontWeight: v.is_active ? 700 : 500, color: v.is_active ? '#6366f1' : '#0f172a' }}>
                    {v.version_name} {v.is_active && '✓'}
                  </div>
                  {v.change_summary && (
                    <div style={{ fontSize: 10.5, color: '#64748b' }}>{v.change_summary.slice(0, 32)}...</div>
                  )}
                </div>
              </div>
            ))}
            <div style={{ borderTop: '1px solid #f1f5f9', marginTop: 4, paddingTop: 4 }}>
              <button
                onClick={() => { setDropdownOpen(false); setHistoryModalOpen(true); }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  border: 'none',
                  background: 'transparent',
                  color: '#6366f1',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                Manage All Versions...
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons matching screenshot */}
      <button className="btn-secondary" onClick={handleOpenRename} title="Rename current active version">
        <Edit3 size={14} /> Rename
      </button>

      <button className="btn-secondary" onClick={handleDeleteActive} title="Delete active version">
        <Trash2 size={14} color="#ef4444" /> Delete
      </button>

      <button className="btn-secondary" onClick={() => setHistoryModalOpen(true)} title="Compare version history">
        <GitCompare size={14} /> Compare
      </button>

      {/* Rename Version Modal */}
      {renameModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <h3>Rename Version</h3>
              <button onClick={() => setRenameModalOpen(false)} className="modal-close-btn">✕</button>
            </div>
            <form onSubmit={handleSaveRename}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Version Display Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    required
                  />
                  <p style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                    E.g. "Subscription-Based Model", "Enterprise Expansion", or "Q4 Spikes"
                  </p>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" onClick={() => setRenameModalOpen(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Name
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manage / Compare Versions Modal */}
      {historyModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <h3>Version History ({moduleTitle})</h3>
              <button onClick={() => setHistoryModalOpen(false)} className="modal-close-btn">✕</button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: 12.5, color: '#64748b' }}>
                Each section maintains up to 5 persistent versions. Restoring an earlier version creates an updated active copy.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                {versions.map((v) => (
                  <div
                    key={v.id}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                      padding: '12px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: v.is_active ? '#f5f3ff' : '#ffffff',
                      borderColor: v.is_active ? '#c7d2fe' : '#e2e8f0'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontWeight: 700, fontSize: 13.5, color: '#0f172a' }}>{v.version_name}</span>
                        {v.is_active && (
                          <span style={{ fontSize: 10, fontWeight: 700, background: '#6366f1', color: '#fff', padding: '1px 6px', borderRadius: 4 }}>
                            Active
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 3 }}>
                        {v.change_summary || 'Initial creation'} • {new Date(v.created_at).toLocaleDateString()}
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {!v.is_active && (
                        <button
                          onClick={async () => {
                            await onRestore(v.id);
                            setHistoryModalOpen(false);
                          }}
                          className="btn-secondary"
                          style={{ padding: '4px 10px', fontSize: 12 }}
                        >
                          <RotateCcw size={12} /> Restore
                        </button>
                      )}
                      {versions.length > 1 && (
                        <button
                          onClick={async () => {
                            if (window.confirm(`Delete ${v.version_name}?`)) {
                              await onDelete(v.id);
                            }
                          }}
                          style={{ border: 'none', background: 'transparent', color: '#ef4444', cursor: 'pointer', padding: 4 }}
                          title="Delete version"
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setHistoryModalOpen(false)} className="btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
