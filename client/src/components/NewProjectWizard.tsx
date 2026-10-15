import React, { useState } from 'react';
import { BusinessStage } from '../types';
import { Sparkles, ArrowRight, ArrowLeft, Check, Layers, AlertCircle, Loader2 } from 'lucide-react';

interface Props {
  onProjectCreated: (project: any) => void;
  onCancel: () => void;
}

const STACK_CATEGORIES: Record<string, string[]> = {
  Frontend: ['React', 'Next.js', 'Vue.js', 'Angular', 'Svelte', 'Vanilla JS/HTML'],
  Backend: ['FastAPI', 'Python', 'Node.js', 'Express', 'Django', 'Go', 'Java / Spring', 'Ruby on Rails'],
  Database: ['PostgreSQL', 'Supabase', 'MySQL', 'MongoDB', 'Redis', 'SQLite', 'DynamoDB'],
  'Cloud / Hosting': ['Render', 'AWS', 'Google Cloud', 'Microsoft Azure', 'Vercel', 'DigitalOcean'],
  'File Storage': ['AWS S3', 'Supabase Storage', 'Google Cloud Storage', 'Cloudflare R2'],
  Authentication: ['Server Sessions', 'Argon2id', 'JWT', 'OAuth 2.0', 'Supabase Auth', 'Auth0'],
  'DevOps & CI/CD': ['Docker', 'GitHub Actions', 'Kubernetes', 'Terraform', 'GitLab CI'],
  'Services & APIs': ['Stripe Payments', 'SendGrid Email', 'PostHog Analytics', 'Sentry Monitoring']
};

