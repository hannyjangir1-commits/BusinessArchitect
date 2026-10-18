import React, { useState, useEffect, useRef } from 'react';
import { Project, CopilotMessage } from '../types';
import { Bot, Send, User, Sparkles, Loader2 } from 'lucide-react';

interface Props {
  project: Project;
  messages: CopilotMessage[];
  onSendMessage: (message: string) => Promise<void>;
  isLoading: boolean;
}

// Clean, lightweight Markdown component for Planning Copilot
const MarkdownContent: React.FC<{ content: string; isUser: boolean }> = ({ content, isUser }) => {
  if (isUser) {
    return <span>{content}</span>;
  }

  // Check if string contains raw JSON wrapper and format it gracefully
  let cleanContent = content.trim();
  if (cleanContent.startsWith('{') && cleanContent.endsWith('}')) {
    try {
      const parsed = JSON.parse(cleanContent);
      if (parsed.message || parsed.response || parsed.content || parsed.summary) {
        cleanContent = parsed.message || parsed.response || parsed.content || parsed.summary;
      }
    } catch {
      // not valid json, leave as markdown
    }
  }

  const lines = cleanContent.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let listBuffer: { type: 'ul' | 'ol'; items: string[] } | null = null;

  const flushList = () => {
    if (listBuffer) {
      if (listBuffer.type === 'ul') {
        elements.push(
          <ul key={`ul-${elements.length}`} style={{ margin: '8px 0 8px 20px', padding: 0 }}>
            {listBuffer.items.map((item, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {renderInlineStyles(item)}
              </li>
            ))}
          </ul>
        );
      } else {
        elements.push(
          <ol key={`ol-${elements.length}`} style={{ margin: '8px 0 8px 20px', padding: 0 }}>
            {listBuffer.items.map((item, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {renderInlineStyles(item)}
              </li>
            ))}
          </ol>
        );
      }
      listBuffer = null;
    }
  };

  const renderInlineStyles = (text: string): React.ReactNode[] => {
    const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
        return (
          <code
            key={idx}
            style={{
              background: 'rgba(109, 133, 95, 0.1)',
              color: 'var(--primary)',
              padding: '2px 5px',
              borderRadius: 4,
              fontSize: '0.9em',
              fontFamily: 'ui-monospace, monospace'
            }}
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return <strong key={idx}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
        return <em key={idx}>{part.slice(1, -1)}</em>;
      }
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code blocks
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre
            key={`code-${elements.length}`}
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-main)',
              padding: '10px 14px',
              borderRadius: 8,
              fontSize: 12,
              overflowX: 'auto',
              margin: '8px 0'
            }}
          >
            <code>{codeBuffer.join('\n')}</code>
          </pre>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        flushList();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Headings
    if (line.startsWith('### ')) {
      flushList();
      elements.push(
        <h4 key={`h3-${i}`} style={{ fontSize: 14.5, fontWeight: 700, margin: '12px 0 6px 0', color: 'var(--primary)' }}>
          {renderInlineStyles(line.slice(4))}
        </h4>
      );
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      elements.push(
        <h3 key={`h2-${i}`} style={{ fontSize: 16, fontWeight: 700, margin: '14px 0 6px 0', color: 'var(--text-main)' }}>
          {renderInlineStyles(line.slice(3))}
        </h3>
      );
      continue;
    }
    if (line.startsWith('# ')) {
      flushList();
      elements.push(
        <h2 key={`h1-${i}`} style={{ fontSize: 17, fontWeight: 800, margin: '16px 0 8px 0', color: 'var(--text-main)' }}>
          {renderInlineStyles(line.slice(2))}
        </h2>
      );
      continue;
    }

    // Bullet lists
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      const itemText = line.trim().slice(2);
      if (!listBuffer || listBuffer.type !== 'ul') {
        flushList();
        listBuffer = { type: 'ul', items: [itemText] };
      } else {
        listBuffer.items.push(itemText);
      }
      continue;
    }

    // Numbered lists
    const numMatch = line.trim().match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      const itemText = numMatch[2];
      if (!listBuffer || listBuffer.type !== 'ol') {
        flushList();
        listBuffer = { type: 'ol', items: [itemText] };
      } else {
        listBuffer.items.push(itemText);
      }
      continue;
    }

    // Empty lines
    if (!line.trim()) {
      flushList();
      continue;
    }

    // Regular paragraphs
    flushList();
    elements.push(
      <p key={`p-${i}`} style={{ margin: '6px 0', lineHeight: 1.55 }}>
        {renderInlineStyles(line)}
      </p>
    );
  }

  flushList();
  return <div style={{ wordBreak: 'break-word' }}>{elements}</div>;
};

