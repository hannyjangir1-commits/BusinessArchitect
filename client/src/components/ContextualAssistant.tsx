import React, { useState } from 'react';
import { Sparkles, Minus, Square, X, Paperclip, Send, Loader2 } from 'lucide-react';

interface Props {
  moduleTitle: string;
  moduleType: string;
  onModify: (instruction: string) => Promise<void>;
  isLoading: boolean;
}

export const ContextualAssistant: React.FC<Props> = ({ moduleTitle, onModify, isLoading }) => {
  const [input, setInput] = useState('');

  const chips = [
    { label: '+ Add a new phase', text: 'Add a new strategic phase to the plan with appropriate timeline and milestones' },
    { label: '🔗 Extend development phase', text: 'Extend the development phase duration by 2 weeks and adjust dependent tasks' },
    { label: '📋 Add more testing tasks', text: 'Add end-to-end regression testing, penetration testing, and load spike tasks' },
    { label: '⏱️ Change timeline to 6 months', text: 'Restructure the execution phases and timeline across a 6-month horizon' }
  ];

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;
    const text = input;
    setInput('');
    await onModify(text);
  };

  const handleChipClick = async (chipText: string) => {
    if (isLoading) return;
    await onModify(chipText);
  };

  return (
    <div className="ai-assistant-panel">
      {/* Header */}
      <div className="ai-assistant-header">
        <div className="ai-assistant-title">
          <Sparkles size={16} color="#eab308" />
          <span>AI Assistant</span>
          <span style={{ fontSize: 11, color: '#6366f1', fontWeight: 600 }}>({moduleTitle})</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#94a3b8' }}>
          <Minus size={14} style={{ cursor: 'pointer' }} />
          <Square size={12} style={{ cursor: 'pointer' }} />
          <X size={14} style={{ cursor: 'pointer' }} />
        </div>
      </div>

      {/* Content Area */}
      <div className="ai-assistant-content">
        <div className="ai-prompt-box-banner">
          <h4>Modify your {moduleTitle.toLowerCase()}</h4>
          <p>Tell me what changes you want to make to the timeline, tasks, or strategic parameters.</p>
        </div>

        {/* Suggestion Chips */}
        <div className="ai-chips-list">
          {chips.map((c, idx) => (
            <button
              key={idx}
              className="ai-chip-btn"
              onClick={() => handleChipClick(c.text)}
              disabled={isLoading}
            >
              <span>{c.label}</span>
            </button>
          ))}
        </div>

        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 12, background: '#f5f3ff', borderRadius: 8, color: '#6366f1', fontSize: 12 }}>
            <Loader2 size={16} className="animate-spin" />
            <span>Gemini AI is analyzing and updating your blueprint...</span>
          </div>
        )}
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="ai-assistant-input-area">
        <Paperclip size={16} color="#94a3b8" style={{ cursor: 'pointer' }} />
        <input
          type="text"
          className="ai-input-field"
          placeholder="Describe your changes..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading}
        />
        <button
          type="submit"
          className="ai-send-btn"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? <Loader2 size={16} /> : <Send size={15} />}
        </button>
      </form>
    </div>
  );
};
