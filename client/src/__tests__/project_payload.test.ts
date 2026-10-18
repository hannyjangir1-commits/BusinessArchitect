import { describe, expect, it } from 'vitest';
import { buildNewProjectPayload } from '../utils/projectPayload';

describe('new project setup payload', () => {
  it.each(['Idea', 'MVP', 'Post-launch', 'Growth'] as const)(
    'keeps budget and goals for the %s stage',
    (stage) => {
      const payload = buildNewProjectPayload({
        name: '  PCB Builder  ',
        stage,
        industry: '  Electronics  ',
        description: '  Collaborative design tool  ',
        targetCustomers: '  PCB designers  ',
        goals: '  Reach 10 active pilot teams  ',
        budget: '  $25,000  ',
        existingStack: { Frontend: ['React'] }
      });

      expect(payload).toMatchObject({
        name: 'PCB Builder',
        stage,
        industry: 'Electronics',
        description: 'Collaborative design tool',
        target_customers: 'PCB designers',
        goals: 'Reach 10 active pilot teams',
        budget: '$25,000'
      });
      expect(payload.existing_stack).toEqual(stage === 'Idea' ? {} : { Frontend: ['React'] });
    }
  );
});
