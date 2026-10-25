import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { parseStrictDateOnly, dueByDay, calculateLocalRoadmapSummary } from '../utils/taskMilestones';
import { reconcileSend } from '../utils/copilotReconciliation';
import { BlueprintCopilotModule } from '../components/BlueprintCopilotModule';
import { CopilotMessage, CopilotSendResult, RoadmapTask } from '../types';
import strictDateCases from '../../../shared_fixtures/strict_date_cases.json';

// ============================================================
// 1. SHARED STRICT DATE-ONLY CONTRACT
// ============================================================

describe('Phase 8.1: Shared strict date-only validation contract', () => {
  it('strictly validates all cases in shared_fixtures/strict_date_cases.json', () => {
    expect(strictDateCases.length).toBeGreaterThan(0);

    for (const testCase of strictDateCases) {
      const parsed = parseStrictDateOnly(testCase.input);
      if (testCase.valid) {
        expect(parsed, `Valid case failed: ${testCase.reason} for input ${testCase.input}`).not.toBeNull();
        expect(parsed?.year).toBe(testCase.year);
        expect(parsed?.month).toBe(testCase.month);
        expect(parsed?.day).toBe(testCase.day);
      } else {
        expect(parsed, `Invalid case should have been rejected: ${testCase.reason} for input ${testCase.input}`).toBeNull();
      }
    }
  });

  it('rejects JS Date.UTC roll-overs (e.g. 2026-02-31 and non-leap 2026-02-29)', () => {
    expect(parseStrictDateOnly('2026-02-31')).toBeNull();
    expect(parseStrictDateOnly('2026-02-29')).toBeNull();
    expect(parseStrictDateOnly('2028-02-29')).not.toBeNull();
  });
});

// ============================================================
// 2. MILESTONE CUMULATIVE BOUNDARIES & STRING FALLBACK REMOVAL
// ============================================================

describe('Phase 8.1: Milestone cumulative boundaries and string fallback removal', () => {
  const anchor = '2026-03-01';

  it('evaluates exact calendar boundaries (Day 1, 30, 31, 60, 61, 90, 91)', () => {
    const makeTask = (id: string, endDate: string): RoadmapTask => ({
      id,
      project_id: 'p1',
      task_code: `TSK-${id}`,
      title: `Task ${id}`,
      priority: 'Medium',
      status: 'Finished',
      phase: 'Phase 1',
      timeline: '30-day MVP', // Duration text should NOT override date calculation
      start_date: anchor,
      end_date: endDate,
      dependencies: []
    });

    const overdueTask = makeTask('t_overdue', '2026-02-20'); // Due before anchor
    const day1Task = makeTask('t_d01', '2026-03-01');
    const day30Task = makeTask('t_d30', '2026-03-30');
    const day31Task = makeTask('t_d31', '2026-03-31');
    const day60Task = makeTask('t_d60', '2026-04-29');
    const day61Task = makeTask('t_d61', '2026-04-30');
    const day90Task = makeTask('t_d90', '2026-05-29');
    const day91Task = makeTask('t_d91', '2026-05-30');
    const undatedTask = makeTask('t_undated', ''); // Empty string for undated

    // Overdue task belongs to cumulative 30, 60, 90
    expect(dueByDay(overdueTask, anchor, 30)).toBe(true);
    expect(dueByDay(overdueTask, anchor, 60)).toBe(true);
    expect(dueByDay(overdueTask, anchor, 90)).toBe(true);

    // Day 30 belongs to 30, 60, 90
    expect(dueByDay(day30Task, anchor, 30)).toBe(true);
    expect(dueByDay(day30Task, anchor, 60)).toBe(true);
    expect(dueByDay(day30Task, anchor, 90)).toBe(true);

    // Day 31 belongs to 60, 90, but NOT 30
    expect(dueByDay(day31Task, anchor, 30)).toBe(false);
    expect(dueByDay(day31Task, anchor, 60)).toBe(true);
    expect(dueByDay(day31Task, anchor, 90)).toBe(true);

    // Day 60 belongs to 60, 90
    expect(dueByDay(day60Task, anchor, 60)).toBe(true);
    expect(dueByDay(day60Task, anchor, 90)).toBe(true);

    // Day 61 belongs to 90, but NOT 60
    expect(dueByDay(day61Task, anchor, 60)).toBe(false);
    expect(dueByDay(day61Task, anchor, 90)).toBe(true);

    // Day 90 belongs to 90
    expect(dueByDay(day90Task, anchor, 90)).toBe(true);

    // Day 91 belongs to none of 30, 60, 90
    expect(dueByDay(day91Task, anchor, 90)).toBe(false);

    // Undated task belongs to no dated milestone
    expect(dueByDay(undatedTask, anchor, 30)).toBe(false);
    expect(dueByDay(undatedTask, anchor, 60)).toBe(false);
    expect(dueByDay(undatedTask, anchor, 90)).toBe(false);
  });

  it('does NOT fall back to timeline duration text when dates are present', () => {
    const conflictingTask: RoadmapTask = {
      id: 't_conflict',
      project_id: 'p1',
      task_code: 'TSK-CONFLICT',
      title: 'Task with misleading text',
      priority: 'High',
      status: 'Finished',
      phase: 'Phase 2',
      start_date: '2026-03-01',
      end_date: '2026-04-14', // Day 45
      timeline: '30-day target quick MVP',
      dependencies: []
    };

    // Because Day 45 > 30, it must NOT belong to Day 30 despite timeline containing '30'
    expect(dueByDay(conflictingTask, anchor, 30)).toBe(false);
    expect(dueByDay(conflictingTask, anchor, 60)).toBe(true);
  });

  it('calculates roadmap summary matching Python backend values', () => {
    const tasks: RoadmapTask[] = [
      { id: 't1', project_id: 'p1', task_code: 'T1', title: 'T1', priority: 'Medium', status: 'Finished', phase: 'P1', timeline: '10d', start_date: '2026-03-01', end_date: '2026-03-10', dependencies: [] },
      { id: 't2', project_id: 'p1', task_code: 'T2', title: 'T2', priority: 'Medium', status: 'Pending', phase: 'P1', timeline: '20d', start_date: '2026-03-10', end_date: '2026-03-30', dependencies: [] },
      { id: 't3', project_id: 'p1', task_code: 'T3', title: 'T3', priority: 'Medium', status: 'Finished', phase: 'P2', timeline: '16d', start_date: '2026-03-15', end_date: '2026-03-31', dependencies: [] },
      { id: 't4', project_id: 'p1', task_code: 'T4', title: 'T4', priority: 'Medium', status: 'Finished', phase: 'P4', timeline: 'undated', start_date: '', end_date: '', dependencies: [] }
    ];

    const summary = calculateLocalRoadmapSummary(tasks, '2026-03-01');
    expect(summary.total_tasks).toBe(4);
    expect(summary.completed_tasks).toBe(3);
    expect(summary.milestone_30_total).toBe(2); // t1 and t2
    expect(summary.milestone_30_completed).toBe(1); // t1
    expect(summary.milestone_60_total).toBe(3); // t1, t2, t3
    expect(summary.milestone_60_completed).toBe(2); // t1, t3
  });
});

