import React, { useState, useEffect, useRef } from 'react';
import { Project, CopilotMessage, CopilotProposalResponse } from '../types';
import {
  Bot, Send, User, Sparkles, Loader2, GitPullRequest, MessageSquare,
  CheckCircle2, ArrowRight, X, AlertTriangle
} from 'lucide-react';
import { saveDraft, getDraft, clearDraft } from '../services/draftStorage';
import { api } from '../services/api';
import { queryCache } from '../services/queryCache';
import { Dialog } from './common/Dialog';

interface Props {
  project: Project;
  messages: CopilotMessage[];
  onSendMessage: (message: string, clientMsgId: string) => Promise<void>;
  onLoadOlderMessages?: () => Promise<void>;
  onRefreshMessages?: () => Promise<void>;
  onCheckStatus?: (clientMsgId: string) => Promise<void>;
  onApplyProposal?: (targetModule: string, instruction: string, proposalId?: string) => Promise<void>;
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
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
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
  onRefreshMessages,
  onCheckStatus,
  onApplyProposal,
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

  // Proposal Workflow State
  const [copilotMode, setCopilotMode] = useState<'ask' | 'propose'>('ask');
  const [proposalTargetModule, setProposalTargetModule] = useState<string>('bmc');
  const [proposalInput, setProposalInput] = useState<string>('');
  const [isGeneratingProposal, setIsGeneratingProposal] = useState(false);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [currentProposal, setCurrentProposal] = useState<CopilotProposalResponse | null>(null);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [isApplyingProposal, setIsApplyingProposal] = useState(false);
  const [applySuccessMessage, setApplySuccessMessage] = useState<string | null>(null);
  const [lastProposedInstruction, setLastProposedInstruction] = useState<string>('');

  const PROPOSAL_MODULE_OPTIONS = [
    { id: 'bmc', label: 'Business Model Canvas' },
    { id: 'tech_stack', label: 'Technology Stack' },
    { id: 'execution_roadmap', label: 'Roadmap & Tasks' },
    { id: 'idea_validator', label: 'Idea Validator' },
    { id: 'market_research', label: 'Market Research' },
  ];

