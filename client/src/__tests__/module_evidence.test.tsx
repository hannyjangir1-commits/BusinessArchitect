import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { IdeaValidatorModule } from '../components/IdeaValidatorModule';
import { RadialBMCInfographic, buildCompleteBmcSvg } from '../components/RadialBMCInfographic';
import { TechStackModule } from '../components/TechStackModule';
import { ModuleLifecycleActions } from '../components/ModuleLifecycleActions';
import { Sidebar } from '../components/Sidebar';
import { BMCData, IdeaValidatorData, ModuleDetail, Project, TechStackData } from '../types';

const project: Project = {
  id: 'project-1',
  name: 'CircuitCraft',
  stage: 'Idea',
  industry: 'EDA Software',
  active_module: 'bmc',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  generated_modules: [],
  created_at: '2026-10-18T00:00:00Z',
  updated_at: '2026-10-18T00:00:00Z',
};

const bmcData: BMCData = {
  tagline: 'Collaborative PCB design',
  customer_segments: ['Electronics students'],
  value_propositions: ['A complete long value proposition that must remain present in the downloadable SVG.'],
  channels: ['Engineering communities'],
  customer_relationships: ['Design support'],
  revenue_streams: ['Team subscriptions'],
  key_resources: ['EDA expertise'],
  key_activities: ['Validate design workflows'],
  key_partnerships: ['Fabrication partners'],
  cost_structure: ['Cloud hosting'],
  actionable_guidance: { value_propositions: 'Interview PCB designers and validate this promise with a prototype.' },
  assumptions: ['Design teams will pay to reduce review time.'],
};

describe('BMC mind map and complete SVG export', () => {
  it('opens full item and actionable guidance when a mind map card is clicked', () => {
    render(<RadialBMCInfographic projectName="CircuitCraft" stage="Idea" data={bmcData} />);

    fireEvent.click(screen.getByRole('button', { name: /Inspect Value Propositions/ }));

    expect(screen.getByText(bmcData.value_propositions[0])).toBeTruthy();
    expect(screen.getByText(bmcData.actionable_guidance!.value_propositions)).toBeTruthy();
  });

  it('includes every block point, guidance, and assumptions in the exported SVG appendix', () => {
    const sourceSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    sourceSvg.setAttribute('viewBox', '0 0 1100 750');

    const exported = buildCompleteBmcSvg(sourceSvg, 'CircuitCraft', 'Idea', bmcData);
    const svgText = exported.textContent || '';

    expect(svgText).toContain(bmcData.value_propositions[0]);
    expect(svgText).toContain(bmcData.actionable_guidance!.value_propositions);
    expect(svgText).toContain(bmcData.assumptions![0]);
    expect(Number(exported.getAttribute('height'))).toBeGreaterThan(750);
  });
});