// ============================================================
// 3. CHAT IDENTITY RECONCILIATION
// ============================================================

describe('Phase 8.1: Chat identity reconciliation', () => {
  it('reconciles temp user ID with authoritative database ID and appends assistant message', () => {
    const existing: CopilotMessage[] = [
      { id: 'msg_001', role: 'user', content: 'First query', created_at: '2026-03-01T10:00:00Z', status: 'saved' },
      { id: 'msg_002', role: 'assistant', content: 'First reply', created_at: '2026-03-01T10:00:05Z', status: 'saved' },
      { id: 'temp_999', role: 'user', content: 'What is our market size?', created_at: '2026-03-01T10:01:00Z', status: 'sending', client_msg_id: 'client_op_1' }
    ];

    const sendResult: CopilotSendResult = {
      id: 'db_asst_msg_101',
      role: 'assistant',
      content: 'The total addressable market is $2.4B.',
      created_at: '2026-03-01T10:01:03Z',
      operation_status: 'completed',
      client_msg_id: 'client_op_1',
      user_message: {
        id: 'db_usr_msg_100',
        role: 'user',
        content: 'What is our market size?',
        created_at: '2026-03-01T10:01:00Z'
      },
      assistant_message: {
        id: 'db_asst_msg_101',
        role: 'assistant',
        content: 'The total addressable market is $2.4B.',
        created_at: '2026-03-01T10:01:03Z'
      }
    };

    const reconciled = reconcileSend(existing, 'temp_999', sendResult);

    // temp_999 must NOT be in the reconciled list
    expect(reconciled.find(m => m.id === 'temp_999')).toBeUndefined();

    // Authoritative saved user message is present with db_usr_msg_100
    const userMsg = reconciled.find(m => m.id === 'db_usr_msg_100');
    expect(userMsg).toBeDefined();
    expect(userMsg?.status).toBe('saved');
    expect(userMsg?.content).toBe('What is our market size?');

    // Assistant message is present with db_asst_msg_101
    const asstMsg = reconciled.find(m => m.id === 'db_asst_msg_101');
    expect(asstMsg).toBeDefined();
    expect(asstMsg?.status).toBe('saved');
    expect(asstMsg?.content).toBe('The total addressable market is $2.4B.');

    // Total length: 4 messages (msg_001, msg_002, db_usr_msg_100, db_asst_msg_101)
    expect(reconciled).toHaveLength(4);
  });

  it('deduplicates by authoritative ID, never duplicates saved message after pagination', () => {
    const pageMessages: CopilotMessage[] = [
      { id: 'db_usr_msg_100', role: 'user', content: 'What is our market size?', created_at: '2026-03-01T10:01:00Z', status: 'saved' },
      { id: 'db_asst_msg_101', role: 'assistant', content: 'The total addressable market is $2.4B.', created_at: '2026-03-01T10:01:03Z', status: 'saved' }
    ];

    const sendResult: CopilotSendResult = {
      id: pageMessages[1].id,
      role: pageMessages[1].role,
      content: pageMessages[1].content,
      created_at: pageMessages[1].created_at,
      operation_status: 'completed',
      client_msg_id: 'client_op_1',
      user_message: pageMessages[0],
      assistant_message: pageMessages[1]
    };

    const reconciled = reconcileSend(pageMessages, 'some_temp_id', sendResult);
    expect(reconciled).toHaveLength(2);
    expect(reconciled.filter(m => m.id === 'db_usr_msg_100')).toHaveLength(1);
  });

  it('keeps two intentional identical questions as two distinct messages', () => {
    const existing: CopilotMessage[] = [
      { id: 'msg_q1', role: 'user', content: 'What are our revenue streams?', created_at: '2026-03-01T10:00:00Z', status: 'saved' },
      { id: 'msg_a1', role: 'assistant', content: 'SaaS subscriptions.', created_at: '2026-03-01T10:00:02Z', status: 'saved' },
    ];

    const sendResult: CopilotSendResult = {
      id: 'msg_a2',
      role: 'assistant',
      content: 'SaaS subscriptions and consulting.',
      created_at: '2026-03-01T10:05:03Z',
      operation_status: 'completed',
      client_msg_id: 'client_op_2',
      user_message: {
        id: 'msg_q2',
        role: 'user',
        content: 'What are our revenue streams?', // Same content, different ID
        created_at: '2026-03-01T10:05:00Z'
      },
      assistant_message: {
        id: 'msg_a2',
        role: 'assistant',
        content: 'SaaS subscriptions and consulting.',
        created_at: '2026-03-01T10:05:03Z'
      }
    };

    const reconciled = reconcileSend(existing, 'temp_q2', sendResult);
    expect(reconciled).toHaveLength(4);
    expect(reconciled.filter(m => m.content === 'What are our revenue streams?')).toHaveLength(2);
  });
});