export const NewProjectWizard: React.FC<Props> = ({ onProjectCreated, onCancel }) => {
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState('');
  const [stage, setStage] = useState<BusinessStage>('Growth');
  const [industry, setIndustry] = useState('Enterprise SaaS');
  const [description, setDescription] = useState('');
  const [targetCustomers, setTargetCustomers] = useState('');
  const [goals, setGoals] = useState('');
  const [budget, setBudget] = useState('$50,000 - $100,000');
  const [existingStack, setExistingStack] = useState<Record<string, string[]>>({
    Frontend: ['React'],
    Backend: ['FastAPI', 'Python'],
    Database: ['PostgreSQL'],
    'Cloud / Hosting': ['Render'],
    Authentication: ['Server Sessions', 'Argon2id'],
    'DevOps & CI/CD': ['Docker']
  });
  const [customTechInput, setCustomTechInput] = useState('');
  const [customCategory, setCustomCategory] = useState('Backend');

  const toggleTech = (category: string, tech: string) => {
    setExistingStack(prev => {
      const currentList = prev[category] || [];
      const updated = currentList.includes(tech)
        ? currentList.filter(t => t !== tech)
        : [...currentList, tech];
      return { ...prev, [category]: updated };
    });
  };

  const addCustomTech = () => {
    if (!customTechInput.trim()) return;
    const tech = customTechInput.trim();
    setExistingStack(prev => {
      const currentList = prev[customCategory] || [];
      if (!currentList.includes(tech)) {
        return { ...prev, [customCategory]: [...currentList, tech] };
      }
      return prev;
    });
    setCustomTechInput('');
  };

  const handleNext = () => {
    setErrorMsg(null);
    if (currentStep === 1) {
      if (!name.trim()) {
        setErrorMsg('Please enter a project name.');
        return;
      }
      setCurrentStep(2);
    } else if (currentStep === 2) {
      setCurrentStep(3);
    }
  };

  const handleCreate = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const payload = {
        name: name.trim(),
        stage,
        industry: industry.trim(),
        description: description.trim(),
        target_customers: targetCustomers.trim(),
        goals: goals.trim(),
        budget: stage === 'Idea / MVP' ? budget : undefined,
        existing_stack: stage !== 'Idea / MVP' ? existingStack : {}
      };

      onProjectCreated(payload);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create project');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-card" style={{ maxWidth: 740, minHeight: 520 }}>
        {/* Wizard Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: '#ede9fe', color: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Layers size={18} />
            </div>
            <div>
              <h3>Architect New Venture Blueprint</h3>
              <p style={{ fontSize: 11.5, color: '#64748b' }}>Three-step stage-aware business blueprint initialization</p>
            </div>
          </div>
          <button onClick={onCancel} className="modal-close-btn">✕</button>
        </div>

        {/* Step Progress Pills */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 24px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
          {[
            { num: 1, title: 'Venture & Stage' },
            { num: 2, title: stage === 'Idea / MVP' ? 'Discovery & Goals' : 'Existing Stack & Architecture' },
            { num: 3, title: 'Review & Blueprint' }
          ].map((s) => {
            const isDone = currentStep > s.num;
            const isCurrent = currentStep === s.num;

            return (
              <div key={s.num} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: '50%',
                    background: isCurrent ? '#6366f1' : isDone ? '#10b981' : '#e2e8f0',
                    color: isCurrent || isDone ? '#ffffff' : '#64748b',
                    fontSize: 12,
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  {isDone ? <Check size={14} /> : s.num}
                </div>
                <span style={{ fontSize: 13, fontWeight: isCurrent ? 700 : 500, color: isCurrent ? '#0f172a' : '#64748b' }}>
                  {s.title}
                </span>
              </div>
            );
          })}
        </div>

        {/* Wizard Body */}
        <div className="modal-body" style={{ flex: 1, overflowY: 'auto' }}>
          {errorMsg && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10, background: '#fee2e2', color: '#b91c1c', borderRadius: 8, fontSize: 13 }}>
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* STEP 1: Basic Venture Details & Stage */}
          {currentStep === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Project / Venture Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. PCB Designer or CloudScale AI"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Venture Stage *</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                  {[
                    { id: 'Idea / MVP', label: 'Idea / MVP', desc: 'Pre-launch validation, concept design & greenfield architecture' },
                    { id: 'Post-launch', label: 'Post-launch', desc: 'Working software in market, initial traction, tech assessment' },
                    { id: 'Growth', label: 'Growth Stage', desc: 'Scaling operations, high reliability, architectural expansion' }
                  ].map((st) => (
                    <div
                      key={st.id}
                      onClick={() => setStage(st.id as BusinessStage)}
                      style={{
                        padding: 14,
                        borderRadius: 10,
                        border: `2px solid ${stage === st.id ? '#6366f1' : '#e2e8f0'}`,
                        background: stage === st.id ? '#f5f3ff' : '#ffffff',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ fontWeight: 700, fontSize: 13.5, color: stage === st.id ? '#6366f1' : '#0f172a' }}>
                        {st.label}
                      </div>
                      <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                        {st.desc}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div className="form-group">
                  <label className="form-label">Industry</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Hardware Engineering, FinTech, HealthTech"
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Target ICP / Customers</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Electrical Engineers, Mid-market CTOs"
                    value={targetCustomers}
                    onChange={(e) => setTargetCustomers(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Venture Description</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="Describe your core product value proposition and what pain points it addresses..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* STEP 2: Stage-aware discovery */}
          {currentStep === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {stage === 'Idea / MVP' ? (
                <>
                  <div className="form-group">
                    <label className="form-label">Initial Build Budget</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. $25,000 - $50,000 or Bootstrapped"
                      value={budget}
                      onChange={(e) => setBudget(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Primary Business Goals & Milestones</label>
                    <textarea
                      className="form-textarea"
                      rows={4}
                      placeholder="e.g. Build MVP in 3 months, validate with 20 design partners, reach $10k MRR..."
                      value={goals}
                      onChange={(e) => setGoals(e.target.value)}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)' }}>
                      Existing Technology Stack Selector
                    </h4>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                      Select the components currently powering your product. The planning engine will evaluate compatibility, scalability, and migration risks without forcing unnecessary rewrites.
                    </p>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 320, overflowY: 'auto', paddingRight: 4 }}>
                    {Object.entries(STACK_CATEGORIES).map(([cat, techs]) => (
                      <div key={cat} style={{ background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', marginBottom: 8, textTransform: 'uppercase' }}>
                          {cat}
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {techs.map((tech) => {
                            const isSelected = (existingStack[cat] || []).includes(tech);
                            return (
                              <button
                                key={tech}
                                type="button"
                                onClick={() => toggleTech(cat, tech)}
                                style={{
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  fontWeight: isSelected ? 700 : 500,
                                  borderRadius: 20,
                                  border: `1px solid ${isSelected ? '#6366f1' : '#cbd5e1'}`,
                                  background: isSelected ? '#6366f1' : '#ffffff',
                                  color: isSelected ? '#ffffff' : '#334155',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease'
                                }}
                              >
                                {tech} {isSelected && '✓'}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Add Custom Tech */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                    <select
                      className="form-select"
                      style={{ width: 150 }}
                      value={customCategory}
                      onChange={(e) => setCustomCategory(e.target.value)}
                    >
                      {Object.keys(STACK_CATEGORIES).map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <input
                      type="text"
                      className="form-input"
                      style={{ flex: 1 }}
                      placeholder="Add custom technology (e.g. Apache Kafka, Rust)..."
                      value={customTechInput}
                      onChange={(e) => setCustomTechInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomTech(); } }}
                    />
                    <button type="button" onClick={addCustomTech} className="btn-secondary">
                      + Add
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* STEP 3: Review & Blueprint Confirmation */}
          {currentStep === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 16 }}>
                <h4 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)', marginBottom: 12 }}>
                  Blueprint Generation Summary
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: '130px 1fr', rowGap: 8, fontSize: 13 }}>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Venture Name:</span>
                  <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>{name}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Stage:</span>
                  <span><span className="stage-badge-purple">{stage}</span></span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Industry:</span>
                  <span style={{ color: 'var(--text-main)' }}>{industry || 'Technology'}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Description:</span>
                  <span style={{ color: 'var(--text-main)' }}>{description || 'Not specified'}</span>

                  {stage !== 'Idea / MVP' && (
                    <>
                      <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Existing Stack:</span>
                      <div>
                        {Object.entries(existingStack).map(([c, list]) => list.length > 0 ? (
                          <div key={c} style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                            <b>{c}:</b> {list.join(', ')}
                          </div>
                        ) : null)}
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div style={{ padding: 12, background: 'rgba(99, 102, 241, 0.1)', borderRadius: 8, border: '1px solid rgba(99, 102, 241, 0.25)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <Sparkles size={18} color="#6366f1" />
                <span style={{ fontSize: 12.5, color: 'var(--primary)' }}>
                  Upon submission, Business Architect will synthesize the 9-block Business Model Canvas, Technology Architecture recommendations, and Execution Roadmap with interactive Gantt milestones.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Wizard Footer */}
        <div className="modal-footer">
          {currentStep > 1 && (
            <button
              type="button"
              onClick={() => setCurrentStep(currentStep - 1)}
              className="btn-secondary"
              disabled={isSubmitting}
            >
              <ArrowLeft size={14} /> Back
            </button>
          )}

          {currentStep < 3 ? (
            <button type="button" onClick={handleNext} className="btn-primary">
              Next Step <ArrowRight size={14} />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCreate}
              className="btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Architecting Blueprint...
                </>
              ) : (
                <>
                  <Sparkles size={15} />
                  Generate Enterprise Blueprint
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
