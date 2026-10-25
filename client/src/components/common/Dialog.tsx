import React, { useEffect, useRef, useId, useCallback } from 'react';
import { X } from 'lucide-react';

export interface DialogStackEntry {
  id: string;
  root: HTMLElement;
  dismiss: () => void;
  dismissible: boolean;
  opener: HTMLElement | null;
}

// Module-scoped dialog stack ensuring only the topmost modal responds to Escape and Tab
const stack: DialogStackEntry[] = [];
let originalBodyOverflow: string | null = null;
let listenersAttached = false;

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const selector = [
    'button:not([disabled])',
    'a[href]',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ].join(', ');
  return Array.from(container.querySelectorAll<HTMLElement>(selector))
    .filter(el => el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0);
}

function handleKeyDown(event: KeyboardEvent) {
  if (stack.length === 0) return;
  const topmost = stack[stack.length - 1];

  if (event.key === 'Escape') {
    if (topmost.dismissible) {
      event.preventDefault();
      event.stopPropagation();
      topmost.dismiss();
    }
    return;
  }

  if (event.key === 'Tab') {
    const focusable = getFocusableElements(topmost.root);
    if (focusable.length === 0) {
      event.preventDefault();
      topmost.root.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey) {
      if (active === first || !topmost.root.contains(active)) {
        event.preventDefault();
        last.focus();
      }
    } else {
      if (active === last || !topmost.root.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    }
  }
}

function attachGlobalListeners() {
  if (!listenersAttached && typeof window !== 'undefined') {
    window.addEventListener('keydown', handleKeyDown, true);
    listenersAttached = true;
  }
}

function detachGlobalListeners() {
  if (listenersAttached && stack.length === 0 && typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleKeyDown, true);
    listenersAttached = false;
  }
}

export function registerDialog(entry: DialogStackEntry) {
  if (stack.length === 0) {
    originalBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  stack.push(entry);
  attachGlobalListeners();
}

export function unregisterDialog(id: string) {
  const index = stack.findIndex(e => e.id === id);
  if (index !== -1) {
    const [removed] = stack.splice(index, 1);
    if (removed && removed.opener && removed.opener.isConnected) {
      try {
        removed.opener.focus();
      } catch {
        // Fallback safely
      }
    } else if (stack.length > 0) {
      const parentDialog = stack[stack.length - 1];
      const parentFocusable = getFocusableElements(parentDialog.root);
      if (parentFocusable.length > 0) {
        parentFocusable[0].focus();
      } else {
        parentDialog.root.focus();
      }
    }
  }

  if (stack.length === 0) {
    if (originalBodyOverflow !== null) {
      document.body.style.overflow = originalBodyOverflow;
      originalBodyOverflow = null;
    } else {
      document.body.style.overflow = '';
    }
    detachGlobalListeners();
  }
}

export function useDialog({
  isOpen,
  onDismiss,
  dismissible = true,
  initialFocusRef
}: {
  isOpen: boolean;
  onDismiss: () => void;
  dismissible?: boolean;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const id = useId();
  const dismissCallback = useCallback(() => {
    onDismiss();
  }, [onDismiss]);

  useEffect(() => {
    if (!isOpen) return;

    const opener = (document.activeElement as HTMLElement) || null;
    const currentRoot = dialogRef.current;
    if (!currentRoot) return;

    registerDialog({
      id,
      root: currentRoot,
      dismiss: dismissCallback,
      dismissible,
      opener
    });

    // Initial focus placement
    const timeout = setTimeout(() => {
      if (initialFocusRef?.current && initialFocusRef.current.isConnected) {
        initialFocusRef.current.focus();
      } else {
        const focusable = getFocusableElements(currentRoot);
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          currentRoot.focus();
        }
      }
    }, 10);

    return () => {
      clearTimeout(timeout);
      unregisterDialog(id);
    };
  }, [isOpen, id, dismissCallback, dismissible, initialFocusRef]);

  return { dialogRef };
}

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
  dismissible?: boolean;
  maxWidth?: number | string;
  className?: string;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  children: React.ReactNode;
  showCloseButton?: boolean;
}

export const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  ariaLabel,
  ariaLabelledBy,
  ariaDescribedBy,
  dismissible = true,
  maxWidth = 520,
  className = '',
  initialFocusRef,
  children,
  showCloseButton = true
}) => {
  const titleId = useId();
  const descId = useId();
  const { dialogRef } = useDialog({
    isOpen,
    onDismiss: onClose,
    dismissible,
    initialFocusRef
  });

  if (!isOpen) return null;

  const effectiveTitleId = ariaLabelledBy || (title ? titleId : undefined);
  const effectiveDescId = ariaDescribedBy || (description ? descId : undefined);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgb(69 60 55 / 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: 16
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && dismissible) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        data-managed-dialog="true"
        aria-label={ariaLabel}
        aria-labelledby={effectiveTitleId}
        aria-describedby={effectiveDescId}
        tabIndex={-1}
        className={`modal-card ${className}`}
        style={{
          background: 'var(--bg-card)',
          color: 'var(--text-main)',
          borderRadius: 12,
          padding: 24,
          maxWidth,
          width: '100%',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border-color)',
          position: 'relative',
          outline: 'none'
        }}
      >
        {(title || showCloseButton) && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: description ? 4 : 16 }}>
            {title && (
              <h2 id={effectiveTitleId} style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                {title}
              </h2>
            )}
            {showCloseButton && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close dialog"
                disabled={!dismissible}
                className="modal-close-btn"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: dismissible ? 'pointer' : 'not-allowed',
                  padding: 4,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 6
                }}
              >
                <X size={18} />
              </button>
            )}
          </div>
        )}

        {description && (
          <p id={effectiveDescId} style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 16px 0' }}>
            {description}
          </p>
        )}

        {children}
      </div>
    </div>
  );
};
