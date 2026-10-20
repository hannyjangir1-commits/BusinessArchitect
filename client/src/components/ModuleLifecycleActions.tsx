import React, { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { VersionItem } from '../types';

interface Props {
  moduleTitle: string;
  onCreateNew?: () => Promise<void>;
  onDeleteModule?: () => Promise<void>;
  onDeleteVersion?: (versionId: string) => Promise<void>;
  versions?: VersionItem[];
  createLabel?: string;
  isBusy?: boolean;
  isCreateDisabled?: boolean;
}

export const ModuleLifecycleActions: React.FC<Props> = ({
  moduleTitle,
  onCreateNew,
  onDeleteModule,
  onDeleteVersion,
  versions = [],
  createLabel = 'Generate New',
  isBusy = false,
  isCreateDisabled = false
}) => {
  const [actionError, setActionError] = useState<string | null>(null);
  const activeVersion = versions.find(version => version.is_active) || versions[versions.length - 1];
  const deletesVersion = versions.length > 1 && !!activeVersion && !!onDeleteVersion;

  const confirmAndDelete = async () => {
    setActionError(null);
    const relatedData = moduleTitle === 'Roadmap & Execution Plan' ? ' and all roadmap tasks' : '';
    const confirmationMessage = deletesVersion
      ? `Delete the current version${activeVersion?.version_name ? ` (${activeVersion.version_name})` : ''} of ${moduleTitle}? Other saved versions will remain.`
      : `Delete ${moduleTitle}${relatedData}, including its saved version? This cannot be undone. You can generate it again later.`;
    if (!window.confirm(confirmationMessage)) return;

    try {
      if (deletesVersion && activeVersion && onDeleteVersion) {
        await onDeleteVersion(activeVersion.id);
      } else {
        await onDeleteModule?.();
      }
    } catch (error: any) {
      setActionError(error?.message || `Could not delete ${moduleTitle}. Please try again.`);
    }
  };

  const canDelete = versions.length > 1 ? deletesVersion : !!onDeleteModule;
  const deleteAccessibleName = deletesVersion
    ? `Delete current version of ${moduleTitle}`
    : `Delete ${moduleTitle}`;

  return (
    <div className="module-lifecycle-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {onCreateNew && (
        <button
          type="button"
          className="btn-secondary"
          onClick={() => { void onCreateNew(); }}
          disabled={isBusy || isCreateDisabled}
          aria-label={createLabel}
          title={createLabel}
        >
          <Plus size={14} /> {createLabel}
        </button>
      )}
      {canDelete && (
        <button
          type="button"
          className="btn-secondary module-delete-action"
          onClick={() => { void confirmAndDelete(); }}
          disabled={isBusy}
          aria-label={deleteAccessibleName}
          title={deletesVersion ? `Delete current ${moduleTitle} version` : `Delete ${moduleTitle} and its saved data`}
        >
          <Trash2 size={14} /> Delete
        </button>
      )}
      {actionError && <span role="alert" style={{ color: 'var(--danger-text)', fontSize: 12, maxWidth: 240 }}>{actionError}</span>}
    </div>
  );
};