export const BlueprintCopilotModule: React.FC<Props> = ({
  project,
  messages,
  onSendMessage,
  isLoading
}) => {
  const [input, setInput] = useState('');
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const msg = input.trim();
    setInput('');
    await onSendMessage(msg);
  };

  const starterPrompts = [
    'How should we structure our enterprise pricing tiers?',
    'What are the primary technical trade-offs of our current database choice?',
    'Recommend 3 high-impact go-to-market channels for our ICP.',
    'How can we reduce customer churn and strengthen defensibility?'
  ];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: 'calc(100vh - 140px)',
      background: 'var(--bg-card)',
      borderRadius: 14,
      border: '1px solid var(--border-color)',
      overflow: 'hidden',
      color: 'var(--text-main)'
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--bg-subtle)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: 'linear-gradient(135deg, #6d855f, #a68757)',
            color: 'var(--text-main)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 3px 10px rgba(109, 133, 95, 0.25)'
          }}>
            <Bot size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Planning Copilot</h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0' }}>
              Project-aware business and technical guidance for <b>{project.name}</b>
            </p>
          </div>
        </div>
        <span className="stage-badge-purple">Context Active: {project.stage}</span>
      </div>

      {/* Messages Stream */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', margin: 'auto 0', maxWidth: 540, alignSelf: 'center' }}>
            <div style={{
              width: 50,
              height: 50,
              borderRadius: '50%',
              background: 'rgba(109, 133, 95, 0.12)',
              color: 'var(--primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 14px auto'
            }}>
              <Sparkles size={24} />
            </div>
            <h4 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>
              Ask Planning Copilot Anything
            </h4>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
              The assistant has full context of {project.name}'s business stage, technology stack, target customers, and roadmap.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {starterPrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(p)}
                  className="btn-secondary"
                  style={{ textAlign: 'left', fontSize: 12, padding: '10px 12px', height: '100%', lineHeight: 1.4 }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => {
            const isUser = m.role === 'user';
            return (
              <div
                key={m.id}
                style={{
                  display: 'flex',
                  gap: 12,
                  maxWidth: '82%',
                  alignSelf: isUser ? 'flex-end' : 'flex-start'
                }}
              >
                {!isUser && (
                  <div style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'rgba(109, 133, 95, 0.12)',
                    color: 'var(--primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}>
                    <Bot size={16} />
                  </div>
                )}
                <div
                  style={{
                    background: isUser ? 'var(--primary)' : 'var(--bg-subtle)',
                    color: isUser ? '#ffffff' : 'var(--text-main)',
                    padding: '12px 16px',
                    borderRadius: 12,
                    fontSize: 13.5,
                    lineHeight: 1.5,
                    border: isUser ? 'none' : '1px solid var(--border-color)',
                  }}
                >
                  <MarkdownContent content={m.content} isUser={isUser} />
                </div>
                {isUser && (
                  <div style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'var(--bg-subtle)',
                    color: 'var(--text-main)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}>
                    <User size={16} />
                  </div>
                )}
              </div>
            );
          })
        )}

        {isLoading && (
          <div style={{ display: 'flex', gap: 12, alignSelf: 'flex-start', alignItems: 'center' }}>
            <div style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: 'rgba(109, 133, 95, 0.12)',
              color: 'var(--primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Bot size={16} />
            </div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border-color)',
              padding: '10px 16px',
              borderRadius: 12,
              fontSize: 13,
              color: 'var(--text-muted)'
            }}>
              <Loader2 size={16} className="animate-spin" color="var(--primary)" />
              <span>Planning Copilot is formulating a response...</span>
            </div>
          </div>
        )}
        <div ref={chatBottomRef} />
      </div>

      {/* Input bar */}
      <form onSubmit={handleSend} style={{
        padding: 16,
        borderTop: '1px solid var(--border-color)',
        display: 'flex',
        gap: 10,
        background: 'var(--bg-subtle)'
      }}>
        <input
          type="text"
          className="form-input"
              placeholder={`Ask Planning Copilot about ${project.name}...`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading}
          style={{ flex: 1 }}
        />
        <button type="submit" className="btn-primary" disabled={isLoading || !input.trim()}>
          {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </form>
    </div>
  );
};
