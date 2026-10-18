import React, { useMemo, useState } from 'react';
import { Calendar, Loader2, Sparkles, X } from 'lucide-react';
import { BusinessStage, RoadmapChecklistItem, RoadmapChecklistStatus, RoadmapPlanningInputs, TeamMemberInput } from '../types';

interface Props {
  stage: BusinessStage;
  initialValues?: Partial<RoadmapPlanningInputs>;
  isGenerating: boolean;
  isDisabled: boolean;
  progress?: { stageText: string; progressPercent: number } | null;
  onSubmit: (inputs: RoadmapPlanningInputs) => Promise<void>;
  onCancel?: () => void;
}

const CHECKLISTS: Record<Exclude<BusinessStage, 'Idea / MVP'>, string[]> = {
  Idea: [
    'Problem and target customer are clearly defined',
    'Customer interviews or problem validation are complete',
    'Value proposition and differentiation are defined',
    'Initial product scope and success measures are defined',
    'Team capacity and initial budget are understood'
  ],
  MVP: [
    'MVP scope and acceptance criteria are defined',
    'Core product workflows have been built',
    'Core workflows have been tested with intended users',
    'Security, privacy, and data handling basics are reviewed',
    'Pilot or release readiness criteria are defined'
  ],
  'Post-launch': [
    'Product is live and customers can use it',
    'Customer feedback and product usage are being collected',
    'Reliability and performance have a baseline',
    'Support and incident response responsibilities are defined',
    'Near-term product or revenue outcome is selected'
  ],
  Growth: [
    'Current product architecture and bottlenecks are assessed',
    'Reliability, performance, and capacity targets are defined',
    'Operational ownership and incident coverage are assigned',
    'Unit economics and delivery capacity are understood',
    'A specific growth initiative and success metric are selected'
  ]
};

const STATUSES: RoadmapChecklistStatus[] = ['Not started', 'In progress', 'Completed', 'Not applicable'];

const localToday = () => {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
};

