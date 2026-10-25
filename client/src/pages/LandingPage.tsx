import React, { useState, useRef, useEffect } from 'react';
import {
  Layers, Compass, Cpu, Calendar, CheckCircle2, TrendingUp, ListTodo,
  FileSpreadsheet, ArrowRight, AlertCircle, Loader2, ShieldCheck,
  Eye, EyeOff, Bot, Wrench, MessageSquare, ClipboardList, Clock
} from 'lucide-react';
import { api } from '../services/api';
import { SessionData, User } from '../types';

interface Props {
  onAuthenticated: (session: SessionData) => void;
  currentUser?: User | null;
  onOpenWorkspace?: () => void;
}

export const LandingPage: React.FC<Props> = ({ onAuthenticated, currentUser, onOpenWorkspace }) => {
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [isLoginTab, setIsLoginTab] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const openerRef = useRef<HTMLElement | null>(null);
  const modalCardRef = useRef<HTMLDivElement | null>(null);

  const openAuthModal = (isLogin: boolean) => {
    openerRef.current = document.activeElement as HTMLElement | null;
    setIsLoginTab(isLogin);
    setErrorMsg(null);
    setAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setAuthModalOpen(false);
    setErrorMsg(null);
    openerRef.current?.focus();
  };

  useEffect(() => {
    if (!authModalOpen) return;

    const focusTimer = setTimeout(() => {
      if (modalCardRef.current) {
        const firstInput = modalCardRef.current.querySelector<HTMLElement>('input, button[type="button"]');
        firstInput?.focus();
      }
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        closeAuthModal();
        return;
      }
      if (e.key === 'Tab' && modalCardRef.current) {
        const focusableElements = modalCardRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length === 0) return;
        const first = focusableElements[0];
        const last = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      clearTimeout(focusTimer);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [authModalOpen]);

  // Form Fields
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);

    try {
      if (isLoginTab) {
        const session = await api.auth.login(email || username, password);
        onAuthenticated(session);
      } else {
        if (password !== confirmPassword) {
          throw new Error('Passwords do not match');
        }
        if (!termsAccepted) {
          throw new Error('You must accept the Terms of Service & Privacy Policy');
        }
        const session = await api.auth.register({
          username: username.trim(),
          email: email.trim(),
          password,
          confirm_password: confirmPassword,
          terms_accepted: termsAccepted
        });
        onAuthenticated(session);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      el.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth' });
    }
  };

  return (
    <div className="landing-page" style={{ minHeight: '100vh', background: 'var(--bg-workspace)', color: 'var(--text-main)', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navbar */}
      <header style={{
        height: 72,
        borderBottom: '1px solid var(--border-color)',
        padding: '0 clamp(16px, 4vw, 36px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        backgroundColor: 'rgb(69 60 55 / 0.96)',
        backdropFilter: 'blur(8px)',
        zIndex: 50
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: 'var(--bg-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 8px rgb(69 60 55 / 0.15)'
          }}>
            <Layers size={22} color="var(--primary-text)" />
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: -0.2, color: 'var(--text-main)' }}>Venture Atlas</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: 0.8 }}>BUSINESS PLANNING & VALIDATION</div>
          </div>
        </div>

        {/* Center Nav Links */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 24 }} className="landing-desktop-nav">
          <button
            type="button"
            onClick={() => scrollToSection('planning-sections')}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer', transition: 'color 0.15s ease' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            Workspace Modules
          </button>
          <button
            type="button"
            onClick={() => scrollToSection('workflow')}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer', transition: 'color 0.15s ease' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            Planning Workflow
          </button>
          <button
            type="button"
            onClick={() => scrollToSection('illustrative-example')}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer', transition: 'color 0.15s ease' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            Enterprise Architecture
          </button>
        </nav>

        {/* Right CTA */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {currentUser ? (
            <>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>
                {currentUser.username || currentUser.email}
              </span>
              <button
                type="button"
                onClick={onOpenWorkspace}
                className="btn-primary"
                style={{ padding: '8px 18px', fontSize: 13 }}
              >
                Open workspace &rarr;
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => openAuthModal(true)}
                style={{
                  background: 'transparent',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-muted)',
                  padding: '8px 16px',
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--primary-text)'; e.currentTarget.style.color = 'var(--text-main)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-color)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => openAuthModal(false)}
                className="btn-primary"
                style={{ padding: '8px 18px', fontSize: 13 }}
              >
                Get Started
              </button>
            </>
          )}
        </div>
      </header>

      {/* Hero Section */}
      <section style={{ padding: '72px clamp(16px, 4vw, 32px) 56px clamp(16px, 4vw, 32px)', textAlign: 'center', maxWidth: 1040, margin: '0 auto', width: '100%' }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 16px',
          borderRadius: 9999,
          background: 'rgb(69 60 55 / 0.12)',
          color: 'var(--text-muted)',
          fontSize: 12,
          fontWeight: 700,
          marginBottom: 24,
          border: '1px solid rgb(69 60 55 / 0.25)',
          letterSpacing: 0.3
        }}>
          <ShieldCheck size={14} /> Turn your business idea into an actionable plan
        </div>

        <h1 style={{
          fontSize: 'clamp(32px, 5vw, 50px)',
          fontWeight: 800,
          lineHeight: 1.15,
          letterSpacing: -1,
          marginBottom: 20,
          color: 'var(--text-main)'
        }}>
          Plan your business.{' '}
          <span style={{ color: 'var(--primary-text)' }}>
            Decide what to test next.
          </span>
        </h1>

        <p style={{
          fontSize: 'clamp(15px, 2vw, 18px)',
          color: 'var(--text-muted)',
          lineHeight: 1.6,
          maxWidth: 720,
          margin: '0 auto 36px auto'
        }}>
          Build a business model, check your assumptions, choose practical tools, and turn decisions into a working plan.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}>
          {currentUser ? (
            <button
              type="button"
              onClick={onOpenWorkspace}
              className="btn-primary"
              style={{ fontSize: 14.5, padding: '13px 28px', borderRadius: 10, boxShadow: '0 4px 16px rgb(69 60 55 / 0.4)' }}
            >
              Open workspace <ArrowRight size={17} />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => openAuthModal(false)}
              className="btn-primary"
              aria-label="Create a project — Create Your Blueprint"
              style={{ fontSize: 14.5, padding: '13px 28px', borderRadius: 10, boxShadow: '0 4px 16px rgb(69 60 55 / 0.4)' }}
            >
              Create a project <ArrowRight size={17} />
            </button>
          )}
          <button
            type="button"
            onClick={() => scrollToSection('illustrative-example')}
            className="btn-secondary"
            style={{
              padding: '13px 24px',
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 600
            }}
          >
            See an example
          </button>
        </div>
      </section>

      {/* Illustrative Example Section: Local Bicycle Repair Service */}
      <section id="illustrative-example" style={{ padding: '0 clamp(16px, 4vw, 32px) 70px clamp(16px, 4vw, 32px)', maxWidth: 1160, margin: '0 auto', width: '100%' }}>
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: 16,
          padding: 24,
          boxShadow: '0 12px 30px -18px rgb(69 60 55 / 0.18)'
        }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: 16, marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                background: 'rgb(69 60 55 / 0.15)',
                color: 'var(--primary)',
                fontSize: 11.5,
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: 6,
                letterSpacing: 0.3
              }}>
                Illustrative example
              </div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Worked Journey: Riverside Mobile Bike Repair
              </h2>
            </div>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Solo service venture · Initial budget: $4,000 · WhatsApp bookings
            </span>
          </div>

          {/* 4 Comparative Worked Steps */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 250px), 1fr))', gap: 16 }}>
            {/* Box 1: Venture Profile */}
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Compass size={17} color="var(--primary-text)" />
                <h3 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>1. Model & Target ICP</h3>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                Alexander Osterwalder 9-block layout tailored to local mobile service delivery.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11.5 }}>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-main)' }}>
                  <b>Value:</b> Doorstep repair before 8 AM for commuters
                </div>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>
                  <b>Revenue:</b> $80 tune-up package + 25% parts markup
                </div>
              </div>
            </div>

            {/* Box 2: Pragmatic Tool Selection */}
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Wrench size={17} color="var(--primary-text)" />
                <h3 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>2. Practical Tooling</h3>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                Honest operational toolchain instead of unneeded cloud microservices.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11.5 }}>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-main)' }}>
                  <b>Inquiries:</b> WhatsApp Business catalog & templates
                </div>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>
                  <b>Records & POS:</b> Google Sheets + Square card reader
                </div>
              </div>
            </div>

            {/* Box 3: Falsifiable Experiment */}
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <CheckCircle2 size={17} color="var(--primary-text)" />
                <h3 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>3. Assumption Testing</h3>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                Preliminary AI assessment paired with practical customer discovery actions.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11.5 }}>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-main)' }}>
                  <b>Test:</b> 20 commuter interviews at commuter train depot
                </div>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>
                  <b>Threshold:</b> 8+ commuters commit to test booking
                </div>
              </div>
            </div>

            {/* Box 4: Execution Roadmap */}
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Calendar size={17} color="var(--primary-text)" />
                <h3 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>4. First Execution Tasks</h3>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                Date-derived milestone delivery schedule with explicit dependencies.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11.5 }}>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-main)' }}>
                  <b>Task P1-01:</b> Procure mobile repair stand & toolkit
                </div>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>
                  <b>Task P1-02:</b> Run 5 trial tune-ups with local club
                </div>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 18, padding: 12, background: 'var(--bg-subtle)', borderRadius: 8, border: '1px solid var(--border-color)', fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.5 }}>
            <strong>Demonstration note:</strong> All examples are illustrative demonstrations, not verified customer outcomes. AI suggestions provide preliminary structure and require founder validation. Market research notes indicate areas where primary research is necessary.
          </div>
        </div>
      </section>

      {/* Structured Planning Sections: Grouped by Purpose */}
      <section id="planning-sections" style={{ padding: '60px clamp(16px, 4vw, 32px) 80px clamp(16px, 4vw, 32px)', maxWidth: 1160, margin: '0 auto', width: '100%', borderTop: '1px solid var(--border-color)' }}>
        <div style={{ textAlign: 'center', marginBottom: 44 }}>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-main)', letterSpacing: -0.5, marginBottom: 12 }}>
            Workspace Planning Sections
          </h2>
          <p style={{ fontSize: 15, color: 'var(--text-muted)', maxWidth: 640, margin: '0 auto' }}>
            Five saved planning sections for core business formulation, supported by dedicated execution and export utilities.
          </p>
        </div>

        {/* Group 1: Core Planning Sections */}
        <div style={{ marginBottom: 36 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--primary)', letterSpacing: 0.6 }}>
              Core Planning Sections (5 Saved Sections)
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: 16 }}>
            {/* Card 1 */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 22 }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgb(69 60 55 / 0.15)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
                <Compass size={20} />
              </div>
              <h3 style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>1. Business Model Canvas</h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55, margin: 0 }}>
                Alexander Osterwalder 9-block grid with value proposition, channels, customer relationships, revenue streams, and cost drivers.
              </p>
            </div>

            {/* Card 2 */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 22 }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgb(69 60 55 / 0.15)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
                <Cpu size={20} />
              </div>
              <h3 style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>2. Practical Tools & Technology</h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55, margin: 0 }}>
                Stage-aware recommendations covering both existing operational tools (messaging, spreadsheets) and custom application architectures.
              </p>
            </div>

            {/* Card 3 */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 22 }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgb(69 60 55 / 0.15)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
                <CheckCircle2 size={20} />
              </div>
              <h3 style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>3. Idea Validator & Testing</h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55, margin: 0 }}>
                Preliminary viability scoring paired with concrete validation experiments, suggested thresholds, and founder discovery actions.
              </p>
            </div>

            {/* Card 4 */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 22 }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgb(69 60 55 / 0.15)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
                <TrendingUp size={20} />
              </div>
              <h3 style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>4. Market Research</h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55, margin: 0 }}>
                Competitor positioning, target customer segments, and clear identification of research gaps requiring direct inquiry.
              </p>
            </div>

            {/* Card 5 */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 22 }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgb(69 60 55 / 0.15)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
                <Calendar size={20} />
              </div>
              <h3 style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>5. Execution Roadmap</h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55, margin: 0 }}>
                Chronological Gantt view, 30/60/90 day milestone counts, and task dependency sequencing derived from planned dates.
              </p>
            </div>
          </div>
        </div>

        {/* Group 2: Supporting Capabilities */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: 0.6 }}>
              Supporting Capabilities
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))', gap: 14 }}>
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <ListTodo size={16} color="var(--primary-text)" />
                <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Task Management</h4>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.45, margin: 0 }}>
                Task codes, status tracking, effort estimation, and role assignments.
              </p>
            </div>

            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <Layers size={16} color="var(--primary-text)" />
                <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Version History</h4>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.45, margin: 0 }}>
                Structured revision snapshots with restore safety and change auditing.
              </p>
            </div>

            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <Bot size={16} color="var(--primary-text)" />
                <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Planning Copilot</h4>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.45, margin: 0 }}>
                Contextual conversation tool for evaluating assumptions and drafting details.
              </p>
            </div>

            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <FileSpreadsheet size={16} color="var(--primary-text)" />
                <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Dossier & Exports</h4>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.45, margin: 0 }}>
                Executive PDF dossiers and vector diagrams for stakeholder reviews.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Practical Workflow Section */}
      <section id="workflow" style={{ padding: '60px clamp(16px, 4vw, 32px) 80px clamp(16px, 4vw, 32px)', maxWidth: 1040, margin: '0 auto', width: '100%', borderTop: '1px solid var(--border-color)' }}>
        <div style={{ textAlign: 'center', marginBottom: 44 }}>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-main)', letterSpacing: -0.5, marginBottom: 12 }}>
            A Practical Planning Workflow
          </h2>
          <p style={{ fontSize: 15, color: 'var(--text-muted)', maxWidth: 580, margin: '0 auto' }}>
            A structured path from initial concept to organized operational execution.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
          {[
            { step: '01', title: 'Define Venture', desc: 'Specify venture name, stage, customer segments, and available budget.' },
            { step: '02', title: 'Synthesize Model', desc: 'Build the 9-block canvas covering value propositions, channels, and unit economics.' },
            { step: '03', title: 'Test Assumptions', desc: 'Identify critical assumptions and set up falsifiable customer interviews or trials.' },
            { step: '04', title: 'Select Tools', desc: 'Pick pragmatic operational tools or software architecture appropriate for your stage.' },
            { step: '05', title: 'Organize Execution', desc: 'Schedule tasks, track milestone progress, save versions, and export project dossiers.' }
          ].map((item) => (
            <div key={item.step} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--primary)', marginBottom: 8 }}>STEP {item.step}</div>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>{item.title}</h3>
              <p style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        marginTop: 'auto',
        borderTop: '1px solid var(--border-color)',
        padding: '36px clamp(16px, 4vw, 40px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 16,
        fontSize: 13,
        color: 'var(--text-muted)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Layers size={18} color="var(--primary-text)" />
          <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>Venture Atlas</span>
          <span>— Business Planning & Validation Workspace</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12 }}>
          <span>Terms & Privacy available in workspace settings</span>
          <span>© 2026 Venture Atlas. All rights reserved.</span>
        </div>
      </footer>

      {/* Authentication Modal */}
      {authModalOpen && (
        <div className="modal-overlay" onClick={closeAuthModal}>
          <div
            ref={modalCardRef}
            className="modal-card"
            style={{ maxWidth: 460 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: 'var(--bg-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-main)'
                }}>
                  <Layers size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0 }}>{isLoginTab ? 'Sign In to Workspace' : 'Create Free Account'}</h3>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                    {isLoginTab ? 'Access your business plans and roadmaps' : 'Start planning and validating your venture'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={closeAuthModal}
                className="modal-close-btn"
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            {/* Tab switch */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', background: 'var(--bg-subtle)' }}>
              <button
                type="button"
                onClick={() => { setIsLoginTab(true); setErrorMsg(null); }}
                style={{
                  flex: 1,
                  padding: '12px',
                  border: 'none',
                  background: isLoginTab ? 'var(--bg-card)' : 'transparent',
                  borderBottom: `2px solid ${isLoginTab ? 'var(--primary)' : 'transparent'}`,
                  fontWeight: isLoginTab ? 700 : 500,
                  color: isLoginTab ? 'var(--primary)' : 'var(--text-muted)',
                  fontSize: 13,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => { setIsLoginTab(false); setErrorMsg(null); }}
                style={{
                  flex: 1,
                  padding: '12px',
                  border: 'none',
                  background: !isLoginTab ? 'var(--bg-card)' : 'transparent',
                  borderBottom: `2px solid ${!isLoginTab ? 'var(--primary)' : 'transparent'}`,
                  fontWeight: !isLoginTab ? 700 : 500,
                  color: !isLoginTab ? 'var(--primary)' : 'var(--text-muted)',
                  fontSize: 13,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                Register
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {errorMsg && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: 12,
                    background: 'var(--bg-subtle)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--danger-text)',
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: 500
                  }}>
                    <AlertCircle size={16} style={{ flexShrink: 0 }} />
                    <span>{errorMsg}</span>
                  </div>
                )}

                {!isLoginTab && (
                  <div className="form-group">
                    <label className="form-label" htmlFor="register-username">Username</label>
                    <input
                      id="register-username"
                      type="text"
                      className="form-input"
                      placeholder="e.g. founder_alice"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      autoComplete="username"
                      required
                    />
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label" htmlFor="auth-email">
                    {isLoginTab ? 'Email or Username' : 'Email Address'}
                  </label>
                  <input
                    id="auth-email"
                    type={isLoginTab ? 'text' : 'email'}
                    className="form-input"
                    placeholder={isLoginTab ? 'Enter your email or username' : 'name@venture.com'}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete={isLoginTab ? 'username' : 'email'}
                    required
                  />
                </div>

                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label className="form-label" htmlFor="auth-password">Password</label>
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-muted)',
                        fontSize: 12,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4
                      }}
                    >
                      {showPassword ? <><EyeOff size={13} /> Hide</> : <><Eye size={13} /> Show</>}
                    </button>
                  </div>
                  <input
                    id="auth-password"
                    type={showPassword ? 'text' : 'password'}
                    className="form-input"
                    placeholder={isLoginTab ? 'Enter your password' : 'At least 8 characters with letter & number'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={isLoginTab ? 'current-password' : 'new-password'}
                    required
                  />
                </div>

                {!isLoginTab && (
                  <>
                    <div className="form-group">
                      <label className="form-label" htmlFor="auth-confirm-password">Confirm Password</label>
                      <input
                        id="auth-confirm-password"
                        type={showPassword ? 'text' : 'password'}
                        className="form-input"
                        placeholder="Re-enter password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        autoComplete="new-password"
                        required
                      />
                    </div>

                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 4 }}>
                      <input
                        type="checkbox"
                        id="terms"
                        checked={termsAccepted}
                        onChange={(e) => setTermsAccepted(e.target.checked)}
                        style={{ marginTop: 3, accentColor: 'var(--primary)', cursor: 'pointer' }}
                        required
                      />
                      <label htmlFor="terms" style={{ fontSize: 12, color: 'var(--text-muted)', cursor: 'pointer', lineHeight: 1.4 }}>
                        I agree to the Terms of Service and acknowledge the Privacy Policy.
                      </label>
                    </div>
                  </>
                )}
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  onClick={() => setAuthModalOpen(false)}
                  className="btn-secondary"
                  disabled={isLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <><Loader2 size={16} className="animate-spin" /> Authenticating...</>
                  ) : (
                    isLoginTab ? 'Sign In' : 'Create Account'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
