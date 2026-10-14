import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { VersionConflictModal } from '../components/VersionConflictModal';
import { ContextualAssistant } from '../components/ContextualAssistant';
import { LogoutConfirmModal } from '../components/LogoutConfirmModal';
import { ProfileModal } from '../components/ProfileModal';
import { ArchitectureInfographic } from '../components/ArchitectureInfographic';
import { VersionItem, TechStackData } from '../types';

describe('VersionConflictModal', () => {
  const mockVersions: VersionItem[] = [
    {
      id: 'ver_1',
      version_number: 1,
      version_name: 'BMC V1',
      change_summary: 'Initial canvas',
      is_active: false,
      created_at: '2026-10-01T10:00:00Z'
    },
    {
      id: 'ver_2',
      version_number: 2,
      version_name: 'BMC V2',
      change_summary: 'Target customer pivot',
      is_active: true,
      created_at: '2026-10-02T10:00:00Z'
    }
  ];

  it('renders existing versions and disables confirm until checkbox is checked', () => {
    const onResolve = vi.fn();
    const onCancel = vi.fn();

    render(
      <VersionConflictModal
        moduleTitle="Business Model Canvas"
        existingVersions={mockVersions}
        onResolveReplace={onResolve}
        onCancel={onCancel}
        isLoading={false}
      />
    );

    expect(screen.getByText('Maximum 5 Versions Reached')).toBeDefined();
    expect(screen.getAllByText(/BMC V1/).length).toBeGreaterThan(0);
    expect(screen.getByText(/BMC V2/)).toBeDefined();

    const confirmBtn = screen.getByText(/Confirm & Replace Selected Version/i).closest('button');
    expect(confirmBtn?.disabled).toBe(true);

    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDefined();

    // Check the confirmation box
    fireEvent.click(checkbox);
    expect(confirmBtn?.disabled).toBe(false);

    // Click confirm
    fireEvent.click(confirmBtn!);
    expect(onResolve).toHaveBeenCalledWith('ver_1');
  });
});

describe('ContextualAssistant', () => {
  it('displays module-specific prompt chips for BMC', () => {
    const onModify = vi.fn();
    const onClose = vi.fn();

    render(
      <ContextualAssistant
        moduleType="bmc"
        moduleTitle="Business Model Canvas"
        onModify={onModify}
        onClose={onClose}
        isLoading={false}
      />
    );

    expect(screen.getByText('AI Assistant')).toBeDefined();
    expect(screen.getByText('(Business Model Canvas)')).toBeDefined();

    // Suggested chips
    expect(screen.getByText(/Refine value proposition/i)).toBeDefined();
    expect(screen.getByText(/Add customer channels/i)).toBeDefined();

    // Clicking close button calls onClose
    const closeBtn = screen.getByLabelText('Close assistant panel');
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('displays tech-specific prompt chips for Tech Stack', () => {
    const onModify = vi.fn();

    render(
      <ContextualAssistant
        moduleType="tech_stack"
        moduleTitle="Technology Stack"
        onModify={onModify}
        isLoading={false}
      />
    );

    expect(screen.getByText('AI Assistant')).toBeDefined();
    expect(screen.getByText('(Technology Stack)')).toBeDefined();
    expect(screen.getByText(/Add authentication layer/i)).toBeDefined();
    expect(screen.getByText(/Evaluate database choice/i)).toBeDefined();
  });
});

describe('LogoutConfirmModal', () => {
  it('handles stay signed in vs confirmed logout', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();

    render(
      <LogoutConfirmModal
        isOpen={true}
        onConfirm={onConfirm}
        onClose={onClose}
        isLoading={false}
      />
    );

    expect(screen.getByText('Are you sure you want to log out?')).toBeDefined();
    expect(screen.getByText('Your current authenticated session will be securely terminated.')).toBeDefined();

    // Cancel
    const cancelBtn = screen.getByText('No, Stay Signed In');
    fireEvent.click(cancelBtn);
    expect(onClose).toHaveBeenCalled();

    // Confirm
    const confirmBtn = screen.getByText('Yes, Log Out');
    fireEvent.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalled();
  });
});

describe('ProfileModal', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('switches and persists theme in localStorage and data-theme', () => {
    const onClose = vi.fn();
    const onThemeChange = vi.fn((theme: 'light' | 'dark') => {
      document.documentElement.setAttribute('data-theme', theme);
    });

    render(
      <ProfileModal
        isOpen={true}
        onClose={onClose}
        user={{ id: 'usr_1', username: 'founder_alice', email: 'alice@founder.io', role: 'user', created_at: '2026-10-01' }}
        onThemeChange={onThemeChange}
        currentTheme="light"
      />
    );

    expect(screen.getByText('User Profile & Preferences')).toBeDefined();
    expect(screen.getByPlaceholderText('e.g. Alex Morgan')).toBeDefined();

    // Toggle Dark Theme
    const darkBtn = screen.getByText(/Dark Theme/i);
    fireEvent.click(darkBtn);

    // Submit save preferences
    const saveBtn = screen.getByText('Save Preferences');
    fireEvent.click(saveBtn);

    expect(onThemeChange).toHaveBeenCalledWith('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('aba_theme')).toBe('dark');
  });
});

describe('ArchitectureInfographic', () => {
  it('renders vector SVG with architecture tiers and export option', () => {
    const onDownloadSvg = vi.fn();

    const techData: TechStackData = {
      architecture_pattern: 'Microservices with Event-Driven Architecture',
      summary: 'High performance enterprise cloud system',
      recommendations: [
        {
          technology: 'React 19',
          name: 'React 19',
          category: 'Frontend Client',
          purpose: 'Single page application web client',
          suitability: 'High performance UI',
          trade_offs: 'Bundle size management'
        },
        {
          technology: 'FastAPI',
          name: 'FastAPI',
          category: 'Backend API',
          purpose: 'Asynchronous RESTful microservices',
          suitability: 'High throughput async endpoints',
          trade_offs: 'Python GIL limits heavy CPU work'
        },
        {
          technology: 'PostgreSQL',
          name: 'PostgreSQL',
          category: 'Database & Storage',
          purpose: 'Relational database persistence',
          suitability: 'ACID transactional guarantees',
          trade_offs: 'Vertical scaling limits'
        }
      ]
    };

    render(
      <ArchitectureInfographic
        projectName="CloudScale Platform"
        techData={techData}
        onDownloadSvg={onDownloadSvg}
      />
    );

    expect(screen.getByText('System Architecture Blueprint Infographic')).toBeDefined();
    expect(screen.getByText(/CLIENT & PRESENTATION TIER/i)).toBeDefined();
    expect(screen.getByText(/APPLICATION & API SERVICES TIER/i)).toBeDefined();
    expect(screen.getByText(/DATA & STATE MANAGEMENT TIER/i)).toBeDefined();
    expect(screen.getByText('React 19')).toBeDefined();
    expect(screen.getByText('FastAPI')).toBeDefined();
    expect(screen.getByText('PostgreSQL')).toBeDefined();

    // Download SVG button
    const downloadSvgBtn = screen.getByText('Download SVG Diagram');
    fireEvent.click(downloadSvgBtn);
    expect(onDownloadSvg).toHaveBeenCalled();
  });
});