export const RoadmapPlanningForm: React.FC<Props> = ({
  stage,
  initialValues,
  isGenerating,
  isDisabled,
  progress,
  onSubmit,
  onCancel
}) => {
  const today = useMemo(() => localToday(), []);
  const currentStage = stage === 'Idea / MVP' ? 'MVP' : stage;
  const checklistLabels = CHECKLISTS[currentStage] || CHECKLISTS.MVP;
  const [checklist, setChecklist] = useState<RoadmapChecklistItem[]>(() => checklistLabels.map((item) => ({
    item,
    status: initialValues?.checklist?.find((answer) => answer.item === item)?.status || 'Not started'
  })));
  const [submitting, setSubmitting] = useState(false);

  const updateChecklist = (item: string, status: RoadmapChecklistStatus) => {
    setChecklist((prev) => prev.map((entry) => (entry.item === item ? { ...entry, status } : entry)));
  };

  const [startDate, setStartDate] = useState(() =>
    initialValues?.start_date && initialValues.start_date >= today ? initialValues.start_date : today
  );
  const [horizonWeeks, setHorizonWeeks] = useState(initialValues?.horizon_weeks || 12);
  const [completedWork, setCompletedWork] = useState(initialValues?.completed_work || '');
  const [inProgressWork, setInProgressWork] = useState(initialValues?.in_progress_work || '');
  const [teamCapacity, setTeamCapacity] = useState(initialValues?.team_capacity || '');
  const [constraints, setConstraints] = useState(initialValues?.constraints || '');
  const [targetOutcome, setTargetOutcome] = useState(initialValues?.target_outcome || '');
  const [customItemsText, setCustomItemsText] = useState((initialValues?.custom_items || []).join('\n'));
  const [isSoloDeveloper, setIsSoloDeveloper] = useState(initialValues?.is_solo_developer || false);
  const [teamMembers, setTeamMembers] = useState<TeamMemberInput[]>(initialValues?.team_members || []);
  const [newMemberName, setNewMemberName] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('');
  const [newMemberDept, setNewMemberDept] = useState('');

  const handleAddMember = () => {
    if (!newMemberName.trim()) return;
    setTeamMembers(prev => [
      ...prev,
      {
        name: newMemberName.trim(),
        roles: newMemberRole.split(',').map(r => r.trim()).filter(Boolean),
        skills: [newMemberRole.trim()],
        department: newMemberDept.trim() || 'Engineering',
        hours_per_week: 40
      }
    ]);
    setNewMemberName('');
    setNewMemberRole('');
    setNewMemberDept('');
  };

  const handleRemoveMember = (idx: number) => {
    setTeamMembers(prev => prev.filter((_, i) => i !== idx));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        start_date: startDate,
        horizon_weeks: Number(horizonWeeks),
        checklist,
        completed_work: completedWork.trim(),
        in_progress_work: inProgressWork.trim(),
        team_capacity: teamCapacity.trim(),
        constraints: constraints.trim(),
        target_outcome: targetOutcome.trim(),
        custom_items: customItemsText.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).slice(0, 20),
        is_solo_developer: isSoloDeveloper,
        team_members: isSoloDeveloper ? [{ name: 'Solo Developer', roles: ['Fullstack Engineer'], skills: ['Fullstack'], department: 'Engineering', hours_per_week: 40 }] : teamMembers
      });
    } finally {
      setSubmitting(false);
    }
  };

  const busy = submitting || isGenerating;

  return (
    <form onSubmit={submit} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h3 style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-main)' }}>Personalize your {currentStage} roadmap</h3>
          <p style={{ marginTop: 4, fontSize: 12.5, color: 'var(--text-muted)' }}>
            Mark what is already true for this project. Completed and irrelevant work will be left out of the plan.
          </p>
        </div>
        {onCancel && (
          <button type="button" onClick={onCancel} className="btn-secondary" disabled={busy} aria-label="Close roadmap planning questions">
            <X size={15} />
          </button>
        )}
      </div>

      <section>
        <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)', marginBottom: 9 }}>Where are you with these milestones?</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {checklist.map(({ item, status }) => (
            <label key={item} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '9px 11px', border: '1px solid var(--border-color)', borderRadius: 8, background: 'var(--bg-subtle)' }}>
              <span style={{ fontSize: 12.5, color: 'var(--text-main)' }}>{item}</span>
              <select
                className="form-select"
                value={status}
                disabled={busy}
                onChange={(event) => updateChecklist(item, event.target.value as RoadmapChecklistStatus)}
                style={{ width: 150, minWidth: 135, padding: '6px 8px', fontSize: 12 }}
                aria-label={`Status: ${item}`}
              >
                {STATUSES.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
          ))}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12 }}>
        <div className="form-group">
          <label className="form-label" htmlFor="roadmap-start-date">Start planning from</label>
          <input id="roadmap-start-date" className="form-input" type="date" min={today} value={startDate} disabled={busy} onChange={(event) => setStartDate(event.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="roadmap-horizon">Planning horizon (weeks)</label>
          <input id="roadmap-horizon" className="form-input" type="number" min={1} max={104} value={horizonWeeks} disabled={busy} onChange={(event) => setHorizonWeeks(Math.max(1, Math.min(104, Number(event.target.value) || 1)))} />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="roadmap-capacity">Team capacity summary</label>
          <input id="roadmap-capacity" className="form-input" type="text" maxLength={500} placeholder="e.g. 2 developers, part-time designer" value={teamCapacity} disabled={busy} onChange={(event) => setTeamCapacity(event.target.value)} />
        </div>
      </div>

      {/* Solo Developer Mode Toggle (ROAD-012) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: 'var(--bg-subtle)', borderRadius: 8, border: '1px solid var(--border-color)' }}>
        <input
          type="checkbox"
          id="roadmap-solo-dev"
          checked={isSoloDeveloper}
          onChange={(e) => setIsSoloDeveloper(e.target.checked)}
          disabled={busy}
          style={{ width: 16, height: 16, cursor: 'pointer' }}
        />
        <label htmlFor="roadmap-solo-dev" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-main)', cursor: 'pointer', margin: 0 }}>
          Solo Developer Mode (Single founder/engineer delivering entire scope)
        </label>
      </div>

      {/* Team Members & Roles Configuration (ROAD-015 to ROAD-019) */}
      {!isSoloDeveloper && (
        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 14 }}>
          <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)', margin: '0 0 8px 0' }}>
            Team Members, Skills & Roles (Optional)
          </h4>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px 0' }}>
            Tasks will be assigned strictly to these real team members based on their designated roles and skills.
          </p>

          {teamMembers.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
              {teamMembers.map((m, idx) => (
                <div key={idx} style={{ background: '#ffffff', border: '1px solid #d9ddcf', borderRadius: 6, padding: '6px 10px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>{m.name}</span>
                  <span style={{ color: '#6d855f' }}>({m.roles.join(', ') || 'General'})</span>
                  <span style={{ color: 'var(--text-muted)' }}>[{m.department || 'General'}]</span>
                  <button type="button" onClick={() => handleRemoveMember(idx)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: 2 }}>
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              type="text"
              placeholder="Member Name (e.g. Alex Chen)"
              value={newMemberName}
              onChange={(e) => setNewMemberName(e.target.value)}
              disabled={busy}
              style={{ flex: 1, minWidth: 150, padding: '6px 10px', fontSize: 12, borderRadius: 6, border: '1px solid var(--border-color)' }}
            />
            <input
              type="text"
              placeholder="Roles/Skills (e.g. Lead Architect, Backend)"
              value={newMemberRole}
              onChange={(e) => setNewMemberRole(e.target.value)}
              disabled={busy}
              style={{ flex: 1.2, minWidth: 180, padding: '6px 10px', fontSize: 12, borderRadius: 6, border: '1px solid var(--border-color)' }}
            />
            <input
              type="text"
              placeholder="Department (e.g. Engineering)"
              value={newMemberDept}
              onChange={(e) => setNewMemberDept(e.target.value)}
              disabled={busy}
              style={{ flex: 1, minWidth: 120, padding: '6px 10px', fontSize: 12, borderRadius: 6, border: '1px solid var(--border-color)' }}
            />
            <button
              type="button"
              onClick={handleAddMember}
              disabled={busy || !newMemberName.trim()}
              className="btn-secondary"
              style={{ fontSize: 12, padding: '6px 12px' }}
            >
              + Add Member
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
        <div className="form-group">
          <label className="form-label" htmlFor="roadmap-completed-work">What have you already completed?</label>
          <textarea id="roadmap-completed-work" className="form-textarea" rows={2} maxLength={2000} placeholder="List completed work that is not covered by the milestone statuses above" value={completedWork} disabled={busy} onChange={(event) => setCompletedWork(event.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="roadmap-in-progress-work">What are you working on now?</label>
          <textarea id="roadmap-in-progress-work" className="form-textarea" rows={2} maxLength={2000} placeholder="List active work and what remains to finish it" value={inProgressWork} disabled={busy} onChange={(event) => setInProgressWork(event.target.value)} />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="roadmap-outcome">What result should this plan achieve?</label>
        <input id="roadmap-outcome" className="form-input" type="text" maxLength={1000} placeholder="e.g. Validate the PCB design workflow with 5 pilot customers" value={targetOutcome} disabled={busy} onChange={(event) => setTargetOutcome(event.target.value)} />
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="roadmap-constraints">Constraints, blockers, or deadlines</label>
        <textarea id="roadmap-constraints" className="form-textarea" rows={2} maxLength={2000} placeholder="Mention dependencies, budget limits, regulatory dates, or other blockers" value={constraints} disabled={busy} onChange={(event) => setConstraints(event.target.value)} />
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="roadmap-custom-items">What else should be included?</label>
        <textarea id="roadmap-custom-items" className="form-textarea" rows={3} maxLength={4000} placeholder={'Add one task or milestone per line, for example:\nComplete a pilot with three PCB design partners\nPrepare the manufacturing handoff checklist'} value={customItemsText} disabled={busy} onChange={(event) => setCustomItemsText(event.target.value)} />
        <span style={{ display: 'block', marginTop: 5, fontSize: 11, color: 'var(--text-muted)' }}>Up to 20 custom items. The planner will merge duplicates into matching tasks.</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 10, borderTop: '1px solid var(--border-color)', paddingTop: 14 }}>
        <button type="submit" className="btn-primary" disabled={busy || isDisabled || !startDate}>
          {busy ? <><Loader2 size={15} className="animate-spin" /> {progress ? `${progress.stageText} (${progress.progressPercent}%)` : 'Generating roadmap...'}</> : <><Calendar size={15} /> <Sparkles size={14} /> Generate tailored roadmap</>}
        </button>
      </div>
    </form>
  );
};
