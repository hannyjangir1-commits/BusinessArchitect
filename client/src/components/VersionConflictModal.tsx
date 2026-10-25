import React, { useState } from 'react';
import { VersionItem } from '../types';
import { AlertTriangle, RefreshCw, X } from 'lucide-react';
import { Dialog } from './common/Dialog';

interface Props {
  moduleTitle: string;
  existingVersions: VersionItem[];
  pendingInstruction?: string;
  pendingData?: any;
  onResolveReplace: (replaceVersionId: string) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}

export const VersionConflictModal: React.FC<Props> = ({
  moduleTitle,
  existingVersions,
  pendingInstruction,
  onResolveReplace,
  onCancel,
  isLoading
}) => {
  const [selectedVersionId, setSelectedVersionId] = useState<string>(
    existingVersions.length > 0 ? existingVersions[0].id : ''
  );
  const [confirmedDeletion, setConfirmedDeletion] = useState<boolean>(false);

  const selectedVersion = existingVersions.find(v => v.id === selectedVersionId);

  const handleConfirm = async () => {
    if (!selectedVersionId || !confirmedDeletion) return;
    await onResolveReplace(selectedVersionId);
  };

  return (
    <Dialog
      isOpen={true}
      onClose={onCancel}
      dismissible={!isLoading}
      showCloseButton={false}
      ariaLabelledBy="conflict-title"
      maxWidth={580}
    >
      <div className="modal-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--bg-subtle)', color: 'var(--danger-text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <AlertTriangle size={18} />
          </div>
          <div>
            <h3 id="conflict-title" style={{ color: 'var(--text-main)', margin: 0, fontSize: 16, fontWeight: 700 }}>Maximum 5 Versions Reached</h3>
            <p style={{ fontSize: 11.5, color: 'var(--text-muted)', margin: '2px 0 0 0' }}>Section: {moduleTitle}</p>
          </div>
        </div>
        <button
          onClick={onCancel}
          className="modal-close-btn"
          aria-label="Close version conflict dialog"
          disabled={isLoading}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: isLoading ? 'not-allowed' : 'pointer', padding: 4 }}
        >
          <X size={16} />
        </button>
      </div>

      <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ padding: 12, background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 13, color: 'var(--primary-text)' }}>
          As per system policy, each module stores a maximum of 5 versions. To save your latest modification, select an existing version to replace. <b>No saved version will be silently deleted or overwritten without your explicit choice.</b>
        </div>

        {pendingInstruction && (
          <div style={{ fontSize: 12, color: 'var(--text-main)', background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', padding: 10, borderRadius: 6 }}>
            <b>Pending Modification:</b> <i>"{pendingInstruction}"</i>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div id="choose-version-label" style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-main)' }}>
            Choose a version to replace:
          </div>
          <div role="radiogroup" aria-labelledby="choose-version-label" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {existingVersions.map((v) => (
              <label
                key={v.id}
                role="radio"
                aria-checked={selectedVersionId === v.id}
                style={{
                  border: `2px solid ${selectedVersionId === v.id ? 'var(--primary)' : 'var(--border-color)'}`,
                  borderRadius: 8,
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: selectedVersionId === v.id ? 'rgb(69 60 55 / 0.12)' : 'var(--bg-card)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-main)' }}>
                    {v.version_name} {v.is_active && '(Currently Active)'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {v.change_summary || 'Initial creation'} • {new Date(v.created_at).toLocaleDateString()}
                  </div>
                </div>
                <input
                  type="radio"
                  name="version-to-replace"
                  value={v.id}
                  checked={selectedVersionId === v.id}
                  onChange={() => {
                    setSelectedVersionId(v.id);
                    setConfirmedDeletion(false);
                  }}
                  style={{ width: 16, height: 16, accentColor: 'var(--primary)' }}
                />
              </label>
            ))}
          </div>
        </div>

        <label htmlFor="confirm-permanent-deletion-checkbox" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--danger-text)', fontWeight: 600, cursor: 'pointer', marginTop: 8, padding: '10px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 6 }}>
          <input
            type="checkbox"
            id="confirm-permanent-deletion-checkbox"
            checked={confirmedDeletion}
            onChange={(e) => setConfirmedDeletion(e.target.checked)}
            style={{ width: 16, height: 16, accentColor: 'var(--danger-text)', cursor: 'pointer' }}
          />
          <span>I confirm that <u>{selectedVersion?.version_name || 'the selected version'}</u> will be permanently removed to free up a slot for the new version.</span>
        </label>
      </div>

      <div className="modal-footer" style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 18 }}>
        <button type="button" onClick={onCancel} className="btn-secondary" disabled={isLoading}>
          Cancel
        </button>
        <button type="button" onClick={handleConfirm} className="btn-primary" disabled={isLoading || !selectedVersionId || !confirmedDeletion}>
          <RefreshCw size={14} /> Confirm & Replace Selected Version
        </button>
      </div>
    </Dialog>
  );
};
