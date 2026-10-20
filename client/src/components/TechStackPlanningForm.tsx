import React, { useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { TechStackPlanningInputs } from '../types';

interface Props {
  initialValues?: Partial<TechStackPlanningInputs>;
  isGenerating: boolean;
  isDisabled: boolean;
  progress?: { stageText: string; progressPercent: number } | null;
  onSubmit: (inputs: TechStackPlanningInputs) => Promise<void>;
  onCancel?: () => void;
}

const split = (value: string) => value.split(',').map((item) => item.trim()).filter(Boolean);

export const TechStackPlanningForm: React.FC<Props> = ({ initialValues, isGenerating, isDisabled, progress, onSubmit, onCancel }) => {
  const [solutionType, setSolutionType] = useState(initialValues?.solution_type || '');
  const [languages, setLanguages] = useState((initialValues?.preferred_languages || []).join(', '));
  const [frameworks, setFrameworks] = useState((initialValues?.preferred_frameworks || []).join(', '));
  const [platforms, setPlatforms] = useState((initialValues?.target_platforms || []).join(', '));
  const [currentStack, setCurrentStack] = useState(initialValues?.current_stack || '');
  const [deployment, setDeployment] = useState(initialValues?.deployment_preference || '');
  const [database, setDatabase] = useState(initialValues?.database_preference || '');
  const [scale, setScale] = useState(initialValues?.expected_scale || '');
  const [dataSensitivity, setDataSensitivity] = useState(initialValues?.data_sensitivity || '');
  const [integrations, setIntegrations] = useState((initialValues?.required_integrations || []).join(', '));
  const [budget, setBudget] = useState(initialValues?.budget_constraint || '');
  const [experience, setExperience] = useState(initialValues?.team_experience || '');
  const [mustUse, setMustUse] = useState((initialValues?.must_use || []).join(', '));
  const [avoid, setAvoid] = useState((initialValues?.avoid || []).join(', '));
  const [constraints, setConstraints] = useState(initialValues?.constraints || '');
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    await onSubmit({ solution_type: solutionType, preferred_languages: split(languages), preferred_frameworks: split(frameworks), current_stack: currentStack, target_platforms: split(platforms), deployment_preference: deployment, database_preference: database, expected_scale: scale, data_sensitivity: dataSensitivity, compliance_requirements: [], required_integrations: split(integrations), budget_constraint: budget, team_experience: experience, must_use: split(mustUse), avoid: split(avoid), constraints });
  };
  const field = (label: string, value: string, setValue: (value: string) => void, placeholder: string) => (
    <label style={{ display: 'grid', gap: 6, fontSize: 13, color: 'var(--text-main)' }}><span>{label}</span><input value={value} onChange={(event) => setValue(event.target.value)} placeholder={placeholder} /></label>
  );
  return <form className="card" onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
    <div><h3 style={{ margin: 0 }}>Technology preferences</h3><p style={{ color: 'var(--text-muted)', margin: '6px 0 0', fontSize: 13 }}>Answer what you know. Leave a preference blank and the planner will choose an appropriate option for this project.</p></div>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 14 }}>
      <label style={{ display: 'grid', gap: 6, fontSize: 13 }}>Solution type<select value={solutionType} onChange={(event) => setSolutionType(event.target.value)}><option value="">Choose a product type</option><option>Web application</option><option>Mobile application</option><option>Desktop application</option><option>Hardware or embedded system</option><option>Internal business tool</option><option>Hybrid product</option></select></label>
      {field('Preferred languages', languages, setLanguages, 'TypeScript, Python (comma separated)')}
      {field('Preferred frameworks and tools', frameworks, setFrameworks, 'React, FastAPI, Docker')}
      {field('Target platforms', platforms, setPlatforms, 'Web, iOS, Android, desktop')}
      <label style={{ display: 'grid', gap: 6, fontSize: 13 }}>Deployment<select value={deployment} onChange={(event) => setDeployment(event.target.value)}><option value="">Choose deployment</option><option>Managed cloud</option><option>Self-hosted</option><option>Offline or local</option><option>Hybrid</option></select></label>
      <label style={{ display: 'grid', gap: 6, fontSize: 13 }}>Database<select value={database} onChange={(event) => setDatabase(event.target.value)}><option value="">Choose database preference</option><option>Relational</option><option>Document</option><option>Time-series</option><option>Existing database</option></select></label>
      <label style={{ display: 'grid', gap: 6, fontSize: 13 }}>Expected scale<select value={scale} onChange={(event) => setScale(event.target.value)}><option value="">Choose expected scale</option><option>Prototype or pilot</option><option>Small production</option><option>Enterprise production</option><option>High traffic or global</option></select></label>
      <label style={{ display: 'grid', gap: 6, fontSize: 13 }}>Data sensitivity<select value={dataSensitivity} onChange={(event) => setDataSensitivity(event.target.value)}><option value="">Choose data sensitivity</option><option>Public data</option><option>Standard business data</option><option>Confidential data</option><option>Regulated or personal data</option></select></label>
      {field('Required integrations', integrations, setIntegrations, 'Payments, email, ERP…')}
      {field('Budget or cost limit', budget, setBudget, 'Optional budget guidance')}
    </div>
    {field('Current stack or existing services', currentStack, setCurrentStack, 'What must be kept or evaluated?')}
    {field('Team experience', experience, setExperience, 'Skills, roles, or staffing constraints')}
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>{field('Must use', mustUse, setMustUse, 'Comma separated')}{field('Avoid', avoid, setAvoid, 'Comma separated')}</div>
    {field('Other constraints', constraints, setConstraints, 'Security, region, licensing, deadlines…')}
    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}><button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button><button className="btn-primary" disabled={isDisabled || isGenerating}>{isGenerating ? <><Loader2 size={15} className="animate-spin" /> {progress?.stageText || 'Generating…'}</> : <><Sparkles size={15} /> Generate technology stack</>}</button></div>
  </form>;
};
