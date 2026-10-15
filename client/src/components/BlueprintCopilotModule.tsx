import React, { useState, useEffect, useRef } from 'react';
import { Project, CopilotMessage } from '../types';
import { Bot, Send, User, Sparkles, Loader2 } from 'lucide-react';

interface Props {
  project: Project;
  messages: CopilotMessage[];
  onSendMessage: (message: string) => Promise<void>;
  isLoading: boolean;
}

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
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 3px 10px rgba(99, 102, 241, 0.25)'
          }}>
            <Bot size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Planning Assistant</h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0' }}>
              Project-aware venture advisor & technical planning assistant for <b>{project.name}</b>
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
              background: 'rgba(99, 102, 241, 0.12)',
              color: 'var(--primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 14px auto'
            }}>
              <Sparkles size={24} />
            </div>
            <h4 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>
              Ask Planning Assistant Anything
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
                    background: 'rgba(99, 102, 241, 0.12)',
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
                    whiteSpace: 'pre-wrap'
                  }}
                >
                  {m.content}
                </div>
                {isUser && (
                  <div style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: '#1e293b',
                    color: '#ffffff',
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
              background: 'rgba(99, 102, 241, 0.12)',
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
              <span>Planning Assistant is formulating response...</span>
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
          placeholder={`Ask Planning Assistant about ${project.name}...`}
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
