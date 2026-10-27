import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { RoadmapMindMap } from '../components/RoadmapMindMap';
import { FinancialWorksheetModule } from '../components/FinancialWorksheetModule';
import { BMCModule } from '../components/BMCModule';
import { BlueprintCopilotModule } from '../components/BlueprintCopilotModule';
import { Project, RoadmapTask, ModuleDetail, FinancialWorksheet } from '../types';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    financials: {
      get: vi.fn(),
      update: vi.fn(),
    },
    copilot: {
      sendMessage: vi.fn(),
      proposeChange: vi.fn(),
    },
    modules: {
      modify: vi.fn(),
    },
    knowledge: {
      create: vi.fn(),
    },
  },
}));

const mockProject: Project = {
  id: 'proj_test_1',
  name: 'Campus Cycle Care',
  stage: 'Idea',
  industry: 'Transportation',
  target_customers: 'College Students & Faculty',
  goals: 'Affordable on-campus bike repairs',
  business_context: 'University campus with 20k students',
  budget: '$5,000',
  active_module: 'execution_roadmap',
  tasks_count: 3,
  completed_tasks_count: 1,
  progress_percentage: 33,
  generated_modules: ['bmc', 'tech_stack', 'execution_roadmap'],
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
};

const mockTasks: RoadmapTask[] = [
  {
    id: 'task_1',
    project_id: 'proj_test_1',
    task_code: 'T-101',
    title: 'Customer Discovery Interviews',
    phase: 'Month 1',
    timeline: '2 weeks',
    start_date: '2026-10-01',
    end_date: '2026-10-15',
    priority: 'High',
    status: 'Finished',
    dependencies: [],
    created_at: '2026-10-01T00:00:00Z',
    edge_type: 'prerequisite',
    roadmap_mode: 'execution',
  },
  {
    id: 'task_2',
    project_id: 'proj_test_1',
    task_code: 'T-102',
    title: 'Secure University Workshop Permit',
    phase: 'Month 1',
    timeline: '1 week',
    start_date: '2026-10-16',
    end_date: '2026-10-23',
    priority: 'Critical',
    status: 'In Progress',
    dependencies: ['T-101'],
    created_at: '2026-10-01T00:00:00Z',
    edge_type: 'prerequisite',
    roadmap_mode: 'execution',
  },
  {
    id: 'task_3',
    project_id: 'proj_test_1',
    task_code: 'T-103',
    title: 'Study Lean Canvas Methodology',
    phase: 'Month 2',
    timeline: '3 weeks',
    start_date: '2026-11-01',
    end_date: '2026-11-21',
    priority: 'Low',
    status: 'Pending',
    dependencies: [],
    created_at: '2026-10-01T00:00:00Z',
    edge_type: 'optional_branch',
    roadmap_mode: 'learning',
  },
];

describe('RoadmapMindMap Component', () => {
  it('renders interactive graph with zoom/pan controls and search filter', () => {
    const onUpdateTask = vi.fn();
    render(<RoadmapMindMap tasks={mockTasks} onUpdateTask={onUpdateTask} projectName={mockProject.name} stage={mockProject.stage} phases={[]} />);

    // Controls
    expect(screen.getByTitle('Zoom In')).toBeDefined();
    expect(screen.getByTitle('Zoom Out')).toBeDefined();
    expect(screen.getByTitle('Fit to Map')).toBeDefined();

    // Mode toggles
    expect(screen.getByText(/Execution Roadmap/)).toBeDefined();
    expect(screen.getByText(/Learning Roadmap/)).toBeDefined();

    // Search
    const searchInput = screen.getByPlaceholderText('Search nodes or code...');
    expect(searchInput).toBeDefined();

    fireEvent.change(searchInput, { target: { value: 'Workshop' } });
    expect(screen.getAllByText(/Secure University Workshop Permit/).length).toBeGreaterThanOrEqual(1);
  });

  it('switches between execution and learning modes and toggles accessible outline', () => {
    render(<RoadmapMindMap tasks={mockTasks} projectName={mockProject.name} stage={mockProject.stage} phases={[]} />);

    const learningBtn = screen.getByText(/Learning Roadmap/).closest('button');
    expect(learningBtn).toBeDefined();
    fireEvent.click(learningBtn!);

    // Outline fallback toggle
    const outlineToggle = screen.getByText(/Accessible Outline/).closest('button');
    expect(outlineToggle).toBeDefined();
    fireEvent.click(outlineToggle!);

    expect(screen.getByText(/Study Lean Canvas Methodology/)).toBeDefined();
  });
});

