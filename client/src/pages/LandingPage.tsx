import React, { useState } from 'react';
import {
  Layers, Compass, Cpu, Calendar, CheckCircle2, TrendingUp, ListTodo,
  FileSpreadsheet, ArrowRight, AlertCircle, Loader2, ShieldCheck,
  Eye, EyeOff, Bot
} from 'lucide-react';
import { api } from '../services/api';
import { SessionData } from '../types';

interface Props {
  onAuthenticated: (session: SessionData) => void;
}

export const LandingPage: React.FC<Props> = ({ onAuthenticated }) => {
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [isLoginTab, setIsLoginTab] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
      <div className="landing-page" style={{ minHeight: '100vh', background: 'var(--bg-workspace)', color: 'var(--text-main)', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navbar */}
      <header style={{
        height: 72,
        borderBottom: '1px solid var(--border-color)',
        padding: '0 36px',
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
            <Layers size={22} color="var(--bg-card)" />
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: -0.2, color: 'var(--text-main)' }}>Venture Atlas</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: 0.8 }}>ENTERPRISE BLUEPRINT</div>
          </div>
        </div>

        {/* Center Nav Links */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 28 }} className="landing-desktop-nav">
          <button
            onClick={() => scrollToSection('features')}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer', transition: 'color 0.15s ease' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            Workspace Modules
          </button>
          <button
            onClick={() => scrollToSection('workflow')}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer', transition: 'color 0.15s ease' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            Planning Workflow
          </button>
          <button
            onClick={() => scrollToSection('architecture')}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer', transition: 'color 0.15s ease' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            Enterprise Architecture
          </button>
        </nav>

        {/* Right CTA */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => { setIsLoginTab(true); setErrorMsg(null); setAuthModalOpen(true); }}
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
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--text-main)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
          >
            Sign In
          </button>
          <button
            onClick={() => { setIsLoginTab(false); setErrorMsg(null); setAuthModalOpen(true); }}
            className="btn-primary"
            style={{ padding: '8px 18px', fontSize: 13 }}
          >
            Get Started
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section style={{ padding: '84px 32px 56px 32px', textAlign: 'center', maxWidth: 1040, margin: '0 auto', width: '100%' }}>
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
          marginBottom: 26,
          border: '1px solid rgb(69 60 55 / 0.25)',
          letterSpacing: 0.3
        }}>
          <ShieldCheck size={14} /> Structured Venture Architecture & Planning Workspace
        </div>

        <h1 style={{
          fontSize: 'clamp(32px, 5vw, 52px)',
          fontWeight: 800,
          lineHeight: 1.14,
          letterSpacing: -1,
          marginBottom: 22,
          color: 'var(--text-main)'
        }}>
          Turn your business idea into an{' '}
          <span style={{ color: 'var(--primary-text)' }}>
            actionable blueprint.
          </span>
        </h1>

        <p style={{
          fontSize: 'clamp(15px, 2vw, 18px)',
          color: 'var(--text-muted)',
          lineHeight: 1.6,
          maxWidth: 760,
          margin: '0 auto 38px auto'
        }}>
          Plan your business model, evaluate your technology choices, research your market, and organize execution in one structured workspace.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}>
          <button
            onClick={() => { setIsLoginTab(false); setErrorMsg(null); setAuthModalOpen(true); }}
            className="btn-primary"
            style={{ fontSize: 14.5, padding: '13px 28px', borderRadius: 10, boxShadow: '0 4px 16px rgb(69 60 55 / 0.4)' }}
          >
            Create Your Blueprint <ArrowRight size={17} />
          </button>
          <button
            onClick={() => scrollToSection('features')}
            style={{
              background: 'var(--bg-card)',
              color: 'var(--text-main)',
              border: '1px solid var(--border-color)',
              padding: '13px 24px',
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--primary-text)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-color)'; }}
          >
            Explore the Workspace
          </button>
        </div>
      </section>

      {/* Interactive Workspace Preview Showcase */}
      <section id="architecture" style={{ padding: '0 32px 70px 32px', maxWidth: 1160, margin: '0 auto', width: '100%' }}>
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: 16,
          padding: 24,
          boxShadow: '0 12px 30px -18px rgb(69 60 55 / 0.18)',
          overflow: 'hidden'
        }}>
          {/* Mock Workspace Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: 16, marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--danger-text)' }} />
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--bg-subtle)' }} />
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--bg-subtle)' }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)', marginLeft: 8 }}>
                Venture Workspace — CloudScale Platform (Growth Stage)
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 9999, background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
                9 Core Modules
              </span>
              <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 9999, background: 'rgb(69 60 55 / 0.2)', color: 'var(--text-muted)', fontWeight: 600 }}>
                Active Version: V2
              </span>
            </div>
          </div>

          {/* Mock Multi-Module Dashboard Preview */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
            {/* Box 1: BMC */}
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Compass size={17} color="var(--primary-text)" />
                <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Business Model Canvas</h4>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 12px 0' }}>
                Alexander Osterwalder's 9-block grid with value proposition, channels, revenue streams, and cost drivers.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>Value: B2B API Suite</div>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>Revenue: Usage Tiers</div>
              </div>
            </div>

            {/* Box 2: Tech Stack */}
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Cpu size={17} color="var(--text-muted)" />
                <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Technology Architecture</h4>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 12px 0' }}>
                Multi-tier architecture recommendations evaluating scalability, database suitability, and migration risk.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>API: FastAPI Async</div>
                <div style={{ background: 'var(--bg-card)', padding: '6px 8px', borderRadius: 6, color: 'var(--text-muted)' }}>DB: PostgreSQL + Redis</div>
              </div>
            </div>

            {/* Box 3: Gantt Timeline */}
            <div style={{ background: 'var(--sidebar-bg)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Calendar size={17} color="var(--primary-text)" />
                <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>Execution Roadmap</h4>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5, margin: '0 0 12px 0' }}>
                5-phase chronological Gantt view with milestone tracking, task dependencies, and sprint deliverables.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
                  <span>Phase 1: Architecture Review</span>
                  <span style={{ color: 'var(--primary-text)', fontWeight: 600 }}>100%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
                  <span>Phase 2: Core Platform Services</span>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>65%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Sections: 9 Coherent Workspace Capabilities */}
      <section id="features" style={{ padding: '60px 32px 80px 32px', maxWidth: 1160, margin: '0 auto', width: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-main)', letterSpacing: -0.5, marginBottom: 12 }}>
            Complete Venture Architecture Workspace
          </h2>
          <p style={{ fontSize: 15, color: 'var(--text-muted)', maxWidth: 640, margin: '0 auto' }}>
            Nine dedicated planning modules designed to take your venture from initial hypothesis to synchronized operational execution.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
          {/* Card 1 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.15)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <Compass size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>1. Business Model Canvas</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Alexander Osterwalder's canonical 9-block grid with radial vector diagram, structured block editing, and high-resolution SVG export.
            </p>
          </div>

          {/* Card 2 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.18)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <Cpu size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>2. Technology Architecture</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Stage-aware system patterns across frontend, backend, database, and cloud infrastructure, evaluating scalability and trade-offs.
            </p>
          </div>

          {/* Card 3 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.15)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <CheckCircle2 size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>3. Idea Validator</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Empirical hypothesis evaluation scoring customer demand, differentiation moat, defensibility, and strategic risk mitigation.
            </p>
          </div>

          {/* Card 4 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.15)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <TrendingUp size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>4. Market Research</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Competitive landscape mapping, target customer ICP personas, industry market dynamics, and defensible wedge strategies.
            </p>
          </div>

          {/* Card 5 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.15)', color: 'var(--danger-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <Calendar size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>5. Execution Roadmap</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Interactive Gantt timeline with five delivery phases, critical path dependency tracking, and milestone completion progress.
            </p>
          </div>

          {/* Card 6 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.2)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <ListTodo size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>6. Detailed Task Management</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Granular sprint task breakdowns with priority badges, delivery timelines, effort estimation, and status lifecycle tracking.
            </p>
          </div>

          {/* Card 7 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.18)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <Layers size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>7. Version History</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Immutable snapshot versioning with rollback safety and structured revision management across every section.
            </p>
          </div>

          {/* Card 8 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.2)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <Bot size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>8. Planning Copilot</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Planning Copilot guidance to refine strategic parameters, add milestones, or evaluate technical trade-offs.
            </p>
          </div>

          {/* Card 9 */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: 24 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgb(69 60 55 / 0.2)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
              <FileSpreadsheet size={22} />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: 'var(--text-main)' }}>9. Project Export</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, margin: 0 }}>
              Publication-ready executive PDF dossiers and vector SVG diagrams formatted for stakeholder presentations and investor review.
            </p>
          </div>
        </div>
      </section>

      {/* Workflow Section */}
      <section id="workflow" style={{ padding: '60px 32px 80px 32px', maxWidth: 1040, margin: '0 auto', width: '100%', borderTop: '1px solid var(--border-color)' }}>
        <div style={{ textAlign: 'center', marginBottom: 44 }}>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-main)', letterSpacing: -0.5, marginBottom: 12 }}>
            A Structured Planning Workflow
          </h2>
          <p style={{ fontSize: 15, color: 'var(--text-muted)', maxWidth: 580, margin: '0 auto' }}>
            Follow a proven path from concept articulation to synchronized engineering execution.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
          {[
            { step: '01', title: 'Define Project', desc: 'Specify venture name, stage, target audience, and primary objectives.' },
            { step: '02', title: 'Build Blueprint', desc: 'Synthesize the 9-block canvas, architecture tiers, and execution schedule.' },
            { step: '03', title: 'Review Options', desc: 'Inspect feasibility scores, tech trade-offs, and competitor intelligence.' },
            { step: '04', title: 'Organize Execution', desc: 'Decompose phases into tasks, establish dependencies, and assign priorities.' },
            { step: '05', title: 'Track & Export', desc: 'Save immutable snapshots, manage versions, and export executive PDF reports.' }
          ].map((item) => (
            <div key={item.step} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-muted)', marginBottom: 8 }}>STEP {item.step}</div>
              <h4 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6 }}>{item.title}</h4>
              <p style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        marginTop: 'auto',
        borderTop: '1px solid var(--border-color)',
        padding: '36px 40px',
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
          <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Venture Atlas</span>
          <span>— Enterprise Blueprint Workspace</span>
        </div>
        <div>
          <span>© 2026 Venture Atlas. All rights reserved.</span>
        </div>
      </footer>

      {/* Authentication Modal */}
      {authModalOpen && (
        <div className="modal-overlay" onClick={() => setAuthModalOpen(false)}>
          <div
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
                    {isLoginTab ? 'Access your venture blueprints and roadmaps' : 'Start architecting your enterprise blueprint'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setAuthModalOpen(false)}
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
