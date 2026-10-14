import React, { useState } from 'react';
import { Sparkles, Minus, Square, X, Send, Loader2 } from 'lucide-react';

interface Props {
  moduleTitle: string;
  moduleType: string;
  onModify: (instruction: string) => Promise<void>;
  onClose?: () => void;
  isLoading: boolean;
}

export const ContextualAssistant: React.FC<Props> = ({ moduleTitle, moduleType, onModify, onClose, isLoading }) => {
  const [input, setInput] = useState('');
  const [isClosed, setIsClosed] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  // Module-specific suggested prompts tailored for each supported module
  const modulePromptMap: Record<string, { label: string; text: string }[]> = {
    overview: [
      { label: '📝 Refine business description', text: 'Refine and sharpen the executive business description for clarity and investor appeal' },
      { label: '🎯 Clarify target customers', text: 'Clarify target customer demographics, primary user personas, and acute pain points' },
      { label: '📈 Update strategic goals', text: 'Update the strategic goals with quarterly measurable metrics and expansion targets' },
      { label: '🏢 Industry positioning', text: 'Sharpen the competitive industry positioning and primary market differentiation' }
    ],
    bmc: [
      { label: '💡 Refine value proposition', text: 'Refine and strengthen the core value proposition with quantitative customer benefits' },
      { label: '📢 Add customer channels', text: 'Add direct enterprise sales and organic partner referral acquisition channels' },
      { label: '💰 Update revenue streams', text: 'Introduce tiered subscription pricing, usage billing, and enterprise service packages' },
      { label: '🤝 Improve key partnerships', text: 'Identify strategic ecosystem alliances, technology integrations, and channel distributors' }
    ],
    tech_stack: [
      { label: '🛡️ Add authentication layer', text: 'Add an enterprise OAuth2, RBAC, and multi-factor authentication security architecture' },
      { label: '🗄️ Evaluate database choice', text: 'Evaluate PostgreSQL and Redis caching suitability for scalable read/write operations' },
      { label: '⚡ Improve scalability', text: 'Optimize architecture for high concurrency with asynchronous queues and connection pooling' },
      { label: '📊 Add observability', text: 'Add distributed telemetry tracing, Prometheus metrics monitoring, and structured audit logging' }
    ],
    execution_roadmap: [
      { label: '+ Add a strategic phase', text: 'Add a new strategic beta deployment phase with dedicated milestone deliverables' },
      { label: '🎯 Adjust milestone deadlines', text: 'Re-align milestone target dates and allocate critical path buffer time' },
      { label: '🔗 Extend development phase', text: 'Extend development phase by 2 weeks and reconcile dependent downstream tasks' },
      { label: '🧪 Add testing tasks', text: 'Add automated end-to-end regression tests, penetration testing, and load validation' }
    ],
    detailed_roadmap: [
      { label: '📋 Break task into subtasks', text: 'Decompose core architecture tasks into granular sprint-level engineering deliverables' },
      { label: '✅ Add acceptance criteria', text: 'Add clear measurable definition-of-done acceptance criteria to major deliverables' },
      { label: '🔗 Adjust dependency chain', text: 'Adjust task dependency links to enable parallel sprint execution without blocking' },
      { label: '⏱️ Update task effort', text: 'Recalculate effort estimates and staffing requirements across all roadmap tasks' }
    ]
  };

  const chips = modulePromptMap[moduleType] || modulePromptMap.execution_roadmap;

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
            background: '#ffffff',
            boxShadow: '0 2px 6px rgba(0,0,0,0.06)'
          }}
          title="Reopen Contextual AI Assistant"
        >
          <Sparkles size={15} color="#eab308" />
          <span>Reopen AI Assistant ({moduleTitle})</span>
        </button>
      </div>
    );
  }

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
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2 }}
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
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2 }}
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
              <p>Instruct Gemini AI to adapt this module's parameters, structure, or strategic direction.</p>
            </div>

            {/* Module-Specific Suggestion Chips */}
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

          {/* Clean Input Area without inert icons */}
          <form onSubmit={handleSubmit} className="ai-assistant-input-area">
            <input
              type="text"
              className="ai-input-field"
              placeholder={`Instruct AI to modify ${moduleTitle}...`}
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