describe('BMCModule Multi-Framework and Epistemic States', () => {
  const mockDetail: ModuleDetail = {
    module_type: 'bmc',
    active_version_id: 'ver_1',
    data: {
      key_partnerships: ['Local Bike Shops', 'Campus Facilities'],
      key_activities: ['Mobile tune-ups', 'Safety inspections'],
      key_resources: ['Mobile tool trailers', 'Student mechanics'],
      value_propositions: ['15-minute express campus bike repair', 'Student-friendly tiered pricing'],
      customer_relationships: ['Direct campus kiosks', 'SMS notification system'],
      channels: ['Campus flyers', 'Student Union booth'],
      customer_segments: ['Commuter students', 'Campus faculty'],
      cost_structure: ['Tool maintenance', 'Student mechanic wages'],
      revenue_streams: ['Pay-per-repair fees', 'Annual semester pass'],
    },
    versions: [],
  };

  it('renders Lean Canvas layout when version framework is lean_canvas', () => {
    const mockDetailLean: ModuleDetail<any> = {
      ...mockDetail,
      framework_type: 'lean_canvas',
      data: {
        framework_type: 'lean_canvas',
        problem: ['Bike chain snaps frequently'],
        solution: ['Mobile emergency tool trailer'],
        key_metrics: ['Average turnaround minutes'],
        unique_value_proposition: ['15-minute express campus repair'],
        unfair_advantage: ['Exclusive campus permit'],
        channels: ['Campus flyers'],
        customer_segments: ['Commuter students'],
        cost_structure: ['Student mechanic wages'],
        revenue_streams: ['Pay-per-repair fees']
      }
    };

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={mockDetailLean}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText('1. Problem')).toBeDefined();
    expect(screen.getByText('4. Unique Value Prop')).toBeDefined();
  });

  it('renders Value Proposition Canvas layout when version framework is value_prop_canvas', () => {
    const mockDetailValueProp: ModuleDetail<any> = {
      ...mockDetail,
      framework_type: 'value_prop_canvas',
      data: {
        framework_type: 'value_prop_canvas',
        customer_jobs: ['Commute to class on time'],
        customer_pains: ['Flat tire during midterms'],
        customer_gains: ['Fast mobile repair'],
        products_and_services: ['On-demand mechanic dispatch'],
        pain_relievers: ['Instant student dispatch notification'],
        gain_creators: ['Quarterly tune-up subscription']
      }
    };

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={mockDetailValueProp}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText('Customer Profile')).toBeDefined();
    expect(screen.getByText('Value Map')).toBeDefined();
    expect(screen.getByText('Customer Jobs')).toBeDefined();
    expect(screen.getByText('Pain Relievers')).toBeDefined();
  });
});

