import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DashboardPage } from '../pages/DashboardPage';
import { ProfileModal } from '../components/ProfileModal';
import { Header } from '../components/Header';
import { Project, User } from '../types';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    auth: {
      updateProfile: vi.fn(),
      changePassword: vi.fn(),
    },
    projects: {
      bulkDelete: vi.fn(),
    }
  }
}));

const createMockProject = (overrides: Partial<Project> = {}): Project => ({
  id: 'proj_mock',
  name: 'Mock Venture',
  stage: 'Idea / MVP',
  active_module: 'bmc',
  tasks_count: 5,
  completed_tasks_count: 2,
  progress_percentage: 40,
  generated_modules: ['bmc'],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  ...overrides
});

describe('F-15: Refresh app user state after profile updates', () => {
  const mockUser: User = {
    id: 'usr_test123',
    username: 'original_user',
    email: 'original@example.com',
    role: 'user',
    created_at: '2026-01-01'
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('invokes onUserUpdated callback with fresh user data on successful profile update', async () => {
    const onUserUpdated = vi.fn();
    const onClose = vi.fn();

    const updatedUser: User = {
      ...mockUser,
      username: 'renamed_user',
      email: 'renamed@example.com'
    };

    (api.auth.updateProfile as any).mockResolvedValue(updatedUser);

    render(
      <ProfileModal
        isOpen={true}
        onClose={onClose}
        user={mockUser}
        onUserUpdated={onUserUpdated}
      />
    );

    // Select the username input (the first input with value 'original_user')
    const inputs = screen.getAllByDisplayValue('original_user');
    const usernameInput = inputs[0];
    fireEvent.change(usernameInput, { target: { value: 'renamed_user' } });

    const emailInput = screen.getByDisplayValue('original@example.com');
    fireEvent.change(emailInput, { target: { value: 'renamed@example.com' } });

    const submitBtn = screen.getByText('Update Profile');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.auth.updateProfile).toHaveBeenCalledWith({
        username: 'renamed_user',
        email: 'renamed@example.com'
      });
      expect(onUserUpdated).toHaveBeenCalledWith(updatedUser);
    });
  });

  it('Header passes onUserUpdated down to ProfileModal and displays current user details', () => {
    const onUserUpdated = vi.fn();
    const mockProject = createMockProject({ name: 'Ventures Alpha' });

    render(
      <Header
        project={mockProject}
        user={mockUser}
        onLogout={vi.fn()}
        onUserUpdated={onUserUpdated}
      />
    );

    // Initial username displayed
    expect(screen.getByText('original_user')).toBeDefined();
  });
});

describe('F-16: Dashboard module shortcuts open their named modules', () => {
  const mockUser: User = {
    id: 'usr_1',
    username: 'tester',
    email: 'tester@test.com',
    role: 'user',
    created_at: '2026-01-01'
  };

  const mockProjects: Project[] = [
    createMockProject({
      id: 'proj_first',
      name: 'Primary Project',
      active_module: 'bmc',
      generated_modules: ['bmc']
    })
  ];

  it('passes the target module explicitly for every shortcut button', () => {
    const onOpenProject = vi.fn();

    render(
      <DashboardPage
        user={mockUser}
        projects={mockProjects}
        onOpenProject={onOpenProject}
        onCreateNewProject={vi.fn()}
        onDeleteProject={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    // Shortcut 1: BMC
    const bmcBtn = screen.getByText('Business Model Canvas');
    fireEvent.click(bmcBtn);
    expect(onOpenProject).toHaveBeenCalledWith('proj_first', 'bmc');

    // Shortcut 2: Technology Stack
    const techBtn = screen.getByText('Technology Stack');
    fireEvent.click(techBtn);
    expect(onOpenProject).toHaveBeenCalledWith('proj_first', 'tech_stack');

    // Shortcut 3: Execution Roadmap
    const roadmapBtn = screen.getByText('Execution Roadmap');
    fireEvent.click(roadmapBtn);
    expect(onOpenProject).toHaveBeenCalledWith('proj_first', 'execution_roadmap');

    // Shortcut 4: Planning Copilot
    const copilotBtn = screen.getByText('Planning Copilot');
    fireEvent.click(copilotBtn);
    expect(onOpenProject).toHaveBeenCalledWith('proj_first', 'blueprint_copilot');
  });

  it('clicking project card without shortcut opens project at default active module', () => {
    const onOpenProject = vi.fn();

    render(
      <DashboardPage
        user={mockUser}
        projects={mockProjects}
        onOpenProject={onOpenProject}
        onCreateNewProject={vi.fn()}
        onDeleteProject={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    const projectCardTitle = screen.getByText('Primary Project');
    fireEvent.click(projectCardTitle);
    expect(onOpenProject).toHaveBeenCalledWith('proj_first');
  });
});

describe('F-07: Repair dashboard bulk deletion', () => {
  const mockUser: User = {
    id: 'usr_1',
    username: 'tester',
    email: 'tester@test.com',
    role: 'user',
    created_at: '2026-01-01'
  };

  const mockProjects: Project[] = [
    createMockProject({ id: 'proj_1', name: 'Project One', stage: 'Idea / MVP' }),
    createMockProject({ id: 'proj_2', name: 'Project Two', stage: 'Growth' })
  ];

  it('propagates error when onBulkDeleteProjects fails without clearing selection', async () => {
    const onBulkDeleteProjects = vi.fn().mockRejectedValue(new Error('Database lock error'));

    render(
      <DashboardPage
        user={mockUser}
        projects={mockProjects}
        onOpenProject={vi.fn()}
        onCreateNewProject={vi.fn()}
        onDeleteProject={vi.fn()}
        onBulkDeleteProjects={onBulkDeleteProjects}
        onLogout={vi.fn()}
      />
    );

    // Enter manage mode
    const manageBtn = screen.getByText('Manage Projects');
    fireEvent.click(manageBtn);

    // Select all
    const selectAllBtn = screen.getByText('Select All');
    fireEvent.click(selectAllBtn);

    // Click delete selected
    const deleteSelectedBtn = screen.getByText(/Delete Selected/);
    fireEvent.click(deleteSelectedBtn);

    // Confirm in modal
    const confirmBtn = screen.getByText('Permanently Delete 2 Projects');
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onBulkDeleteProjects).toHaveBeenCalledWith(['proj_1', 'proj_2']);
      expect(screen.getByText('Database lock error')).toBeDefined();
    });
  });

  it('clears selection and closes modal when onBulkDeleteProjects succeeds', async () => {
    const onBulkDeleteProjects = vi.fn().mockResolvedValue(undefined);

    render(
      <DashboardPage
        user={mockUser}
        projects={mockProjects}
        onOpenProject={vi.fn()}
        onCreateNewProject={vi.fn()}
        onDeleteProject={vi.fn()}
        onBulkDeleteProjects={onBulkDeleteProjects}
        onLogout={vi.fn()}
      />
    );

    const manageBtn = screen.getByText('Manage Projects');
    fireEvent.click(manageBtn);

    const selectAllBtn = screen.getByText('Select All');
    fireEvent.click(selectAllBtn);

    const deleteSelectedBtn = screen.getByText(/Delete Selected/);
    fireEvent.click(deleteSelectedBtn);

    const confirmBtn = screen.getByText('Permanently Delete 2 Projects');
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onBulkDeleteProjects).toHaveBeenCalledWith(['proj_1', 'proj_2']);
      expect(screen.queryByText('Permanently Delete 2 Projects')).toBeNull();
    });
  });
});
