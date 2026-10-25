import React from 'react';
import { LogOut, AlertTriangle } from 'lucide-react';
import { Dialog } from './common/Dialog';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  isLoading?: boolean;
}

export const LogoutConfirmModal: React.FC<Props> = ({
  isOpen,
  onClose,
  onConfirm,
  isLoading = false
}) => {
  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      dismissible={!isLoading}
      showCloseButton={false}
      ariaLabelledBy="logout-title"
      maxWidth={440}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: 'var(--bg-subtle)',
            color: 'var(--danger-text)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}
        >
          <AlertTriangle size={22} />
        </div>
        <div>
          <h3 id="logout-title" style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
            Are you sure you want to log out?
          </h3>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
            Your current authenticated session will be securely terminated.
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 24 }}>
        <button
          type="button"
          className="btn-secondary"
          onClick={onClose}
          disabled={isLoading}
          style={{ padding: '8px 16px', fontSize: 13 }}
        >
          No, Stay Signed In
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={isLoading}
          style={{
            padding: '8px 18px',
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--text-main)',
            background: 'var(--danger-text)',
            border: 'none',
            borderRadius: 6,
            cursor: isLoading ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6
          }}
        >
          <LogOut size={14} />
          {isLoading ? 'Signing out...' : 'Yes, Log Out'}
        </button>
      </div>
    </Dialog>
  );
};
