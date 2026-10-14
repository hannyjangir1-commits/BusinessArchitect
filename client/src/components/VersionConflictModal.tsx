import React, { useState } from 'react';
import { VersionItem } from '../types';
import { AlertTriangle, RefreshCw } from 'lucide-react';

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
    <div className="modal-overlay">
      <div className="modal-card" style={{ maxWidth: 580 }}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#fee2e2', color: '#dc2626', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <AlertTriangle size={18} />
            </div>
            <div>
              <h3 style={{ color: '#0f172a' }}>Maximum 5 Versions Reached</h3>
              <p style={{ fontSize: 11.5, color: '#64748b' }}>Section: {moduleTitle}</p>
            </div>
          </div>
          <button onClick={onCancel} className="modal-close-btn" disabled={isLoading}>✕</button>
        </div>

        <div className="modal-body">
          <div style={{ padding: 12, background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, fontSize: 13, color: '#92400e' }}>
            As per system policy, each module stores a maximum of 5 versions. To save your latest modification, select an existing version to replace. <b>No saved version will be silently deleted or overwritten without your explicit choice.</b>
          </div>

          {pendingInstruction && (
            <div style={{ fontSize: 12, color: '#475569', background: '#f8fafc', padding: 10, borderRadius: 6 }}>
              <b>Pending AI Modification:</b> <i>"{pendingInstruction}"</i>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>
              Choose a version to replace:
            </div>
            {existingVersions.map((v) => (
              <div
                key={v.id}
                onClick={() => {
                  setSelectedVersionId(v.id);
                  setConfirmedDeletion(false);
                }}
                style={{
                  border: `2px solid ${selectedVersionId === v.id ? '#6366f1' : '#e2e8f0'}`,
                  borderRadius: 8,
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: selectedVersionId === v.id ? '#f5f3ff' : '#ffffff',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: '#0f172a' }}>
                    {v.version_name} {v.is_active && '(Currently Active)'}
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>
                    {v.change_summary || 'Initial creation'} • {new Date(v.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div style={{ width: 20, height: 20, borderRadius: '50%', border: `2px solid ${selectedVersionId === v.id ? '#6366f1' : '#cbd5e1'}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {selectedVersionId === v.id && <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#6366f1' }} />}
                </div>
              </div>
            ))}
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: '#b91c1c', fontWeight: 600, cursor: 'pointer', marginTop: 14, padding: '10px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6 }}>
            <input
              type="checkbox"
              id="confirm-permanent-deletion-checkbox"
              checked={confirmedDeletion}
              onChange={(e) => setConfirmedDeletion(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: '#dc2626', cursor: 'pointer' }}
            />
            <span>I confirm that <u>{selectedVersion?.version_name || 'the selected version'}</u> will be permanently removed to free up a slot for the new version.</span>
          </label>
        </div>

        <div className="modal-footer">
          <button onClick={onCancel} className="btn-secondary" disabled={isLoading}>
            Cancel
          </button>
          <button onClick={handleConfirm} className="btn-primary" disabled={isLoading || !selectedVersionId || !confirmedDeletion}>
            <RefreshCw size={14} /> Confirm & Replace Selected Version
          </button>
        </div>
      </div>
    </div>
  );
};