describe('Idea Validator evidence display', () => {
  it('preserves a valid zero viability score instead of replacing it with the default', () => {
    const data: IdeaValidatorData = {
      overall_viability_score: 0,
      score_factors: { problem_clarity: 0, market_demand: 0, feasibility: 0, defensibility: 0, budget_alignment: 0 },
      problem_clarity: 'The problem has not been defined.',
      customer_fit: 'No customers identified.',
      value_proposition: 'Not established.',
      market_assumptions: [],
      differentiation: 'Not assessed.',
      feasibility: 'Not feasible from the available information.',
      budget_feasibility: 'No budget evidence.',
      risks: [],
      validation_experiments: [],
      suggested_next_actions: [],
      evidence_note: 'Preliminary offline heuristic; live market evidence is unavailable.',
      source_references: [],
    };
    const detail: ModuleDetail<IdeaValidatorData> = {
      module_type: 'idea_validator',
      active_version_name: 'V1',
      versions: [],
      data,
    };

    render(
      <IdeaValidatorModule
        project={project}
        moduleDetail={detail}
        onGenerate={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText('0')).toBeTruthy();
    expect(screen.getByText('problem clarity')).toBeTruthy();
    expect(screen.getByText(data.evidence_note!)).toBeTruthy();
  });
});

describe('Technology stack compatibility review', () => {
  it('shows existing components and labels offline compatibility as unverified', () => {
    const techData: TechStackData = {
      summary: 'Provisional architecture for an early EDA product.',
      architecture_pattern: 'Modular monolith',
      recommendations: [{
        technology: 'React',
        category: 'Frontend',
        purpose: 'User interface',
        suitability: 'Fits the current scope',
      }],
      existing_stack_evaluation: {
        evaluation_status: 'not_verified_offline',
        existing_components: ['frontend: React', 'backend: FastAPI'],
        compatible_elements: [],
        incompatible_or_redundant: [],
        migration_trade_offs: 'Offline mode cannot verify compatibility or migration risk.',
      },
      assumptions: [],
    };
    const detail: ModuleDetail<TechStackData> = {
      module_type: 'tech_stack',
      active_version_name: 'V1',
      active_version_number: 1,
      versions: [],
      data: techData,
    };

    render(
      <TechStackModule
        project={project}
        moduleDetail={detail}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText('Existing Stack Compatibility Review')).toBeTruthy();
    expect(screen.getByText(/could not be verified in offline mode/i)).toBeTruthy();
    expect(screen.getByText(/frontend: React, backend: FastAPI/i)).toBeTruthy();
  });
});

describe('module lifecycle actions', () => {
  it('starts a fresh module generation without requiring an AI instruction', () => {
    const onCreateNew = vi.fn().mockResolvedValue(undefined);
    render(
      <ModuleLifecycleActions
        moduleTitle="Technology Stack"
        createLabel="Create New Stack"
        onCreateNew={onCreateNew}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Create New Stack' }));

    expect(onCreateNew).toHaveBeenCalledOnce();
  });

  it('requires confirmation before deleting the full module', () => {
    const onDeleteModule = vi.fn().mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(
      <ModuleLifecycleActions
        moduleTitle="Technology Stack"
        onDeleteModule={onDeleteModule}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Delete Technology Stack' }));

    expect(confirm).toHaveBeenCalledOnce();
    expect(onDeleteModule).toHaveBeenCalledOnce();
    confirm.mockRestore();
  });

  it('shows one delete control for a single saved version and removes that module', () => {
    const onDeleteModule = vi.fn().mockResolvedValue(undefined);
    const onDeleteVersion = vi.fn().mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(
      <ModuleLifecycleActions
        moduleTitle="Technology Stack"
        onDeleteModule={onDeleteModule}
        onDeleteVersion={onDeleteVersion}
        versions={[
          { id: 'version-1', version_number: 1, version_name: 'Only stack', is_active: true, created_at: '2026-10-18' }
        ]}
      />
    );

    expect(screen.getAllByRole('button', { name: /delete/i })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Delete Technology Stack' }));

    expect(onDeleteModule).toHaveBeenCalledOnce();
    expect(onDeleteVersion).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it('deletes the current version when the module has multiple versions', () => {
    const onDeleteModule = vi.fn().mockResolvedValue(undefined);
    const onDeleteVersion = vi.fn().mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(
      <ModuleLifecycleActions
        moduleTitle="Technology Stack"
        onDeleteModule={onDeleteModule}
        onDeleteVersion={onDeleteVersion}
        versions={[
          { id: 'version-1', version_number: 1, version_name: 'Original stack', is_active: false, created_at: '2026-10-17' },
          { id: 'version-2', version_number: 2, version_name: 'Current stack', is_active: true, created_at: '2026-10-18' }
        ]}
      />
    );

    expect(screen.getAllByRole('button', { name: /delete/i })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Delete current version of Technology Stack' }));

    expect(onDeleteVersion).toHaveBeenCalledWith('version-2');
    expect(onDeleteModule).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it('does not delete when the user cancels confirmation', () => {
    const onDeleteModule = vi.fn().mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(
      <ModuleLifecycleActions
        moduleTitle="Market Research"
        onDeleteModule={onDeleteModule}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Delete Market Research' }));

    expect(onDeleteModule).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});

describe('sidebar module status cues', () => {
  it('announces whether a module is open, generated, or not generated', () => {
    render(
      <Sidebar
        currentProject={project}
        activeModule="bmc"
        onSelectModule={vi.fn()}
        onBackToDashboard={vi.fn()}
        onCreateNewProject={vi.fn()}
        onExportFullPdf={vi.fn()}
        moduleVersionBadges={{
          bmc: { version: 'V1', isGenerated: true },
          tech_stack: { version: 'V1', isGenerated: true },
          idea_validator: { version: 'V1', isGenerated: false }
        }}
      />
    );

    expect(screen.getByRole('button', { name: 'Business Model Canvas, Currently open' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Technology Stack, Generated' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Idea Validator, Not generated' })).toBeTruthy();
  });
});