// ============================================================
// 4. UNCERTAIN SEND / TIMEOUT UI HANDLING
// ============================================================

describe('Phase 8.1: BlueprintCopilotModule ambiguous timeout and recovery UI', () => {
  it('renders "uncertain" message status with Check status, Refresh conversation, and Retry actions', () => {
    const handleSendMessage = vi.fn().mockResolvedValue(undefined);
    const handleCheckStatus = vi.fn();
    const handleRefresh = vi.fn();

    const messages: CopilotMessage[] = [
      {
        id: 'temp_uncertain_1',
        role: 'user',
        content: 'Long running query that timed out in transit',
        created_at: '2026-03-01T10:00:00Z',
        status: 'uncertain',
        client_msg_id: 'op_timeout_123'
      }
    ];

    render(
      <BlueprintCopilotModule
        project={{
          id: 'proj_1',
          name: 'Test Project',
          stage: 'Idea',
          active_module: 'bmc',
          tasks_count: 0,
          completed_tasks_count: 0,
          progress_percentage: 0,
          created_at: '2026-01-01',
          updated_at: '2026-01-01'
        }}
        messages={messages}
        isLoading={false}
        onSendMessage={handleSendMessage}
        onCheckStatus={handleCheckStatus}
        onRefreshMessages={handleRefresh}
      />
    );

    // Confirmation message shown
    expect(screen.getByText(/We could not confirm whether this response finished/i)).toBeTruthy();

    // Check status button
    const checkBtn = screen.getByRole('button', { name: /Check status/i });
    expect(checkBtn).toBeTruthy();
    fireEvent.click(checkBtn);
    expect(handleCheckStatus).toHaveBeenCalledWith('op_timeout_123');

    // Refresh conversation button
    const refreshBtn = screen.getByRole('button', { name: /Refresh conversation/i });
    expect(refreshBtn).toBeTruthy();
    fireEvent.click(refreshBtn);
    expect(handleRefresh).toHaveBeenCalled();

    // Retry button preserves client operation ID
    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    expect(retryBtn).toBeTruthy();
    fireEvent.click(retryBtn);
    expect(handleSendMessage).toHaveBeenCalledWith(
      'Long running query that timed out in transit',
      'op_timeout_123'
    );
  });
});
