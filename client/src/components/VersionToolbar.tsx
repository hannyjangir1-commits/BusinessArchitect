import React, { useState } from 'react';
import { VersionItem } from '../types';
import { ChevronDown, Download, Edit3, RotateCcw } from 'lucide-react';
import { ModuleLifecycleActions } from './ModuleLifecycleActions';

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
  onCreateNew?: () => Promise<void>;
  onDeleteModule?: () => Promise<void>;
  createLabel?: string;
  isBusy?: boolean;
  isCreateDisabled?: boolean;
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
  onExportSvg,
  onCreateNew,
  onDeleteModule,
  createLabel,
  isBusy = false,
  isCreateDisabled = false
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

  return (
    <div className="module-toolbar" style={{ position: 'relative' }}>
      <ModuleLifecycleActions
        moduleTitle={moduleTitle}
        onCreateNew={onCreateNew}
        onDeleteModule={onDeleteModule}
        onDeleteVersion={onDelete}
        versions={versions}
        createLabel={createLabel}
        isBusy={isBusy}
        isCreateDisabled={isCreateDisabled}
      />

      {/* Export This Module Dropdown */}
      <div style={{ position: 'relative' }}>
        <button
          className="btn-secondary"
          onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
        >
          <Download size={14} color="#6d855f" />
          <span>Export This Module</span>
          <ChevronDown size={14} />
        </button>

        {exportDropdownOpen && (
          <div
            className="module-toolbar-menu module-export-menu"
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 4,
              width: 180,
              zIndex: 100,
              overflow: 'hidden'
            }}
          >
            <button
              className="module-toolbar-menu-item"
              onClick={() => { setExportDropdownOpen(false); onExportPdf(); }}
              style={{
                width: '100%',
                padding: '9px 12px',
                textAlign: 'left',
                border: 'none',
                background: 'transparent',
                fontSize: 12.5,
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
                className="module-toolbar-menu-item"
                onClick={() => { setExportDropdownOpen(false); onExportSvg(); }}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  textAlign: 'left',
                  border: 'none',
                  background: 'transparent',
                  fontSize: 12.5,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
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
          className="version-selector-button"
          onClick={() => setDropdownOpen(!dropdownOpen)}
        >
          <span>Version: {activeVersionName || (activeVersionNumber ? `V${activeVersionNumber}` : 'V1')}</span>
          <ChevronDown size={14} />
        </button>

        {dropdownOpen && (
          <div
            className="module-toolbar-menu module-version-menu"
            style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 4,
              minWidth: 220,
              zIndex: 100,
              padding: 4
            }}
          >
            <div className="version-menu-heading">
              Saved Versions ({versions.length}/5)
            </div>
            {versions.map((v) => (
              <div
                key={v.id}
                className={`module-version-menu-item ${v.is_active ? 'active' : ''}`}
                onClick={() => {
                  setDropdownOpen(false);
                  if (!v.is_active) onRestore(v.id);
                }}
              >
                <div>
                  <div className="module-version-menu-name" style={{ fontWeight: v.is_active ? 700 : 500 }}>
                    {v.version_name} {v.is_active && '✓'}
                  </div>
                  {v.change_summary && (
                    <div className="module-version-menu-summary">{v.change_summary.slice(0, 32)}...</div>
                  )}
                </div>
              </div>
            ))}
            <div className="module-version-menu-footer">
              <button
                className="module-version-menu-manage"
                onClick={() => { setDropdownOpen(false); setHistoryModalOpen(true); }}
              >
                Manage All Versions...
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Compact actions; version history remains available from the version menu. */}
      <button className="btn-secondary" onClick={handleOpenRename} title="Rename current active version" aria-label="Rename current version">
        <Edit3 size={14} /> Rename
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
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
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

      {/* Version History Modal */}
      {historyModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <h3>Version History ({moduleTitle})</h3>
              <button onClick={() => setHistoryModalOpen(false)} className="modal-close-btn">✕</button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
                Each section maintains up to 5 saved versions. Restore an older snapshot here. Use the module header's Delete button to delete the active version.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                {versions.map((v) => (
                  <div
                    key={v.id}
                    className={`version-history-entry ${v.is_active ? 'active' : ''}`}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className="version-history-entry-name">{v.version_name}</span>
                        {v.is_active && (
                          <span style={{ fontSize: 10, fontWeight: 700, background: 'var(--primary)', color: 'var(--text-main)', padding: '1px 6px', borderRadius: 4 }}>
                            Active
                          </span>
                        )}
                      </div>
                      <div className="version-history-entry-summary">
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
