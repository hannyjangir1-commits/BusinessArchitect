import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BlueprintCopilotModule } from '../components/BlueprintCopilotModule';
import { api } from '../services/api';
import { queryCache } from '../services/queryCache';
import { Project } from '../types';

vi.mock('../services/api', () => ({
  api: {
    copilot: {
      proposeChange: vi.fn(),
      applyProposal: vi.fn(),
      sendMessage: vi.fn(),
      getPage: vi.fn(),
      getLatestHistory: vi.fn(),
      getOperationStatus: vi.fn(),
    },
    modules: {
      modify: vi.fn(),
    },
  },
}));

describe('Copilot Proposals & Exact Application', () => {
  const mockProject: Project = {
    id: 'proj_copilot_test',
    name: 'Atlas Systems',
    stage: 'MVP',
    industry: 'Cloud Infrastructure',
    description: 'Autonomous cloud management platform',
    goals: 'Validate with 10 design partners',
    budget: '$50,000',
    business_context: 'B2B infrastructure SaaS',
    existing_stack: { backend: ['Go', 'Kubernetes'], database: ['Postgres'] },
    target_customers: 'DevOps leads at scale-ups',
    active_module: 'blueprint_copilot',
    tasks_count: 0,
    completed_tasks_count: 0,
    progress_percentage: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    generated_modules: ['bmc'],
  };

  const mockProposal = {
    id: 'prop_999',
    target_module: 'bmc',
    summary: 'Add enterprise security compliance and dedicated support tiers.',
    proposed_diff: {
      revenue_streams: {
        before: ['Self-serve $49/mo'],
        after: ['Self-serve $49/mo', 'Enterprise custom contract with SLA'],
      },
    },
    affected_assumptions: ['Enterprise procurement timeline is under 60 days'],
    affected_tasks: ['Obtain SOC2 Type 1 certification'],
    requires_confirmation: true,
    proposed_content: {
      customer_segments: [{ id: 'cs1', text: 'Enterprise IT teams' }],
    },
    status: 'pending',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls api.copilot.applyProposal with proposal ID when applying exact proposal', async () => {
    vi.mocked(api.copilot.proposeChange).mockResolvedValueOnce(mockProposal);
    vi.mocked(api.copilot.applyProposal).mockResolvedValueOnce({
      success: true,
      message: 'Proposal applied successfully',
      target_module: 'bmc',
      proposal_id: 'prop_999',
      version_id: 'ver_2',
      version_number: 2,
      version_name: 'BMC V2',
      data: mockProposal.proposed_content,
    });

    const invalidateSpy = vi.spyOn(queryCache, 'invalidate');

    render(
      <BlueprintCopilotModule
        project={mockProject}
        messages={[]}
        onSendMessage={vi.fn()}
        isLoading={false}
      />
    );

    // Switch to propose mode
    const proposeTab = screen.getByRole('button', { name: /Propose Change/i });
    fireEvent.click(proposeTab);

    // Enter prompt and click Generate Preview
    const textarea = screen.getByPlaceholderText(/Describe the updates for Business Model Canvas/i);
    fireEvent.change(textarea, { target: { value: 'Add enterprise tiers' } });

    const submitBtn = screen.getByRole('button', { name: /Generate Proposal Preview/i });
    fireEvent.click(submitBtn);

    // Verify modal appears
    await waitFor(() => {
      expect(screen.getByText('Review Change Proposal')).toBeDefined();
      expect(screen.getAllByText(/Add enterprise security compliance/).length).toBeGreaterThanOrEqual(1);
    });

    // Click Apply Changes to Module
    const applyBtn = screen.getByRole('button', { name: /Apply Changes to Module/i });
    fireEvent.click(applyBtn);

    // Verify exact apply was called without re-running modify
    await waitFor(() => {
      expect(api.copilot.applyProposal).toHaveBeenCalledWith('proj_copilot_test', 'prop_999');
      expect(api.modules.modify).not.toHaveBeenCalled();
    });

    // Verify cache invalidations
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('forwards proposalId to onApplyProposal if callback is provided', async () => {
    vi.mocked(api.copilot.proposeChange).mockResolvedValueOnce(mockProposal);
    const mockOnApply = vi.fn().mockResolvedValue(undefined);

    render(
      <BlueprintCopilotModule
        project={mockProject}
        messages={[]}
        onSendMessage={vi.fn()}
        onApplyProposal={mockOnApply}
        isLoading={false}
      />
    );

    // Switch to propose mode
    const proposeTab = screen.getByRole('button', { name: /Propose Change/i });
    fireEvent.click(proposeTab);

    const textarea = screen.getByPlaceholderText(/Describe the updates for Business Model Canvas/i);
    fireEvent.change(textarea, { target: { value: 'Add enterprise tiers' } });

    const submitBtn = screen.getByRole('button', { name: /Generate Proposal Preview/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Review Change Proposal')).toBeDefined();
    });

    const applyBtn = screen.getByRole('button', { name: /Apply Changes to Module/i });
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(mockOnApply).toHaveBeenCalledWith('bmc', 'Add enterprise tiers', 'prop_999');
    });
  });
});