  const handleGenerateProposal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proposalInput.trim() || isGeneratingProposal) return;
    setIsGeneratingProposal(true);
    setProposalError(null);
    setApplySuccessMessage(null);
    const instruction = proposalInput.trim();
    setLastProposedInstruction(instruction);

    try {
      const proposal = await api.copilot.proposeChange(project.id, proposalTargetModule, instruction);
      setCurrentProposal(proposal);
      setIsReviewOpen(true);
    } catch (err: any) {
      setProposalError(err.message || 'Failed to generate proposal preview.');
    } finally {
      setIsGeneratingProposal(false);
    }
  };

  const handleApplyProposal = async () => {
    if (!currentProposal) return;
    setIsApplyingProposal(true);
    setProposalError(null);
    try {
      if (onApplyProposal) {
        if (currentProposal.id) {
          await onApplyProposal(currentProposal.target_module, lastProposedInstruction, currentProposal.id);
        } else {
          await onApplyProposal(currentProposal.target_module, lastProposedInstruction);
        }
      } else if (currentProposal.id) {
        await api.copilot.applyProposal(project.id, currentProposal.id);
      } else {
        await api.modules.modify(project.id, currentProposal.target_module, lastProposedInstruction);
      }
      queryCache.invalidate(new RegExp(`^module:${project.id}:${currentProposal.target_module}`));
      queryCache.invalidate(new RegExp(`^tasks:${project.id}`));
      queryCache.invalidate(new RegExp(`^overview:${project.id}`));
      setApplySuccessMessage(`Successfully updated ${currentProposal.target_module.replaceAll('_', ' ')}! A new version has been saved.`);
      setIsReviewOpen(false);
      setProposalInput('');
    } catch (err: any) {
      setProposalError(err.message || 'Failed to apply change to module.');
    } finally {
      setIsApplyingProposal(false);
    }
  };

  const formatDiffValue = (val: any) => {
    if (val === undefined || val === null) {
      return <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 13 }}>None</span>;
    }
    if (Array.isArray(val)) {
      if (val.length === 0) {
        return <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 13 }}>Empty list</span>;
      }
      return (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {val.map((item, idx) => (
            <li key={idx}>
              {typeof item === 'object' ? JSON.stringify(item) : String(item)}
            </li>
          ))}
        </ul>
      );
    }
    if (typeof val === 'object') {
      return (
        <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace' }}>
          {JSON.stringify(val, null, 2)}
        </pre>
      );
    }
    return <span style={{ fontSize: 13 }}>{String(val)}</span>;
  };

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

  const handleSendText = async (text: string, existingClientMsgId?: string) => {
    if (!text.trim() || isLoading || isSending) return;
    const msg = text.trim();
    const clientMsgId = existingClientMsgId || `temp-user-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const originalInput = input;
    if (!existingClientMsgId) {
      setInput('');
      if (userScope) clearDraft(userScope, 'copilot_input', project.id);
    }
    shouldScrollToBottomRef.current = true;
    setIsSending(true);

    try {
      await onSendMessage(msg, clientMsgId);
    } catch {
      // Restore draft on confirmed failure so user never loses their question
      if (!existingClientMsgId) {
        setInput(originalInput || msg);
        if (userScope) saveDraft(userScope, 'copilot_input', originalInput || msg, project.id);
      }
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

        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* Mode Switcher */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 8,
            padding: 3,
            gap: 2
          }}>
            <button
              type="button"
              onClick={() => setCopilotMode('ask')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '5px 12px',
                borderRadius: 6,
                border: 'none',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                background: copilotMode === 'ask' ? 'var(--primary)' : 'transparent',
                color: copilotMode === 'ask' ? '#fff' : 'var(--text-muted)',
                transition: 'all 0.15s ease'
              }}
            >
              <MessageSquare size={13} />
              <span>Ask</span>
            </button>
            <button
              type="button"
              onClick={() => setCopilotMode('propose')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '5px 12px',
                borderRadius: 6,
                border: 'none',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                background: copilotMode === 'propose' ? 'var(--primary)' : 'transparent',
                color: copilotMode === 'propose' ? '#fff' : 'var(--text-muted)',
                transition: 'all 0.15s ease'
              }}
            >
              <GitPullRequest size={13} />
              <span>Propose Change</span>
            </button>
          </div>

          <span className="stage-badge-purple">Context Active: {project.stage}</span>
        </div>
      </div>

      {copilotMode === 'ask' ? (
        <>
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
                  {m.status === 'uncertain' && (
                    <div style={{ marginTop: 6, fontSize: 11, color: '#fef08a', display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <span>We could not confirm whether this response finished.</span>
                      <div style={{ display: 'flex', gap: 10, marginTop: 2, flexWrap: 'wrap' }}>
                        {onCheckStatus && (m.client_msg_id || m.id) && (
                          <button
                            type="button"
                            onClick={() => onCheckStatus(m.client_msg_id || m.id)}
                            style={{ textDecoration: 'underline', background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0, fontSize: 11, fontWeight: 600 }}
                          >
                            Check status
                          </button>
                        )}
                        {onRefreshMessages && (
                          <button
                            type="button"
                            onClick={() => onRefreshMessages()}
                            style={{ textDecoration: 'underline', background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0, fontSize: 11, fontWeight: 600 }}
                          >
                            Refresh conversation
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleSendText(m.content, m.client_msg_id || m.id)}
                          style={{ textDecoration: 'underline', background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0, fontSize: 11, fontWeight: 600 }}
                        >
                          Retry
                        </button>
                      </div>
                    </div>
                  )}
                  {m.status === 'failed' && (
                    <div style={{ marginTop: 6, fontSize: 11, color: '#fca5a5', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span>Failed to deliver</span>
                      <button
                        type="button"
                        onClick={() => handleSendText(m.content, m.client_msg_id || m.id)}
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
    </>
  ) : (
    /* Propose Change View */
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      <div style={{ padding: 24, flex: 1, display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 840, margin: '0 auto', width: '100%' }}>
        {/* Informational Guidance Banner */}
        <div style={{
          background: 'var(--bg-subtle)',
          border: '1px solid var(--border-color)',
          borderRadius: 12,
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 14
        }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgb(69 60 55 / 0.12)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <GitPullRequest size={20} />
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: '0 0 4px', fontSize: 14, fontWeight: 700, color: 'var(--text-main)' }}>
              Non-Destructive Module Proposals
            </h4>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Instruct Copilot to draft updates for your business modules. You will receive an interactive before-and-after diff with impacted assumptions and tasks to inspect before confirming.
            </p>
          </div>
        </div>

        {/* Success notice */}
        {applySuccessMessage && (
          <div style={{
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: 8,
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            color: 'var(--success-text, #10b981)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <CheckCircle2 size={18} />
              <span style={{ fontSize: 13, fontWeight: 600 }}>{applySuccessMessage}</span>
            </div>
            <button
              type="button"
              onClick={() => setApplySuccessMessage(null)}
              style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}
            >
              <X size={15} />
            </button>
          </div>
        )}

        {/* Error notice */}
        {proposalError && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 8,
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            color: 'var(--danger-text, #ef4444)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <AlertTriangle size={18} />
              <span style={{ fontSize: 13, fontWeight: 500 }}>{proposalError}</span>
            </div>
            <button
              type="button"
              onClick={() => setProposalError(null)}
              style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}
            >
              <X size={15} />
            </button>
          </div>
        )}

        {/* Pending proposal ready banner */}
        {currentProposal && (
          <div style={{
            background: 'var(--bg-subtle)',
            border: '1px solid var(--primary)',
            borderRadius: 10,
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12
          }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: 0.5 }}>
                Pending Proposal Ready
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-main)', marginTop: 2 }}>
                {currentProposal.target_module.replaceAll('_', ' ')} · {currentProposal.summary}
              </div>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={() => setIsReviewOpen(true)}
              style={{ fontSize: 12, padding: '7px 16px', gap: 6 }}
            >
              <span>Review Diff</span>
              <ArrowRight size={14} />
            </button>
          </div>
        )}

        {/* Target Module Selection */}
        <div>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-main)', marginBottom: 8 }}>
            Target Module to Update:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
            {PROPOSAL_MODULE_OPTIONS.map((opt) => {
              const isSel = proposalTargetModule === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setProposalTargetModule(opt.id)}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: isSel ? '1.5px solid var(--primary)' : '1px solid var(--border-color)',
                    background: isSel ? 'rgba(69, 60, 55, 0.08)' : 'var(--bg-card)',
                    color: isSel ? 'var(--primary)' : 'var(--text-main)',
                    fontWeight: isSel ? 700 : 500,
                    fontSize: 13,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Instruction Composer */}
        <div>
          <label htmlFor="proposal-instruction-input" style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-main)', marginBottom: 8 }}>
            Proposed Changes / Instructions:
          </label>
          <textarea
            id="proposal-instruction-input"
            className="form-input"
            rows={4}
            value={proposalInput}
            onChange={(e) => setProposalInput(e.target.value)}
            placeholder={`Describe the updates for ${PROPOSAL_MODULE_OPTIONS.find(o => o.id === proposalTargetModule)?.label}... (e.g. "Add university bike co-ops to key partners and adjust pricing strategy for students")`}
            style={{ width: '100%', resize: 'vertical', fontSize: 13, padding: 12 }}
            disabled={isGeneratingProposal}
          />
        </div>

        {/* Starter Suggestion Chips */}
        <div>
          <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>
            Suggested Modifications
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {[
              `Add 2 enterprise pilot milestones and test SLAs`,
              `Introduce high-margin subscription tier with onboarding fee`,
              `Add competitive differentiation against incumbent legacy vendors`,
              `Incorporate automated security compliance tasks in Q2`
            ].map((sugg, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setProposalInput(sugg)}
                style={{
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 16,
                  padding: '5px 12px',
                  fontSize: 12,
                  color: 'var(--text-muted)',
                  cursor: 'pointer'
                }}
              >
                + {sugg}
              </button>
            ))}
          </div>
        </div>

        {/* Action Bar */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
          <button
            type="button"
            className="btn-primary"
            onClick={handleGenerateProposal}
            disabled={isGeneratingProposal || !proposalInput.trim()}
            style={{ gap: 8, padding: '10px 22px', fontSize: 13 }}
          >
            {isGeneratingProposal ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Analyzing & Drafting Preview...</span>
              </>
            ) : (
              <>
                <Sparkles size={16} />
                <span>Generate Proposal Preview</span>
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  )}

  {/* Proposal Review Modal */}
  {isReviewOpen && currentProposal && (
    <Dialog
      isOpen={true}
      onClose={() => setIsReviewOpen(false)}
      dismissible={!isApplyingProposal}
      showCloseButton={false}
      ariaLabelledBy="proposal-review-title"
      maxWidth={820}
    >
      <div style={{ display: 'flex', flexDirection: 'column', maxHeight: '80vh' }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: 14,
          borderBottom: '1px solid var(--border-color)',
          marginBottom: 16
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: 'rgb(69 60 55 / 0.12)',
              color: 'var(--primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <GitPullRequest size={18} />
            </div>
            <div>
              <h3 id="proposal-review-title" style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-main)' }}>
                Review Change Proposal
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
                Target: <b>{currentProposal.target_module.replaceAll('_', ' ').toUpperCase()}</b> · Non-destructive preview
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsReviewOpen(false)}
            disabled={isApplyingProposal}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
            aria-label="Close proposal review"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Modal Content */}
        <div style={{ overflowY: 'auto', flex: 1, paddingRight: 4, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Summary */}
          <div style={{
            background: 'var(--bg-subtle)',
            border: '1px solid var(--border-color)',
            borderRadius: 8,
            padding: '12px 16px'
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
              Summary of Changes
            </div>
            <div style={{ fontSize: 13.5, color: 'var(--text-main)', lineHeight: 1.45 }}>
              {currentProposal.summary}
            </div>
          </div>

          {/* Side-by-Side Diff Sections */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 10 }}>
              Detailed Changes (Before vs After)
            </div>
            {Object.keys(currentProposal.proposed_diff || {}).length === 0 ? (
              <div style={{ padding: 14, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, background: 'var(--bg-subtle)', borderRadius: 8 }}>
                No direct field changes detected. Content is aligned.
              </div>
            ) : (
              Object.entries(currentProposal.proposed_diff).map(([key, diff]) => (
                <div
                  key={key}
                  style={{
                    marginBottom: 14,
                    border: '1px solid var(--border-color)',
                    borderRadius: 8,
                    overflow: 'hidden'
                  }}
                >
                  <div style={{
                    background: 'var(--bg-subtle)',
                    padding: '8px 12px',
                    fontWeight: 700,
                    fontSize: 12.5,
                    borderBottom: '1px solid var(--border-color)',
                    color: 'var(--text-main)'
                  }}>
                    {key.replaceAll('_', ' ').toUpperCase()}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
                    <div style={{
                      padding: '12px 14px',
                      background: 'rgba(239, 68, 68, 0.04)',
                      borderRight: '1px solid var(--border-color)'
                    }}>
                      <div style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: 'var(--danger-text, #ef4444)',
                        marginBottom: 8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4
                      }}>
                        <span>&minus; Current</span>
                      </div>
                      {formatDiffValue(diff.before)}
                    </div>
                    <div style={{
                      padding: '12px 14px',
                      background: 'rgba(16, 185, 129, 0.04)'
                    }}>
                      <div style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: 'var(--success-text, #10b981)',
                        marginBottom: 8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4
                      }}>
                        <span>+ Proposed</span>
                      </div>
                      {formatDiffValue(diff.after)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Impact Analysis */}
          {(currentProposal.affected_assumptions?.length > 0 || currentProposal.affected_tasks?.length > 0) && (
            <div style={{
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              padding: '12px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: 10
            }}>
              <div style={{ fontSize: 11.5, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                Impacted Blueprint Entities
              </div>
              {currentProposal.affected_assumptions?.length > 0 && (
                <div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-main)' }}>
                    Affected Assumptions ({currentProposal.affected_assumptions.length}):
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                    {currentProposal.affected_assumptions.map((a, i) => (
                      <span key={i} style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-card)', border: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {currentProposal.affected_tasks?.length > 0 && (
                <div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-main)' }}>
                    Affected Roadmap Tasks ({currentProposal.affected_tasks.length}):
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                    {currentProposal.affected_tasks.map((t, i) => (
                      <span key={i} style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-card)', border: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingTop: 16,
          borderTop: '1px solid var(--border-color)',
          marginTop: 16
        }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setIsReviewOpen(false)}
            disabled={isApplyingProposal}
          >
            Dismiss Preview
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleApplyProposal}
            disabled={isApplyingProposal}
            style={{ gap: 8 }}
          >
            {isApplyingProposal ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Applying Changes...</span>
              </>
            ) : (
              <>
                <CheckCircle2 size={16} />
                <span>Apply Changes to Module</span>
              </>
            )}
          </button>
        </div>
      </div>
    </Dialog>
  )}
</div>
);
};
