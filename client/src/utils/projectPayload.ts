import { BusinessStage } from '../types';

export interface NewProjectPayloadInput {
  name: string;
  stage: BusinessStage;
  industry: string;
  description: string;
  targetCustomers: string;
  goals: string;
  budget: string;
  existingStack: Record<string, string[]>;
}

export function buildNewProjectPayload(input: NewProjectPayloadInput) {
  return {
    name: input.name.trim(),
    stage: input.stage,
    industry: input.industry.trim(),
    description: input.description.trim(),
    target_customers: input.targetCustomers.trim(),
    goals: input.goals.trim(),
    budget: input.budget.trim() || undefined,
    existing_stack: input.stage !== 'Idea' ? input.existingStack : {}
  };
}
