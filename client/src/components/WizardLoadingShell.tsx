import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { Dialog } from './common/Dialog';

interface LoadingProps {
  onCancel: () => void;
}

export const WizardLoadingShell: React.FC<LoadingProps> = ({ onCancel }) => {
  return (
    <Dialog
      isOpen={true}
      onClose={onCancel}
      title="Opening project setup…"
      maxWidth={680}
    >
      <div
        role="status"
        aria-live="polite"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 24px',
          gap: 16,
          textAlign: 'center'
        }}
      >
        <Loader2 size={32} className="animate-spin" color="var(--primary)" />
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-main)' }}>
            Loading project setup wizard…
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 4 }}>
            Preparing the three-step venture configuration wizard.
          </div>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="btn-secondary"
          style={{ marginTop: 8, padding: '8px 18px', fontSize: 13 }}
        >
          Cancel
        </button>
      </div>
    </Dialog>
  );
};

interface ErrorBoundaryProps {
  onCancel: () => void;
  onRetry?: () => void;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class WizardErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Isolated client chunk loading catch
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onRetry?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <Dialog
          isOpen={true}
          onClose={this.props.onCancel}
          title="Project Setup Unavailable"
          maxWidth={500}
        >
          <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', padding: '12px 0' }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: 'var(--bg-subtle)',
                color: 'var(--danger-text)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}
            >
              <AlertCircle size={22} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-main)' }}>
                Could not load the project wizard
              </div>
              <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                A network disruption prevented loading the wizard component. Check your connection and try again.
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 18 }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={this.props.onCancel}
              style={{ padding: '8px 16px', fontSize: 13 }}
            >
              Close
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={this.handleRetry}
              style={{ padding: '8px 18px', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={14} /> Retry
            </button>
          </div>
        </Dialog>
      );
    }

    return this.props.children;
  }
}
