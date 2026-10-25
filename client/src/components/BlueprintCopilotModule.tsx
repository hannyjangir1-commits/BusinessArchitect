import React, { useState, useEffect, useRef } from 'react';
import { Project, CopilotMessage } from '../types';
import { Bot, Send, User, Sparkles, Loader2 } from 'lucide-react';
import { saveDraft, getDraft, clearDraft } from '../services/draftStorage';

interface Props {
  project: Project;
  messages: CopilotMessage[];
  onSendMessage: (message: string, tempId: string) => Promise<void>;
  onLoadOlderMessages?: () => Promise<void>;
  hasMoreOlder?: boolean;
  isLoadingOlder?: boolean;
  isLoading: boolean;
  userScope?: string;
}

// Clean, lightweight Markdown component for Planning Copilot
const isSafeUrl = (url: string): boolean => {
  try {
    const trimmed = url.trim();
    if (trimmed.startsWith('#') || trimmed.startsWith('/')) return true;
    const parsed = new URL(trimmed);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' || parsed.protocol === 'mailto:';
  } catch {
    return false;
  }
};

export const renderInlineStyles = (text: string): React.ReactNode[] => {
  const parts = text.split(/(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('[') && part.includes('](') && part.endsWith(')')) {
      const closingBracket = part.indexOf('](');
      const label = part.slice(1, closingBracket);
      const url = part.slice(closingBracket + 2, -1).trim();
      if (isSafeUrl(url)) {
        return (
          <a
            key={idx}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--primary)', textDecoration: 'underline' }}
          >
            {label}
          </a>
        );
      }
      return <span key={idx}>{label}</span>;
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code
          key={idx}
          style={{
            background: 'rgb(69 60 55 / 0.1)',
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

interface ListItemData {
  text: string;
  subItems?: string[];
}

export interface MarkdownBlockData {
  type: 'heading' | 'hr' | 'code' | 'paragraph' | 'ul' | 'ol';
  level?: number;
  text?: string;
  code?: string;
  items?: ListItemData[];
  start?: number;
}

export const parseMarkdownBlocks = (cleanContent: string): MarkdownBlockData[] => {
  const lines = cleanContent.split('\n');
  const blocks: MarkdownBlockData[] = [];
  let inCodeBlock = false;
  let codeBuffer: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Code block fencing
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        blocks.push({ type: 'code', code: codeBuffer.join('\n') });
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(rawLine);
      continue;
    }

    // Horizontal Rule: ---, ***, ___ (at least 3 characters)
    if (/^(\-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: 'hr' });
      continue;
    }

    // Headings
    if (trimmed.startsWith('### ')) {
      blocks.push({ type: 'heading', level: 3, text: trimmed.slice(4) });
      continue;
    }
    if (trimmed.startsWith('## ')) {
      blocks.push({ type: 'heading', level: 2, text: trimmed.slice(3) });
      continue;
    }
    if (trimmed.startsWith('# ')) {
      blocks.push({ type: 'heading', level: 1, text: trimmed.slice(2) });
      continue;
    }

    // Blank lines
    if (!trimmed) {
      continue;
    }

    // List item checks:
    const leadingSpaces = (rawLine.match(/^\s*/) || [''])[0].length;
    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    const unorderedMatch = trimmed.match(/^[-*]\s+(.*)$/);

    const lastBlock = blocks[blocks.length - 1];

    if (orderedMatch && leadingSpaces < 2) {
      const itemText = orderedMatch[2];
      if (lastBlock && lastBlock.type === 'ol') {
        lastBlock.items = lastBlock.items || [];
        lastBlock.items.push({ text: itemText, subItems: [] });
      } else {
        const startNum = parseInt(orderedMatch[1], 10) || 1;
        blocks.push({
          type: 'ol',
          start: startNum,
          items: [{ text: itemText, subItems: [] }]
        });
      }
      continue;
    }

    if (unorderedMatch) {
      const itemText = unorderedMatch[1];
      if (leadingSpaces >= 2 && lastBlock && lastBlock.type === 'ol' && lastBlock.items && lastBlock.items.length > 0) {
        const currentItem = lastBlock.items[lastBlock.items.length - 1];
        currentItem.subItems = currentItem.subItems || [];
        currentItem.subItems.push(itemText);
        continue;
      }

      if (lastBlock && lastBlock.type === 'ul') {
        lastBlock.items = lastBlock.items || [];
        lastBlock.items.push({ text: itemText, subItems: [] });
      } else {
        blocks.push({
          type: 'ul',
          items: [{ text: itemText, subItems: [] }]
        });
      }
      continue;
    }

    // Regular paragraph
    blocks.push({ type: 'paragraph', text: trimmed });
  }

  if (inCodeBlock && codeBuffer.length > 0) {
    blocks.push({ type: 'code', code: codeBuffer.join('\n') });
  }

  return blocks;
};

// Clean, semantic, secure Markdown component for Planning Copilot
export const MarkdownContent: React.FC<{ content: string; isUser: boolean }> = ({ content, isUser }) => {
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

  const blocks = parseMarkdownBlocks(cleanContent);

  return (
    <div style={{ wordBreak: 'break-word' }}>
      {blocks.map((block, idx) => {
        if (block.type === 'hr') {
          return <hr key={`hr-${idx}`} style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '14px 0' }} />;
        }
        if (block.type === 'heading') {
          if (block.level === 1) {
            return (
              <h2 key={`h1-${idx}`} style={{ fontSize: 17, fontWeight: 800, margin: '16px 0 8px 0', color: 'var(--text-main)' }}>
                {renderInlineStyles(block.text || '')}
              </h2>
            );
          }
          if (block.level === 2) {
            return (
              <h3 key={`h2-${idx}`} style={{ fontSize: 16, fontWeight: 700, margin: '14px 0 6px 0', color: 'var(--text-main)' }}>
                {renderInlineStyles(block.text || '')}
              </h3>
            );
          }
          return (
            <h4 key={`h3-${idx}`} style={{ fontSize: 14.5, fontWeight: 700, margin: '12px 0 6px 0', color: 'var(--primary)' }}>
              {renderInlineStyles(block.text || '')}
            </h4>
          );
        }
        if (block.type === 'code') {
          return (
            <pre
              key={`code-${idx}`}
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
              <code>{block.code}</code>
            </pre>
          );
        }
        if (block.type === 'ol') {
          return (
            <ol key={`ol-${idx}`} start={block.start || 1} style={{ margin: '8px 0 8px 20px', padding: 0 }}>
              {(block.items || []).map((item, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  <span>{renderInlineStyles(item.text)}</span>
                  {item.subItems && item.subItems.length > 0 && (
                    <ul style={{ margin: '4px 0 4px 18px', padding: 0 }}>
                      {item.subItems.map((sub, sIdx) => (
                        <li key={sIdx} style={{ marginBottom: 2 }}>
                          {renderInlineStyles(sub)}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ol>
          );
        }
        if (block.type === 'ul') {
          return (
            <ul key={`ul-${idx}`} style={{ margin: '8px 0 8px 20px', padding: 0 }}>
              {(block.items || []).map((item, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  <span>{renderInlineStyles(item.text)}</span>
                  {item.subItems && item.subItems.length > 0 && (
                    <ul style={{ margin: '4px 0 4px 18px', padding: 0 }}>
                      {item.subItems.map((sub, sIdx) => (
                        <li key={sIdx} style={{ marginBottom: 2 }}>
                          {renderInlineStyles(sub)}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={`p-${idx}`} style={{ margin: '6px 0', lineHeight: 1.55 }}>
            {renderInlineStyles(block.text || '')}
          </p>
        );
      })}
    </div>
  );
};


export const BlueprintCopilotModule: React.FC<Props> = ({
  project,
  messages,
  onSendMessage,
  onLoadOlderMessages,
  hasMoreOlder = false,
  isLoadingOlder = false,
  isLoading,
  userScope
}) => {
  const [input, setInput] = useState(() => (userScope ? getDraft<string>(userScope, 'copilot_input', project.id) || '' : ''));
  const [isSending, setIsSending] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isPaginatingOlderRef = useRef(false);
  const shouldScrollToBottomRef = useRef(false);
  const isInitialLoadRef = useRef(true);
  const scrollSnapshotRef = useRef<{ scrollHeight: number; scrollTop: number } | null>(null);

  // Deduplicate messages by id preserving chronological order
  const displayMessages = React.useMemo(() => {
    const seen = new Set<string>();
    const unique: CopilotMessage[] = [];
    for (const m of (messages || [])) {
      if (m && m.id && !seen.has(m.id)) {
        seen.add(m.id);
        unique.push(m);
      } else if (m && !m.id) {
        unique.push(m);
      }
    }
    return unique;
  }, [messages]);

  useEffect(() => {
    if (isPaginatingOlderRef.current && scrollSnapshotRef.current && scrollContainerRef.current) {
      const container = scrollContainerRef.current;
      const heightDiff = container.scrollHeight - scrollSnapshotRef.current.scrollHeight;
      container.scrollTop = scrollSnapshotRef.current.scrollTop + heightDiff;
      isPaginatingOlderRef.current = false;
      scrollSnapshotRef.current = null;
    } else if (shouldScrollToBottomRef.current || isInitialLoadRef.current) {
      if (typeof chatBottomRef.current?.scrollIntoView === 'function') {
        chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
      }
      shouldScrollToBottomRef.current = false;
      if (displayMessages.length > 0) {
        isInitialLoadRef.current = false;
      }
    }
  }, [displayMessages, isLoading]);

  const handleLoadOlder = async () => {
    if (!onLoadOlderMessages || isLoadingOlder) return;
    if (scrollContainerRef.current) {
      scrollSnapshotRef.current = {
        scrollHeight: scrollContainerRef.current.scrollHeight,
        scrollTop: scrollContainerRef.current.scrollTop
      };
      isPaginatingOlderRef.current = true;
    }
    await onLoadOlderMessages();
  };

  // Persist unsent draft input
  useEffect(() => {
    if (userScope) {
      if (input.trim()) {
        saveDraft(userScope, 'copilot_input', input, project.id);
      } else {
        clearDraft(userScope, 'copilot_input', project.id);
      }
    }
  }, [userScope, input, project.id]);

  const handleSendText = async (text: string) => {
    if (!text.trim() || isLoading || isSending) return;
    const msg = text.trim();
    const tempId = `temp-user-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const originalInput = input;
    setInput('');
    if (userScope) clearDraft(userScope, 'copilot_input', project.id);
    shouldScrollToBottomRef.current = true;
    setIsSending(true);

    try {
      await onSendMessage(msg, tempId);
    } catch {
      // Restore draft on confirmed failure so user never loses their question
      setInput(originalInput || msg);
      if (userScope) saveDraft(userScope, 'copilot_input', originalInput || msg, project.id);
    } finally {
      setIsSending(false);
    }
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendText(input);
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
            borderRadius: 8,
            background: 'var(--bg-subtle)',
            color: 'var(--text-main)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--shadow-sm)'
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
      <div
        ref={scrollContainerRef}
        style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}
      >
        {hasMoreOlder && (
          <div style={{ textAlign: 'center', marginBottom: 6 }}>
            <button
              type="button"
              onClick={handleLoadOlder}
              disabled={isLoadingOlder}
              className="btn-secondary"
              style={{
                fontSize: 12,
                padding: '6px 14px',
                borderRadius: 6,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              {isLoadingOlder && <Loader2 size={12} className="animate-spin" />}
              {isLoadingOlder ? 'Loading older messages...' : 'Load older messages'}
            </button>
          </div>
        )}
        {isLoading && displayMessages.length === 0 ? (
          <div
            role="status"
            aria-live="polite"
            aria-label="Loading conversation history"
            style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%', maxWidth: 720, margin: '20px auto 0' }}
          >
            <div style={{ display: 'flex', gap: 12, maxWidth: '75%', alignSelf: 'flex-start' }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--border-color)', animation: 'pulse 1.5s infinite', flexShrink: 0 }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
                <div style={{ width: 140, height: 14, borderRadius: 4, background: 'var(--border-color)', animation: 'pulse 1.5s infinite' }} />
                <div style={{ width: 320, height: 44, borderRadius: 8, background: 'var(--border-color)', animation: 'pulse 1.5s infinite' }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, maxWidth: '65%', alignSelf: 'flex-end', flexDirection: 'row-reverse' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, alignItems: 'flex-end' }}>
                <div style={{ width: 240, height: 36, borderRadius: 8, background: 'var(--border-color)', animation: 'pulse 1.5s infinite' }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, maxWidth: '80%', alignSelf: 'flex-start' }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--border-color)', animation: 'pulse 1.5s infinite', flexShrink: 0 }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
                <div style={{ width: 180, height: 14, borderRadius: 4, background: 'var(--border-color)', animation: 'pulse 1.5s infinite' }} />
                <div style={{ width: 420, height: 60, borderRadius: 8, background: 'var(--border-color)', animation: 'pulse 1.5s infinite' }} />
              </div>
            </div>
          </div>
        ) : displayMessages.length === 0 ? (
          <div style={{ textAlign: 'center', margin: 'auto 0', maxWidth: 540, alignSelf: 'center' }}>
            <div style={{
              width: 50,
              height: 50,
              borderRadius: '50%',
              background: 'rgb(69 60 55 / 0.12)',
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
                  type="button"
                  disabled={isLoading || isSending}
                  onClick={() => handleSendText(p)}
                  className="btn-secondary"
                  style={{ textAlign: 'left', fontSize: 12, padding: '10px 12px', height: '100%', lineHeight: 1.4 }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          displayMessages.map((m) => {
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
                    background: 'rgb(69 60 55 / 0.12)',
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
                    color: isUser ? 'var(--bg-card)' : 'var(--text-main)',
                    padding: '12px 16px',
                    borderRadius: 12,
                    fontSize: 13.5,
                    lineHeight: 1.5,
                    border: isUser ? (m.status === 'failed' ? '1px solid var(--danger, #ef4444)' : 'none') : '1px solid var(--border-color)',
                    opacity: m.status === 'sending' ? 0.75 : 1
                  }}
                >
                  <MarkdownContent content={m.content} isUser={isUser} />
                  {m.status === 'sending' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, opacity: 0.85 }}>
                      <Loader2 size={11} className="animate-spin" />
                      <span>Sending...</span>
                    </div>
                  )}
                  {m.status === 'failed' && (
                    <div style={{ marginTop: 6, fontSize: 11, color: '#fca5a5', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span>Failed to deliver</span>
                      <button
                        type="button"
                        onClick={() => handleSendText(m.content)}
                        style={{
                          textDecoration: 'underline',
                          background: 'none',
                          border: 'none',
                          color: '#fff',
                          cursor: 'pointer',
                          padding: 0,
                          fontSize: 11,
                          fontWeight: 600
                        }}
                      >
                        Retry
                      </button>
                    </div>
                  )}
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
              background: 'rgb(69 60 55 / 0.12)',
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
          disabled={isLoading || isSending}
          style={{ flex: 1 }}
        />
        <button type="submit" className="btn-primary" disabled={isLoading || isSending || !input.trim()}>
          {isLoading || isSending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </form>
    </div>
  );
};