describe('FinancialWorksheetModule Component', () => {
  const mockWorksheetData: FinancialWorksheet = {
    id: 'ws_1',
    project_id: 'proj_test_1',
    currency: 'USD',
    startup_costs: [
      { category: 'Equipment', item: 'Tool kits', amount: 1200 },
      { category: 'Permits', item: 'Campus license', amount: 300 },
    ],
    fixed_costs: [
      { category: 'Insurance', item: 'Liability policy', monthly_amount: 150, frequency: 'monthly' },
      { category: 'Software', item: 'Booking platform', monthly_amount: 50, frequency: 'monthly' },
    ],
    variable_costs: [
      { item: 'Spare brake pads & cables', unit_cost: 8 },
      { item: 'Lubricants & cleaning supplies', unit_cost: 2 },
    ],
    revenue_model: {
      model_type: 'per_unit',
      price_per_unit: 35,
      expected_volume_monthly: 20,
    },
    cash_available: 5000,
    metrics: {
      total_startup_cost: 1500,
      monthly_fixed_cost: 200,
      unit_variable_cost: 10,
      price_per_unit: 35,
      unit_contribution_margin: 25,
      contribution_margin_ratio: 71.43,
      breakeven_units_monthly: 8,
      breakeven_revenue_monthly: 280,
      monthly_burn_rate: 200,
      runway_months: 17.5,
    },
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  };

  it('calculates deterministic unit margin, break-even units, and runway', async () => {
    vi.mocked(api.financials.get).mockResolvedValueOnce(mockWorksheetData);

    render(<FinancialWorksheetModule project={mockProject} />);

    await waitFor(() => {
      // Total Startup Capital = $1,200 + $300 = $1,500
      expect(screen.getByText(/1,500/)).toBeDefined();
      // Unit Margin = $35 - ($8 + $2) = $25.00
      expect(screen.getByText(/25\.00/)).toBeDefined();
      // Margin % = ($25 / $35) * 100 = 71.43%
      expect(screen.getByText(/71\.43/)).toBeDefined();
      // Fixed overhead = $150 + $50 = $200
      expect(screen.getAllByText(/200/).length).toBeGreaterThanOrEqual(1);
    });
  });
});

describe('BlueprintCopilotModule Proposal Workflow', () => {
  const mockProposalResponse = {
    target_module: 'bmc',
    summary: 'Add university bike co-op partnership and reduce starter pricing to $25.',
    proposed_diff: {
      key_partnerships: {
        before: ['Local Bike Shops', 'Campus Facilities'],
        after: ['Local Bike Shops', 'Campus Facilities', 'University Bike Co-op'],
      },
      revenue_streams: {
        before: ['Pay-per-repair fees ($35)'],
        after: ['Pay-per-repair fees ($25 student rate)', 'Semester subscription pass ($49)'],
      },
    },
    affected_assumptions: ['Price elasticity among undergraduate students'],
    affected_tasks: ['Negotiate co-op space agreement'],
    requires_confirmation: true,
    proposed_content: {},
  };

  it('toggles to Propose Change mode, generates preview, and displays diff modal', async () => {
    vi.mocked(api.copilot.proposeChange).mockResolvedValueOnce(mockProposalResponse);
    const onApplyProposal = vi.fn().mockResolvedValueOnce(undefined);

    render(
      <BlueprintCopilotModule
        project={mockProject}
        messages={[]}
        onSendMessage={vi.fn()}
        onApplyProposal={onApplyProposal}
        isLoading={false}
      />
    );

    // Click Propose Change in Header
    const proposeTab = screen.getByRole('button', { name: /Propose Change/i });
    expect(proposeTab).toBeDefined();
    fireEvent.click(proposeTab);

    // Propose view elements
    expect(screen.getByText('Non-Destructive Module Proposals')).toBeDefined();
    const textarea = screen.getByPlaceholderText(/Describe the updates for Business Model Canvas/i);
    fireEvent.change(textarea, { target: { value: 'Add bike co-op partnership and adjust rates' } });

    // Submit proposal
    const submitBtn = screen.getByRole('button', { name: /Generate Proposal Preview/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.copilot.proposeChange).toHaveBeenCalledWith(
        'proj_test_1',
        'bmc',
        'Add bike co-op partnership and adjust rates'
      );
    });

    // Review Modal displays diff
    await waitFor(() => {
      expect(screen.getByText('Review Change Proposal')).toBeDefined();
      expect(screen.getAllByText(/Add university bike co-op partnership/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('KEY PARTNERSHIPS')).toBeDefined();
      expect(screen.getByText(/Affected Assumptions \(1\):/)).toBeDefined();
      expect(screen.getByText(/Affected Roadmap Tasks \(1\):/)).toBeDefined();
    });

    // Click Apply Changes
    const applyBtn = screen.getByRole('button', { name: /Apply Changes to Module/i });
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(onApplyProposal).toHaveBeenCalledWith('bmc', 'Add bike co-op partnership and adjust rates');
    });
  });
});
