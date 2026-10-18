import React, { useState } from 'react';
import { BusinessStage } from '../types';
import { Sparkles, ArrowRight, ArrowLeft, Check, Layers, AlertCircle, Loader2 } from 'lucide-react';
import { buildNewProjectPayload } from '../utils/projectPayload';

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
  const [stage, setStage] = useState<BusinessStage>('Idea');
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
      const payload = buildNewProjectPayload({
        name,
        stage,
        industry,
        description,
        targetCustomers,
        goals,
        budget,
        existingStack
      });

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
            <div style={{ width: 32, height: 32, borderRadius: 8, background: '#e8ede2', color: '#6d855f', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Layers size={18} />
            </div>
            <div>
              <h3>Architect New Venture Blueprint</h3>
              <p style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>Three-step stage-aware business blueprint initialization</p>
            </div>
          </div>
          <button onClick={onCancel} className="modal-close-btn">✕</button>
        </div>

        {/* Step Progress Pills */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 24px', background: '#f7f6ef', borderBottom: '1px solid #dfe2d6' }}>
          {[
            { num: 1, title: 'Venture & Stage' },
            { num: 2, title: stage === 'Idea' ? 'Discovery & Goals' : 'Existing Stack & Architecture' },
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
                    background: isCurrent ? '#6d855f' : isDone ? '#10b981' : '#dfe2d6',
                    color: isCurrent || isDone ? '#ffffff' : '#687164',
                    fontSize: 12,
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  {isDone ? <Check size={14} /> : s.num}
                </div>
                <span style={{ fontSize: 13, fontWeight: isCurrent ? 700 : 500, color: isCurrent ? '#626b5f' : '#687164' }}>
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
                  placeholder="e.g. PCB Designer or CircuitCloud"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Venture Stage *</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                  {[
                    { id: 'Idea', label: 'Idea', desc: 'Validate the problem, customers, value proposition, and initial concept' },
                    { id: 'MVP', label: 'MVP', desc: 'Build or improve the minimum viable product and validate core workflows' },
                    { id: 'Post-launch', label: 'Post-launch', desc: 'Operate a live product, learn from customers, and improve reliability' },
                    { id: 'Growth', label: 'Growth', desc: 'Scale a proven product, operations, and customer acquisition' }
                  ].map((st) => (
                    <div
                      key={st.id}
                      onClick={() => setStage(st.id as BusinessStage)}
                      style={{
                        padding: 14,
                        borderRadius: 10,
                        border: `2px solid ${stage === st.id ? '#6d855f' : '#dfe2d6'}`,
                        background: stage === st.id ? '#f0f1e9' : '#ffffff',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ fontWeight: 700, fontSize: 13.5, color: stage === st.id ? '#6d855f' : '#626b5f' }}>
                        {st.label}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
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
              <div className="form-group">
                <label className="form-label">{stage === 'Idea' ? 'Initial Build Budget' : 'Available Budget / Runway'}</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. $25,000 - $50,000, monthly runway, or Bootstrapped"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Primary Business Goals & Milestones</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="e.g. Validate retention, reach $10k MRR, reduce support time, or expand to two new regions..."
                  value={goals}
                  onChange={(e) => setGoals(e.target.value)}
                />
              </div>

              {stage !== 'Idea' && (
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
                      <div key={cat} style={{ background: '#f7f6ef', padding: 12, borderRadius: 8, border: '1px solid #dfe2d6' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-main)', marginBottom: 8, textTransform: 'uppercase' }}>
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
                                  border: `1px solid ${isSelected ? '#6d855f' : '#d9ddcf'}`,
                                  background: isSelected ? '#6d855f' : '#ffffff',
                                  color: isSelected ? '#ffffff' : '#687164',
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

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Budget / Runway:</span>
                  <span style={{ color: 'var(--text-main)' }}>{budget || 'Not specified'}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Goals:</span>
                  <span style={{ color: 'var(--text-main)' }}>{goals || 'Not specified'}</span>

                  {stage !== 'Idea' && (
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

              <div style={{ padding: 12, background: 'rgba(109, 133, 95, 0.1)', borderRadius: 8, border: '1px solid rgba(109, 133, 95, 0.25)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <Sparkles size={18} color="#6d855f" />
                <span style={{ fontSize: 12.5, color: 'var(--primary)' }}>
                  Upon submission, Venture Atlas will synthesize the 9-block Business Model Canvas, Technology Architecture recommendations, and Execution Roadmap with interactive Gantt milestones.
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
