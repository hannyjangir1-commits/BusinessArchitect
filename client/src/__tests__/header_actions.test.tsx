import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Header } from '../components/Header';
import { Project, User } from '../types';

vi.mock('../services/api', () => ({
  api: {
    tasks: { list: vi.fn() },
    modules: { get: vi.fn() },
    health: vi.fn(),
  },
}));

import { api } from '../services/api';

const project = {
  id: 'project-1',
  name: 'PCB Venture',
  description: 'PCB layout planning workspace',
  industry: 'Electronics',
  stage: 'Idea',
  generated_modules: ['bmc'],
  active_module: 'bmc',
} as Project;

const user = { id: 'user-1', username: 'tester', email: 'tester@example.com' } as User;

describe('project header actions', () => {
  beforeEach(() => vi.clearAllMocks());

  it('searches saved project content and opens the matching module', async () => {
    vi.mocked(api.tasks.list).mockResolvedValue([
      { id: 'task-1', title: 'Prototype PCB board', phase: 'Validation' } as never,
    ]);
    vi.mocked(api.modules.get).mockResolvedValue({ data: { value_propositions: ['PCB design workspace'] } } as never);
    const onSelectModule = vi.fn();

    render(
      <Header project={project} user={user} onLogout={vi.fn()} onSelectModule={onSelectModule} />
    );

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search project content' }), {
      target: { value: 'PCB' },
    });

    const taskResult = await screen.findByText('Prototype PCB board', {}, { timeout: 2000 });
    fireEvent.click(taskResult);

    expect(api.tasks.list).toHaveBeenCalledWith('project-1', { search: 'PCB' });
    expect(api.modules.get).toHaveBeenCalledWith('project-1', 'bmc');
    expect(onSelectModule).toHaveBeenCalledWith('execution_roadmap');
  });

  it('shows current API and database health when the health control is opened', async () => {
    vi.mocked(api.health).mockResolvedValue({
      status: 'healthy',
      database_connected: true,
      generation_configured: true,
    });

    render(<Header project={project} user={user} onLogout={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Check service health' }));

    await waitFor(() => expect(api.health).toHaveBeenCalledOnce());
    expect(await screen.findByText(/API available/)).toBeTruthy();
    expect(screen.getByText('Database connected')).toBeTruthy();
  });
});
