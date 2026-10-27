import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React from 'react';
import { BMCModule } from '../components/BMCModule';
import { Project, ModuleDetail, BMCData } from '../types';

const mockProject: Project = {
  id: 'proj-framework-1',
  name: 'CleanAir Tech',
  description: 'Industrial air scrubbing using bio-filters',
  stage: 'MVP',
  goals: 'Build prototype',
  budget: '$50,000',
  industry: 'CleanTech',
  target_customers: 'Industrial factories',
  active_module: 'bmc',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  generated_modules: ['bmc'],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z'
};

describe('Frameworks End-to-End Frontend Support', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('allows framework selection before first generation and passes framework_type', async () => {
    const handleGenerate = vi.fn().mockResolvedValue(undefined);

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={null}
        onGenerate={handleGenerate}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    // Initial empty state should show framework selector
    const selector = screen.getByLabelText('Framework selection') as HTMLSelectElement;
    expect(selector.value).toBe('standard_bmc');

    // Switch to Lean Canvas
    fireEvent.change(selector, { target: { value: 'lean_canvas' } });
    expect(selector.value).toBe('lean_canvas');

    // Button should reflect Lean Canvas
    const generateBtn = screen.getByRole('button', { name: /Generate Lean Canvas/i });
    fireEvent.click(generateBtn);

    expect(handleGenerate).toHaveBeenCalledWith({ framework_type: 'lean_canvas' });
  });

  it('renders real Lean Canvas fields without hardcoded generic placeholders', () => {
    const leanModuleDetail: ModuleDetail<any> = {
      module_type: 'bmc',
      framework_type: 'lean_canvas',
      active_version_id: 'ver-lean-1',
      active_version_name: 'V1 - Lean Canvas',
      active_version_number: 1,
      versions: [],
      data: {
        framework_type: 'lean_canvas',
        problem: ['Real problem: Factory filter replacement costs exceed $10k/month'],
        solution: ['Real solution: Bio-regenerative scrubbers with 3x lifespan'],
        key_metrics: ['Scrubber uptime %', 'Filter replacement cycle days'],
        unique_value_proposition: ['Zero-downtime industrial bio-scrubbers'],
        unfair_advantage: ['Proprietary bacterial enzyme patent #48291'],
        channels: ['Direct B2B plant engineering sales'],
        customer_segments: ['Mid-size chemical processing plants in Midwest'],
        cost_structure: ['Bio-culture incubator maintenance', 'Stainless steel reactor vessels'],
        revenue_streams: ['Hardware lease $2,500/mo', 'Bio-enzyme refill subscription']
      }
    };

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={leanModuleDetail}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    // Real content must appear
    expect(screen.getByText(/Factory filter replacement costs exceed \$10k\/month/i)).toBeTruthy();
    expect(screen.getByText(/Bio-regenerative scrubbers with 3x lifespan/i)).toBeTruthy();
    expect(screen.getByText(/Proprietary bacterial enzyme patent #48291/i)).toBeTruthy();

    // Fabricated fallback strings from old defect must NOT exist
    expect(screen.queryByText(/High service coordination friction/i)).toBeNull();
    expect(screen.queryByText(/Proprietary network density/i)).toBeNull();
  });

  it('renders real Value Proposition Canvas fields correctly', () => {
    const valuePropDetail: ModuleDetail<any> = {
      module_type: 'bmc',
      framework_type: 'value_prop_canvas',
      active_version_id: 'ver-vp-1',
      active_version_name: 'V1 - Value Prop',
      active_version_number: 1,
      versions: [],
      data: {
        framework_type: 'value_prop_canvas',
        customer_jobs: ['Comply with EPA air emission standards quarterly'],
        customer_pains: ['Unplanned downtime during compliance audits'],
        customer_gains: ['Automated emissions reporting telemetry'],
        products_and_services: ['BioScrub Enterprise 5000 Unit'],
        pain_relievers: ['Continuous filter health monitoring alerts'],
        gain_creators: ['Instant one-click compliance documentation export']
      }
    };

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={valuePropDetail}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText(/Comply with EPA air emission standards quarterly/i)).toBeTruthy();
    expect(screen.getByText(/Unplanned downtime during compliance audits/i)).toBeTruthy();
    expect(screen.getByText(/Automated emissions reporting telemetry/i)).toBeTruthy();
    expect(screen.getByText(/BioScrub Enterprise 5000 Unit/i)).toBeTruthy();
    expect(screen.getByText(/Continuous filter health monitoring alerts/i)).toBeTruthy();
    expect(screen.getByText(/Instant one-click compliance documentation export/i)).toBeTruthy();

    // Fabricated fallbacks from old defect must NOT exist
    expect(screen.queryByText(/Inconvenient scheduling/i)).toBeNull();
  });

  it('shows framework switch explanation banner when dropdown changes from active framework', () => {
    const bmcDetail: ModuleDetail<BMCData> = {
      module_type: 'bmc',
      framework_type: 'standard_bmc',
      active_version_id: 'ver-bmc-1',
      active_version_name: 'V1 - 9 Block',
      active_version_number: 1,
      versions: [],
      data: {
        framework_type: 'standard_bmc',
        customer_segments: ['Manufacturing plants'],
        value_propositions: ['Clean emission scrubbers'],
        channels: ['Direct sales'],
        customer_relationships: ['Key account management'],
        revenue_streams: ['Equipment purchase'],
        key_resources: ['Patented bio-enzymes'],
        key_activities: ['Enzyme cultivation'],
        key_partnerships: ['Chemical distributors'],
        cost_structure: ['R&D and bio-lab testing']
      }
    };

    const handleGenerate = vi.fn().mockResolvedValue(undefined);

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={bmcDetail}
        onGenerate={handleGenerate}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    // Initial active framework is Standard BMC
    const switcher = screen.getByLabelText('Framework switcher') as HTMLSelectElement;
    expect(switcher.value).toBe('standard_bmc');
    expect(screen.queryByText(/Framework preview:/i)).toBeNull();

    // Switch dropdown to Lean Canvas
    fireEvent.change(switcher, { target: { value: 'lean_canvas' } });

    // Informational banner must appear explaining that generating will create a new version under Lean Canvas
    expect(screen.getByText(/Framework preview:/i)).toBeTruthy();
    expect(screen.getByText(/Active version was generated under/i)).toBeTruthy();

    // Existing active version 9-block content is still intact
    expect(screen.getByText(/Chemical distributors/i)).toBeTruthy();

    // Clicking generate in banner triggers new version generation with lean_canvas
    const generateLeanBtn = screen.getByRole('button', { name: /Generate Lean Canvas/i });
    fireEvent.click(generateLeanBtn);
    expect(handleGenerate).toHaveBeenCalledWith({ framework_type: 'lean_canvas' });
  });
});
