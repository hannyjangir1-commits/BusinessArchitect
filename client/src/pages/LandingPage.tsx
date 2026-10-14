import React, { useState } from 'react';
import { Layers, Sparkles, Compass, Cpu, Calendar, ArrowRight, AlertCircle, Loader2 } from 'lucide-react';
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

  return (
    <div style={{ minHeight: '100vh', background: '#0d121f', color: '#ffffff', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navbar */}
      <nav style={{ height: 72, borderBottom: '1px solid #1e293b', padding: '0 40px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Layers size={22} color="#fff" />
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: -0.2 }}>AI Business Architect</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#818cf8', letterSpacing: 0.8 }}>ENTERPRISE BLUEPRINT</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <button
            onClick={() => { setIsLoginTab(true); setAuthModalOpen(true); }}
            style={{ background: 'transparent', border: '1px solid #334155', color: '#cbd5e1', padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
          >
            Log In
          </button>
          <button
            onClick={() => { setIsLoginTab(false); setAuthModalOpen(true); }}
            className="btn-primary"
            style={{ padding: '8px 18px' }}
          >
            Get Started Free
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{ padding: '80px 40px 60px 40px', textAlign: 'center', maxWidth: 960, margin: '0 auto' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 14px', borderRadius: 9999, background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', fontSize: 12, fontWeight: 700, marginBottom: 24, border: '1px solid rgba(99, 102, 241, 0.3)' }}>
          <Sparkles size={14} /> Powered by Google Gemini AI & Supabase PostgreSQL
        </div>

        <h1 style={{ fontSize: 46, fontWeight: 800, lineHeight: 1.15, letterSpacing: -1, marginBottom: 20 }}>
          Transform Your Venture Idea into an <span style={{ background: 'linear-gradient(90deg, #818cf8, #c084fc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Enterprise-Grade Blueprint</span>
        </h1>

        <p style={{ fontSize: 17, color: '#94a3b8', lineHeight: 1.6, maxWidth: 720, margin: '0 auto 36px auto' }}>
          AI Business Architect synthesizes 9-block Business Model Canvases with radial vector infographics, stage-aware technology stacks, empirical idea validation, and Gantt-driven execution roadmaps.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
          <button
            onClick={() => { setIsLoginTab(false); setAuthModalOpen(true); }}
            className="btn-primary"
            style={{ fontSize: 15, padding: '12px 28px', borderRadius: 10 }}
          >
            Create Your Business Blueprint <ArrowRight size={18} />
          </button>
          <button
            onClick={() => { setIsLoginTab(true); setAuthModalOpen(true); }}
            style={{ background: '#1e293b', color: '#ffffff', border: '1px solid #334155', padding: '12px 24px', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
          >
            Sign In to Existing Project
          </button>
        </div>
      </section>

      {/* Feature Cards Grid */}
      <section style={{ padding: '20px 40px 80px 40px', maxWidth: 1140, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
        <div style={{ background: '#151c2e', border: '1px solid #1e293b', borderRadius: 14, padding: 24 }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
            <Compass size={22} />
          </div>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Radial Business Model Canvas</h3>
          <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>
            Code-generated vector radial infographic connecting Alexander Osterwalder's 9 core blocks directly around your venture core.
          </p>
        </div>

        <div style={{ background: '#151c2e', border: '1px solid #1e293b', borderRadius: 14, padding: 24 }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
            <Cpu size={22} />
          </div>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Stage-Aware Tech Stacks</h3>
          <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>
            Architectural recommendations that respect your existing technologies for launched & growth ventures, evaluating compatibility and migration risk.
          </p>
        </div>

        <div style={{ background: '#151c2e', border: '1px solid #1e293b', borderRadius: 14, padding: 24 }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
            <Calendar size={22} />
          </div>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Gantt Execution Roadmap</h3>
          <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>
            Interactive SVG timeline with 5 delivery phases, dependency tracking, milestone progress bars, and synchronized task management.
          </p>
        </div>
      </section>

      {/* Authentication Modal */}
      {authModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 440, background: '#ffffff', color: '#0f172a' }}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Layers size={20} color="#6366f1" />
                <h3>{isLoginTab ? 'Sign In' : 'Create Free Account'}</h3>
              </div>
              <button onClick={() => setAuthModalOpen(false)} className="modal-close-btn">✕</button>
            </div>

            {/* Tab switch */}
            <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0' }}>
              <button
                type="button"
                onClick={() => { setIsLoginTab(true); setErrorMsg(null); }}
                style={{
                  flex: 1,
                  padding: '11px',
                  border: 'none',
                  background: isLoginTab ? '#ffffff' : '#f8fafc',
                  borderBottom: `2px solid ${isLoginTab ? '#6366f1' : 'transparent'}`,
                  fontWeight: isLoginTab ? 700 : 500,
                  color: isLoginTab ? '#6366f1' : '#64748b',
                  fontSize: 13,
                  cursor: 'pointer'
                }}
              >
                Log In
              </button>
              <button
                type="button"
                onClick={() => { setIsLoginTab(false); setErrorMsg(null); }}
                style={{
                  flex: 1,
                  padding: '11px',
                  border: 'none',
                  background: !isLoginTab ? '#ffffff' : '#f8fafc',
                  borderBottom: `2px solid ${!isLoginTab ? '#6366f1' : 'transparent'}`,
                  fontWeight: !isLoginTab ? 700 : 500,
                  color: !isLoginTab ? '#6366f1' : '#64748b',
                  fontSize: 13,
                  cursor: 'pointer'
                }}
              >
                Register
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {errorMsg && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10, background: '#fee2e2', color: '#b91c1c', borderRadius: 8, fontSize: 13 }}>
                    <AlertCircle size={16} />
                    <span>{errorMsg}</span>
                  </div>
                )}

                {!isLoginTab && (
                  <div className="form-group">
                    <label className="form-label">Username</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. founder_alice"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                    />
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">{isLoginTab ? 'Email or Username' : 'Email Address'}</label>
                  <input
                    type={isLoginTab ? 'text' : 'email'}
                    className="form-input"
                    placeholder={isLoginTab ? 'Enter your email or username' : 'name@venture.com'}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Password</label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder="At least 8 characters with letter and number"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>

                {!isLoginTab && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Confirm Password</label>
                      <input
                        type="password"
                        className="form-input"
                        placeholder="Re-enter password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        required
                      />
                    </div>

                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 4 }}>
                      <input
                        type="checkbox"
                        id="terms"
                        checked={termsAccepted}
                        onChange={(e) => setTermsAccepted(e.target.checked)}
                        style={{ marginTop: 3 }}
                        required
                      />
                      <label htmlFor="terms" style={{ fontSize: 12, color: '#475569' }}>
                        I agree to the Terms of Service and acknowledge the Privacy Policy.
                      </label>
                    </div>
                  </>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setAuthModalOpen(false)} className="btn-secondary" disabled={isLoading}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isLoading}>
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
