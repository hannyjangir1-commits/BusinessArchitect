import React, { useState } from 'react';
import { MessageCircle, Minus, Square, X, Send, Loader2 } from 'lucide-react';

interface Props {
  moduleTitle: string;
  moduleType: string;
  onModify: (instruction: string) => Promise<void>;
  onClose?: () => void;
  isLoading: boolean;
}

export const ContextualAssistant: React.FC<Props> = ({ moduleTitle, onModify, onClose, isLoading }) => {
  const [input, setInput] = useState('');
  const [isClosed, setIsClosed] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  // Suggestions cannot be safely inferred from a module name alone. A software
  // prompt such as "add OAuth" is actively misleading for projects like a local
  // bakery, so the assistant accepts only the user's project-specific request.
  const chips: { label: string; text: string }[] = [];

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;
    const text = input;
    try { await onModify(text); setInput(''); } catch { /* Workspace displays the error and keeps this instruction. */ }
  };

  if (isClosed) {
    return (
      <div style={{ padding: '8px 0' }}>
        <button
          onClick={() => setIsClosed(false)}
          className="btn-secondary"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12.5,
            padding: '8px 14px',
            background: 'var(--bg-card)',
            boxShadow: '0 2px 6px rgb(69 60 55 / 0.06)'
          }}
          title="Reopen Contextual Blueprint Assistant"
        >
          <MessageCircle size={15} />
          <span>Reopen Blueprint Assistant ({moduleTitle})</span>
        </button>
      </div>
    );
  }

  return (
    <div className="ai-assistant-panel">
      {/* Header */}
      <div className="ai-assistant-header">
        <div className="ai-assistant-title">
          <MessageCircle size={16} />
          <span>Blueprint Assistant</span>
          <span style={{ fontSize: 11, color: 'var(--primary-text)', fontWeight: 600 }}>({moduleTitle})</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)' }}>
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 2 }}
            title={isMinimized ? 'Expand assistant' : 'Minimize assistant'}
            aria-label="Minimize assistant"
          >
            {isMinimized ? <Square size={13} /> : <Minus size={14} />}
          </button>
          <button
            onClick={() => {
              setIsClosed(true);
              onClose?.();
            }}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 2 }}
            title="Close assistant panel"
            aria-label="Close assistant panel"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Content Area (collapsed when minimized) */}
      {!isMinimized && (
        <>
          <div className="ai-assistant-content">
            <div className="ai-prompt-box-banner">
              <h4>Modify your {moduleTitle.toLowerCase()}</h4>
              <p>Instruct Blueprint Assistant to adapt this module's parameters, structure, or strategic direction.</p>
            </div>

            {/* Module-Specific Suggestion Chips */}
            {chips.length > 0 && (
              <div className="ai-chips-list">
                {chips.map((c, idx) => (
                  <button
                    key={idx}
                    className="ai-chip-btn"
                    onClick={() => setInput(c.text)}
                    disabled={isLoading}
                  >
                    <span>{c.label}</span>
                  </button>
                ))}
              </div>
            )}

            {isLoading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 12, background: 'rgb(69 60 55 / 0.1)', borderRadius: 8, color: 'var(--primary)', fontSize: 12 }}>
                <Loader2 size={16} className="animate-spin" />
                <span>Updating your blueprint recommendations...</span>
              </div>
            )}
          </div>

          {/* Clean Input Area without inert icons */}
          <form onSubmit={handleSubmit} className="ai-assistant-input-area">
            <input
              type="text"
              className="ai-input-field"
              placeholder={`Instruct Blueprint Assistant to modify ${moduleTitle}...`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              aria-label="Instruction text"
            />
            <button
              type="submit"
              className="ai-send-btn"
              disabled={isLoading || !input.trim()}
              title="Submit modification instruction"
              aria-label="Submit instruction"
            >
              {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={15} />}
            </button>
          </form>
        </>
      )}
    </div>
  );
};
