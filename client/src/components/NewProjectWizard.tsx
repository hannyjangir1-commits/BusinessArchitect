import React, { useState, useEffect, useRef } from 'react';
import { BusinessStage } from '../types';
import { Sparkles, ArrowRight, ArrowLeft, Check, Layers, AlertCircle, Loader2, X } from 'lucide-react';
import { buildNewProjectPayload } from '../utils/projectPayload';
import { saveDraft, getDraft, clearDraft } from '../services/draftStorage';
import { Dialog } from './common/Dialog';

interface Props {
  onProjectCreated: (project: any) => Promise<void>;
  onCancel: () => void;
  userScope?: string;
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

export const NewProjectWizard: React.FC<Props> = ({ onProjectCreated, onCancel, userScope }) => {
  const initialDraft = userScope ? getDraft<any>(userScope, 'wizard') : null;

  const [currentStep, setCurrentStep] = useState<number>(initialDraft?.currentStep || 1);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState(initialDraft?.name || '');
  const [stage, setStage] = useState<BusinessStage>(initialDraft?.stage || 'Idea');
  const [industry, setIndustry] = useState(initialDraft?.industry || '');
  const [description, setDescription] = useState(initialDraft?.description || '');
  const [targetCustomers, setTargetCustomers] = useState(initialDraft?.targetCustomers || '');
  const [goals, setGoals] = useState(initialDraft?.goals || '');
  const [budget, setBudget] = useState(initialDraft?.budget || '');
  const [existingStack, setExistingStack] = useState<Record<string, string[]>>(initialDraft?.existingStack || {});
  const [customTechInput, setCustomTechInput] = useState('');
  const [customCategory, setCustomCategory] = useState('Backend');

  const nameInputRef = useRef<HTMLInputElement | null>(null);

  // Save draft on edit (scoped to user)
  useEffect(() => {
    if (userScope && (name || description || targetCustomers || goals || budget || Object.keys(existingStack).length > 0)) {
      saveDraft(userScope, 'wizard', {
        currentStep,
        name,
        stage,
        industry,
        description,
        targetCustomers,
        goals,
        budget,
        existingStack
      });
    }
  }, [userScope, currentStep, name, stage, industry, description, targetCustomers, goals, budget, existingStack]);

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
        nameInputRef.current?.focus();
        return;
      }
    }
    setCurrentStep(prev => prev + 1);
  };

  const handleCreate = async () => {
    setErrorMsg(null);
    if (!name.trim()) {
      setErrorMsg('Project name is required.');
      setCurrentStep(1);
      setTimeout(() => nameInputRef.current?.focus(), 50);
      return;
    }

    setIsSubmitting(true);
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

      await onProjectCreated(payload);
      if (userScope) clearDraft(userScope, 'wizard');
    } catch (err: any) {
      setErrorMsg(err.message || 'Could not create project. Please review your details and try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      isOpen={true}
      onClose={onCancel}
      dismissible={!isSubmitting}
      showCloseButton={false}
      ariaLabelledBy="wizard-title"
      maxWidth={740}
    >
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 480 }}>
        {/* Wizard Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--bg-subtle)', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Layers size={18} />
            </div>
            <div>
              <h3 id="wizard-title" style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Create project
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Three simple steps to configure your business workspace
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close project setup"
            className="modal-close-btn"
            disabled={isSubmitting}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: isSubmitting ? 'not-allowed' : 'pointer', padding: 4 }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Step Progress Pills */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, marginBottom: 16 }}>
          {[
            { num: 1, title: 'Basics & Stage' },
            { num: 2, title: stage === 'Idea' ? 'Goals & Runway' : 'Tools & Architecture' },
            { num: 3, title: 'Review & Create' }
          ].map((s) => {
            const isDone = currentStep > s.num;
            const isCurrent = currentStep === s.num;

            return (
              <div key={s.num} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: isCurrent || isDone ? 'var(--primary-text)' : 'var(--border-color)',
                    color: isCurrent || isDone ? 'var(--bg-card)' : 'var(--text-main)',
                    fontSize: 11,
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  {isDone ? <Check size={13} /> : s.num}
                </div>
                <span style={{ fontSize: 12.5, fontWeight: isCurrent ? 700 : 500, color: 'var(--text-main)' }}>
                  {s.title}
                </span>
              </div>
            );
          })}
        </div>

        {/* Wizard Body */}
        <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
          {errorMsg && (
            <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10, background: 'var(--bg-subtle)', color: 'var(--danger-text)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 13, marginBottom: 14 }}>
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* STEP 1: Basic Venture Details & Stage */}
          {currentStep === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="form-group">
                <label htmlFor="wizard-venture-name" className="form-label">Business / Project Name *</label>
                <input
                  id="wizard-venture-name"
                  ref={nameInputRef}
                  type="text"
                  className="form-input"
                  placeholder="e.g. Riverside Bike Works or CircuitCloud"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label id="wizard-stage-label" className="form-label">Business Stage *</label>
                <div
                  role="radiogroup"
                  aria-labelledby="wizard-stage-label"
                  style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}
                >
                  {[
                    { id: 'Idea', label: 'Idea', desc: 'Validate customer problem, value proposition, and initial concept' },
                    { id: 'MVP', label: 'MVP', desc: 'Build or improve the initial offering and validate real workflows' },
                    { id: 'Post-launch', label: 'Post-launch', desc: 'Operate a live business, learn from customers, and improve reliability' },
                    { id: 'Growth', label: 'Growth', desc: 'Scale a proven business model, operations, and customer reach' }
                  ].map((st) => (
                    <label
                      key={st.id}
                      role="radio"
                      aria-checked={stage === st.id}
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        border: `2px solid ${stage === st.id ? 'var(--primary)' : 'var(--border-color)'}`,
                        background: stage === st.id ? 'rgb(69 60 55 / 0.1)' : 'var(--bg-card)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        gap: 6
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-main)' }}>
                          {st.label}
                        </span>
                        <input
                          type="radio"
                          name="wizard-business-stage"
                          value={st.id}
                          checked={stage === st.id}
                          onChange={() => setStage(st.id as BusinessStage)}
                          style={{ accentColor: 'var(--primary)' }}
                        />
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.35 }}>
                        {st.desc}
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label htmlFor="wizard-industry" className="form-label">Industry / Sector</label>
                  <input
                    id="wizard-industry"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Local Services, Retail, Healthcare, or SaaS"
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="wizard-target-customers" className="form-label">Target Customers</label>
                  <input
                    id="wizard-target-customers"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Local bicycle commuters, Homeowners, or Engineering leads"
                    value={targetCustomers}
                    onChange={(e) => setTargetCustomers(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="wizard-description" className="form-label">Business Description</label>
                <textarea
                  id="wizard-description"
                  className="form-textarea"
                  rows={3}
                  placeholder="Describe your core offering, how customers find you, and what needs you address..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* STEP 2: Stage-aware discovery */}
          {currentStep === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="form-group">
                <label htmlFor="wizard-budget" className="form-label">
                  {stage === 'Idea' ? 'Initial Build / Startup Budget' : 'Available Budget or Monthly Runway'}
                </label>
                <input
                  id="wizard-budget"
                  type="text"
                  className="form-input"
                  placeholder="e.g. $5,000, 10,000 EUR, Bootstrapped, or $5k/mo runway"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                />
                <p style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4 }}>
                  Enter any currency or funding status. Distinguish upfront capital from recurring runway.
                </p>
              </div>

              <div className="form-group">
                <label htmlFor="wizard-goals" className="form-label">Primary Business Goals & Milestones</label>
                <textarea
                  id="wizard-goals"
                  className="form-textarea"
                  rows={3}
                  placeholder="e.g. First 50 paying customers, open 2nd repair bay, or validate willingness to pay..."
                  value={goals}
                  onChange={(e) => setGoals(e.target.value)}
                />
              </div>

              {stage !== 'Idea' && (
                <>
                  <div>
                    <h4 style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', margin: '8px 0 2px 0' }}>
                      Existing Tools & Technology Stack (Optional)
                    </h4>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
                      Select tools or systems currently in use. For non-software businesses, this can include spreadsheets or messaging.
                    </p>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 260, overflowY: 'auto', paddingRight: 4 }}>
                    {Object.entries(STACK_CATEGORIES).map(([cat, techs]) => (
                      <div key={cat} style={{ background: 'var(--bg-subtle)', padding: 10, borderRadius: 8, border: '1px solid var(--border-color)' }}>
                        <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--text-main)', marginBottom: 6, textTransform: 'uppercase' }}>
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
                                  borderRadius: 16,
                                  border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--border-color)'}`,
                                  background: isSelected ? 'var(--primary)' : 'var(--bg-card)',
                                  color: isSelected ? 'var(--paper)' : 'var(--text-main)',
                                  cursor: 'pointer'
                                }}
                              >
                                {tech}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 4 }}>
                    <select
                      className="form-select"
                      value={customCategory}
                      onChange={(e) => setCustomCategory(e.target.value)}
                      style={{ maxWidth: 160, fontSize: 12 }}
                    >
                      {Object.keys(STACK_CATEGORIES).map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Add custom tool (e.g. WhatsApp, Google Sheets)..."
                      value={customTechInput}
                      onChange={(e) => setCustomTechInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomTech(); } }}
                      style={{ flex: 1, fontSize: 12 }}
                    />
                    <button type="button" onClick={addCustomTech} className="btn-secondary" style={{ fontSize: 12 }}>
                      Add Tool
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* STEP 3: Review & Project Confirmation */}
          {currentStep === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 10, padding: 16 }}>
                <h4 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)', margin: '0 0 12px 0' }}>
                  Review project
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', rowGap: 8, fontSize: 13 }}>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Business Name:</span>
                  <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>{name}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Stage:</span>
                  <span><span className="stage-badge-purple">{stage}</span></span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Industry:</span>
                  <span style={{ color: 'var(--text-main)' }}>{industry || 'Not specified'}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Target Customers:</span>
                  <span style={{ color: 'var(--text-main)' }}>{targetCustomers || 'Not specified'}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Description:</span>
                  <span style={{ color: 'var(--text-main)' }}>{description || 'Not specified'}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Budget / Runway:</span>
                  <span style={{ color: 'var(--text-main)' }}>{budget || 'Not specified'}</span>

                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Goals:</span>
                  <span style={{ color: 'var(--text-main)' }}>{goals || 'Not specified'}</span>

                  {stage !== 'Idea' && Object.keys(existingStack).length > 0 && (
                    <>
                      <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Existing Tools:</span>
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

              <div style={{ padding: 12, background: 'rgb(69 60 55 / 0.1)', borderRadius: 8, border: '1px solid rgb(69 60 55 / 0.25)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <Sparkles size={18} color="var(--primary-text)" />
                <span style={{ fontSize: 12.5, color: 'var(--primary)' }}>
                  Create the project first, then generate each planning module inside your workspace. Your settings will be preserved across all sections.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Wizard Footer */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 18, borderTop: '1px solid var(--border-color)', paddingTop: 14 }}>
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
                  Creating project...
                </>
              ) : (
                <>
                  <Sparkles size={15} />
                  Create project
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </Dialog>
  );
};
