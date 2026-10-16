import React, { useState } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { BMCModule } from '../components/BMCModule';
import { TechStackModule } from '../components/TechStackModule';
import { Project, ModuleDetail } from '../types';

const mockProject1: Project = {
  id: 'proj_1',
  name: 'Alpha Venture',
  stage: 'Idea / MVP',
  active_module: 'bmc',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  generated_modules: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z'
};

const mockProject2: Project = {
  id: 'proj_2',
  name: 'Beta Venture',
  stage: 'Growth',
  active_module: 'bmc',
  tasks_count: 0,
  completed_tasks_count: 0,
  progress_percentage: 0,
  generated_modules: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z'
};

describe('Phase 3 & 5: Module-Scoped Generation Progress', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('BMC Generate button displays inline spinner and progress text without a global banner', () => {
    const onGenerate = vi.fn().mockResolvedValue(undefined);
    const progress = {
      stageText: 'Synthesizing Alexander Osterwalder 9 blocks...',
      progressPercent: 40
    };

    render(
      <BMCModule
        project={mockProject1}
        moduleDetail={null}
        onGenerate={onGenerate}
        onModify={vi.fn().mockResolvedValue(undefined)}
        onRenameVersion={vi.fn().mockResolvedValue(undefined)}
        onDeleteVersion={vi.fn().mockResolvedValue(undefined)}
        onRestoreVersion={vi.fn().mockResolvedValue(undefined)}
        onExportPdf={vi.fn()}
        isLoading={false}
        isGenerating={true}
        generationProgress={progress}
        isGenerateDisabled={false}
      />
    );

    // Progress must appear inside the button
    const btn = screen.getByRole('button');
    expect(btn).toBeDefined();
    expect(btn.textContent).toContain('Synthesizing Alexander Osterwalder 9 blocks...');
    expect(btn.textContent).toContain('40%');
    expect(btn.hasAttribute('disabled')).toBe(true);

    // Verify no separate banner card exists
    expect(document.querySelector('.card[style*="background: #f5f3ff"]')).toBeNull();
  });

  it('Tech Stack button does not show BMC progress when BMC request is running', () => {
    const onGenerate = vi.fn().mockResolvedValue(undefined);

    // BMC is generating in the project, so TechStack has isGenerateDisabled=true but isGenerating=false
    render(
      <TechStackModule
        project={mockProject1}
        moduleDetail={null}
        onGenerate={onGenerate}
        onModify={vi.fn().mockResolvedValue(undefined)}
        onRenameVersion={vi.fn().mockResolvedValue(undefined)}
        onDeleteVersion={vi.fn().mockResolvedValue(undefined)}
        onRestoreVersion={vi.fn().mockResolvedValue(undefined)}
        onExportPdf={vi.fn()}
        isLoading={false}
        isGenerating={false}
        generationProgress={null}
        isGenerateDisabled={true}
      />
    );

    const btn = screen.getByRole('button', { name: /Generate Technology Stack/i });
    expect(btn).toBeDefined();
    expect(btn.hasAttribute('disabled')).toBe(true);
    // Must NOT contain BMC stage text, spinner, or percentage
    expect(btn.textContent).not.toContain('Synthesizing');
    expect(btn.textContent).not.toContain('%');
    expect(btn.textContent?.trim()).toContain('Generate Technology Stack');
  });

  it('Switching between modules isolates progress to the initiating module and restores it upon return', async () => {
    // Multi-module test harness simulating App.tsx module switching
    const TestHarness: React.FC = () => {
      const [activeMod, setActiveMod] = useState<'bmc' | 'tech_stack'>('bmc');
      const [generatingProgress, setGeneratingProgress] = useState<Record<string, { stageText: string; progressPercent: number }>>({});
      const [bmcDetail, setBmcDetail] = useState<ModuleDetail | null>(null);

      const handleStartBmc = async () => {
        setGeneratingProgress(prev => ({
          ...prev,
          [`${mockProject1.id}:bmc`]: {
            stageText: 'Synthesizing BMC blocks...',
            progressPercent: 35
          }
        }));
      };

      const handleResolveBmc = () => {
        setGeneratingProgress(prev => {
          const next = { ...prev };
          delete next[`${mockProject1.id}:bmc`];
          return next;
        });
        setBmcDetail({
          module_type: 'bmc',
          active_version_id: 'ver_1',
          active_version_name: 'V1',
          active_version_number: 1,
          data: {
            tagline: 'Generated Tagline',
            customer_segments: ['Devs'],
            value_propositions: ['Speed'],
            channels: ['Web'],
            customer_relationships: ['Direct'],
            revenue_streams: ['SaaS'],
            key_resources: ['Servers'],
            key_activities: ['Coding'],
            key_partnerships: ['Cloud'],
            cost_structure: ['Hosting']
          },
          versions: []
        });
      };

      const anyGenerating = Object.keys(generatingProgress).length > 0;
      const bmcProgress = generatingProgress[`${mockProject1.id}:bmc`] || null;
      const techProgress = generatingProgress[`${mockProject1.id}:tech_stack`] || null;

      return (
        <div>
          <button data-testid="tab-bmc" onClick={() => setActiveMod('bmc')}>BMC Tab</button>
          <button data-testid="tab-tech" onClick={() => setActiveMod('tech_stack')}>Tech Tab</button>
          <button data-testid="resolve-bmc" onClick={handleResolveBmc}>Resolve BMC</button>

          {activeMod === 'bmc' && (
            <BMCModule
              project={mockProject1}
              moduleDetail={bmcDetail}
              onGenerate={handleStartBmc}
              onModify={vi.fn().mockResolvedValue(undefined)}
              onRenameVersion={vi.fn().mockResolvedValue(undefined)}
              onDeleteVersion={vi.fn().mockResolvedValue(undefined)}
              onRestoreVersion={vi.fn().mockResolvedValue(undefined)}
              onExportPdf={vi.fn()}
              isLoading={false}
              isGenerating={Boolean(bmcProgress)}
              generationProgress={bmcProgress}
              isGenerateDisabled={anyGenerating && !bmcProgress}
            />
          )}

          {activeMod === 'tech_stack' && (
            <TechStackModule
              project={mockProject1}
              moduleDetail={null}
              onGenerate={vi.fn().mockResolvedValue(undefined)}
              onModify={vi.fn().mockResolvedValue(undefined)}
              onRenameVersion={vi.fn().mockResolvedValue(undefined)}
              onDeleteVersion={vi.fn().mockResolvedValue(undefined)}
              onRestoreVersion={vi.fn().mockResolvedValue(undefined)}
              onExportPdf={vi.fn()}
              isLoading={false}
              isGenerating={Boolean(techProgress)}
              generationProgress={techProgress}
              isGenerateDisabled={anyGenerating && !techProgress}
            />
          )}
        </div>
      );
    };

    render(<TestHarness />);

    // 1. Initially BMC button is idle
    const bmcBtn = screen.getByRole('button', { name: /Generate Business Model Canvas/i });
    expect(bmcBtn.hasAttribute('disabled')).toBe(false);

    // 2. Click Generate BMC
    fireEvent.click(bmcBtn);

    // BMC button now shows BMC-specific progress
    expect(bmcBtn.textContent).toContain('Synthesizing BMC blocks...');
    expect(bmcBtn.textContent).toContain('35%');

    // 3. Switch to Tech Stack tab while BMC is still pending
    fireEvent.click(screen.getByTestId('tab-tech'));

    // Tech Stack button must be disabled to prevent duplicate concurrent runs,
    // but must NEVER display BMC's stage text, percentage, or spinner!
    const techBtn = screen.getByRole('button', { name: /Generate Technology Stack/i });
    expect(techBtn.hasAttribute('disabled')).toBe(true);
    expect(techBtn.textContent?.trim()).toContain('Generate Technology Stack');
    expect(techBtn.textContent).not.toContain('Synthesizing');
    expect(techBtn.textContent).not.toContain('35%');

    // 4. Return to BMC tab: BMC button still shows pending progress
    fireEvent.click(screen.getByTestId('tab-bmc'));
    const bmcBtnReturned = screen.getByRole('button', { name: /Synthesizing BMC blocks/i });
    expect(bmcBtnReturned.textContent).toContain('Synthesizing BMC blocks...');
    expect(bmcBtnReturned.textContent).toContain('35%');

    // 5. Complete/resolve BMC request
    fireEvent.click(screen.getByTestId('resolve-bmc'));

    // BMC is now rendered with its canvas content and progress is cleared
    expect(screen.queryByText(/Synthesizing BMC blocks/)).toBeNull();
    expect(screen.getByText(/Alexander Osterwalder's 9-block business model architecture/i)).toBeDefined();

    // Tech Stack tab button is now re-enabled
    fireEvent.click(screen.getByTestId('tab-tech'));
    const techBtnAfter = screen.getByRole('button', { name: /Generate Technology Stack/i });
    expect(techBtnAfter.hasAttribute('disabled')).toBe(false);
  });

  it('Project switching isolates pending progress to the originating project', () => {
    // Progress state contains a key for Project 1: bmc
    const generatingProgress: Record<string, { stageText: string; progressPercent: number }> = {
      'proj_1:bmc': { stageText: 'Synthesizing Alpha...', progressPercent: 50 }
    };

    // When viewing Project 2, its BMC button must NOT show Project 1 progress
    const isProj2BmcGenerating = Boolean(generatingProgress[`${mockProject2.id}:bmc`]);
    const proj2BmcProgress = generatingProgress[`${mockProject2.id}:bmc`] || null;
    const isProj2GenerateDisabled = Object.keys(generatingProgress).length > 0 && !isProj2BmcGenerating;

    render(
      <BMCModule
        project={mockProject2}
        moduleDetail={null}
        onGenerate={vi.fn().mockResolvedValue(undefined)}
        onModify={vi.fn().mockResolvedValue(undefined)}
        onRenameVersion={vi.fn().mockResolvedValue(undefined)}
        onDeleteVersion={vi.fn().mockResolvedValue(undefined)}
        onRestoreVersion={vi.fn().mockResolvedValue(undefined)}
        onExportPdf={vi.fn()}
        isLoading={false}
        isGenerating={isProj2BmcGenerating}
        generationProgress={proj2BmcProgress}
        isGenerateDisabled={isProj2GenerateDisabled}
      />
    );

    const btn = screen.getByRole('button', { name: /Generate Business Model Canvas/i });
    expect(btn).toBeDefined();
    expect(btn.textContent).not.toContain('Synthesizing Alpha');
    expect(btn.textContent).not.toContain('50%');
  });

  it('Request failure or timeout returns button to retryable state with error', () => {
    const TestErrorHarness: React.FC = () => {
      const [isGenerating, setIsGenerating] = useState(false);
      const [progress, setProgress] = useState<{ stageText: string; progressPercent: number } | null>(null);
      const [errorMessage, setErrorMessage] = useState<string | null>(null);

      const handleGenerate = async () => {
        setIsGenerating(true);
        setProgress({ stageText: 'Starting generation...', progressPercent: 20 });

        // Simulate rejected request
        setTimeout(() => {
          setIsGenerating(false);
          setProgress(null);
          setErrorMessage('Blueprint generation failed. Please try again.');
        }, 50);
      };

      return (
        <div>
          {errorMessage && <div data-testid="error-alert">{errorMessage}</div>}
          <BMCModule
            project={mockProject1}
            moduleDetail={null}
            onGenerate={handleGenerate}
            onModify={vi.fn().mockResolvedValue(undefined)}
            onRenameVersion={vi.fn().mockResolvedValue(undefined)}
            onDeleteVersion={vi.fn().mockResolvedValue(undefined)}
            onRestoreVersion={vi.fn().mockResolvedValue(undefined)}
            onExportPdf={vi.fn()}
            isLoading={false}
            isGenerating={isGenerating}
            generationProgress={progress}
            isGenerateDisabled={false}
          />
        </div>
      );
    };

    vi.useFakeTimers();
    render(<TestErrorHarness />);

    const btn = screen.getByRole('button', { name: /Generate Business Model Canvas/i });
    fireEvent.click(btn);

    // While generating:
    expect(btn.textContent).toContain('Starting generation...');
    expect(btn.hasAttribute('disabled')).toBe(true);

    // Fast-forward timer to simulate failure
    act(() => {
      vi.advanceTimersByTime(100);
    });

    // After failure: error message is displayed, button is re-enabled for retry
    expect(screen.getByTestId('error-alert').textContent).toContain('Blueprint generation failed');
    expect(btn.hasAttribute('disabled')).toBe(false);
    expect(btn.textContent?.trim()).toContain('Generate Business Model Canvas');

    vi.useRealTimers();
  });
});
