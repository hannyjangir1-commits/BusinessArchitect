import React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor, cleanup, within } from '@testing-library/react';
import { BMCModule } from '../components/BMCModule';
import { api } from '../services/api';
import { BMCData, ModuleDetail, Project } from '../types';

vi.mock('../services/api', () => ({
  api: {
    tasks: {
      create: vi.fn(),
    },
    knowledge: {
      create: vi.fn(),
    },
    modules: {
      modify: vi.fn(),
    },
  },
}));

vi.mock('../services/queryCache', () => ({
  queryCache: {
    invalidate: vi.fn(),
    invalidatePrefix: vi.fn(),
  },
}));

const mockProject: Project = {
  id: 'proj-123',
  name: 'Venture Test',
  stage: 'MVP',
  industry: 'FinTech',
  active_module: 'bmc',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  generated_modules: ['bmc'],
  created_at: '2026-10-28T00:00:00Z',
  updated_at: '2026-10-28T00:00:00Z',
};

const baseBMCData: BMCData = {
  tagline: 'Grounded financial operations',
  customer_segments: ['No evidence has verified this assumption.'],
  value_propositions: ['Automated unit economics engine'],
  channels: ['Direct outreach'],
  customer_relationships: ['High-touch onboarding'],
  revenue_streams: ['SaaS subscription'],
  key_resources: ['Core ledger engine'],
  key_activities: ['Compliance audits'],
  key_partnerships: ['Banking API providers'],
  cost_structure: ['Cloud infrastructure'],
  assumptions: ['Testing assumptions array'],
};

const mockModuleDetail: ModuleDetail<BMCData> = {
  module_type: 'bmc',
  active_version_name: 'V1',
  versions: [{ id: 'v1', version_number: 1, version_name: 'V1', is_active: true, created_at: '2026-10-28T00:00:00Z' }],
  data: baseBMCData,
};

describe('Truthful Canvas Actions and Epistemic Badges', () => {
  beforeEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('does NOT mark "No evidence has verified this assumption" as Evidence Supported', () => {
    render(
      <BMCModule
        project={mockProject}
        moduleDetail={mockModuleDetail}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    // The item text is present
    expect(screen.getByText('No evidence has verified this assumption.')).toBeTruthy();

    // The badge must be Hypothesis, NOT Evidence Supported
    expect(screen.getAllByText('Hypothesis').length).toBeGreaterThan(0);
    expect(screen.queryByText('Evidence Supported')).toBeNull();
  });

  it('renders Evidence Supported only when explicit item_metadata defines it', () => {
    const dataWithMetadata: BMCData = {
      ...baseBMCData,
      item_metadata: {
        'Automated unit economics engine': {
          epistemic_status: 'evidence_supported',
          evidence_ids: ['ev-001'],
        },
      },
    };

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={{ ...mockModuleDetail, data: dataWithMetadata }}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText('Evidence Supported')).toBeTruthy();
  });

  it('opens real Task dialog on Add to delivery roadmap and creates a task via API', async () => {
    (api.tasks.create as any).mockResolvedValueOnce({
      id: 'task-1',
      project_id: 'proj-123',
      title: 'Deliver: Automated unit economics engine',
      task_code: 'TSK-01',
    });

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={mockModuleDetail}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    // Target the specific canvas item container for Automated unit economics engine
    const itemEl = screen.getByText('Automated unit economics engine');
    const itemContainer = itemEl.closest('div[style*="display: flex"]') || itemEl.parentElement!;
    const actionBtn = within(itemContainer as HTMLElement).getByTitle('Actions');
    fireEvent.click(actionBtn);

    // Click "Add to Delivery Roadmap" button in popover
    const addRoadmapBtn = screen.getByRole('button', { name: /Add to Delivery Roadmap/i });
    fireEvent.click(addRoadmapBtn);

    // Dialog should open with prefilled task title
    expect(screen.getByText('Create Roadmap Task')).toBeTruthy();
    const titleInput = screen.getByPlaceholderText(/Set up partner agreements/i) as HTMLInputElement;
    expect(titleInput.value).toContain('Automated unit economics engine');

    // Submit dialog
    const createBtn = screen.getByRole('button', { name: 'Create Task' });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(api.tasks.create).toHaveBeenCalledTimes(1);
    });

    expect(api.tasks.create).toHaveBeenCalledWith(
      'proj-123',
      expect.objectContaining({
        title: expect.stringContaining('Automated unit economics engine'),
        phase: 'Core Implementation',
      })
    );
  });

  it('handles API failure gracefully without showing false success', async () => {
    (api.tasks.create as any).mockRejectedValueOnce(new Error('Network connection failed'));

    render(
      <BMCModule
        project={mockProject}
        moduleDetail={mockModuleDetail}
        onGenerate={vi.fn()}
        onModify={vi.fn()}
        onRenameVersion={vi.fn()}
        onDeleteVersion={vi.fn()}
        onRestoreVersion={vi.fn()}
        onExportPdf={vi.fn()}
        isLoading={false}
      />
    );

    const itemEl = screen.getByText('Automated unit economics engine');
    const itemContainer = itemEl.closest('div[style*="display: flex"]') || itemEl.parentElement!;
    const actionBtn = within(itemContainer as HTMLElement).getByTitle('Actions');
    fireEvent.click(actionBtn);

    const addRoadmapBtn = screen.getByRole('button', { name: /Add to Delivery Roadmap/i });
    fireEvent.click(addRoadmapBtn);

    const createBtn = screen.getByRole('button', { name: 'Create Task' });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(screen.getByText('Network connection failed')).toBeTruthy();
    });

    // Form remains open and preserved
    expect(screen.getByText('Create Roadmap Task')).toBeTruthy();
  });
});
