// "Idea / MVP" remains accepted for older local fixtures and records; the UI exposes four stages.
export type BusinessStage = 'Idea' | 'MVP' | 'Post-launch' | 'Growth' | 'Idea / MVP';

export interface User {
  id: string;
  username: string;
  email: string;
  role?: string;
  is_suspended?: boolean;
  last_active_at?: string;
  created_at: string;
}

export interface SessionData {
  user: User;
  csrf_token: string;
}

export interface Project {
  id: string;
  name: string;
  stage: BusinessStage;
  description?: string;
  industry?: string;
  target_customers?: string;
  goals?: string;
  business_context?: string;
  budget?: string;
  existing_stack?: Record<string, string[]>;
  active_module: string;
  tasks_count: number;
  completed_tasks_count: number;
  progress_percentage: number;
  generated_modules?: string[];
  created_at: string;
  updated_at: string;
}

export interface VersionItem {
  id: string;
  version_number: number;
  version_name: string;
  change_summary?: string;
  is_active: boolean;
  created_at: string;
}

export interface ModuleDetail<T = any> {
  module_type: string;
  active_version_id?: string;
  active_version_name?: string;
  active_version_number?: number;
  data?: T;
  versions: VersionItem[];
}

export interface BMCData {
  tagline?: string;
  customer_segments: string[];
  value_propositions: string[];
  channels: string[];
  customer_relationships: string[];
  revenue_streams: string[];
  key_resources: string[];
  key_activities: string[];
  key_partnerships: string[];
  cost_structure: string[];
}

export interface TechItem {
  technology: string;
  name?: string;
  category: string;
  purpose: string;
  suitability: string;
  trade_offs?: string;
  migration_risk?: string;
}

export interface TechStackData {
  summary: string;
  architecture_pattern: string;
  recommendations: TechItem[];
}

export type TechRecommendation = TechItem;

export interface ValidationRisk {
  risk: string;
  severity: 'High' | 'Medium' | 'Low';
  mitigation: string;
}

export interface ValidationExperiment {
  experiment: string;
  metric: string;
  target_criteria: string;
}

export interface IdeaValidatorData {
  overall_viability_score: number;
  problem_clarity: string;
  customer_fit: string;
  value_proposition: string;
  market_assumptions: string[];
  differentiation: string;
  feasibility: string;
  risks: ValidationRisk[];
  validation_experiments: ValidationExperiment[];
  suggested_next_actions: string[];
}

export interface CompetitorProfile {
  name: string;
  strengths: string[];
  weaknesses: string[];
  pricing_model: string;
  market_share_estimate: string;
}

export interface MarketResearchData {
  provenance_note: string;
  target_market_size: string;
  customer_needs: string[];
  competitor_profiles: CompetitorProfile[];
  competitive_positioning: string;
  differentiation_factors: string[];
  opportunities: string[];
  threats: string[];
  research_gaps: string[];
}

export interface RoadmapTask {
  id: string;
  project_id: string;
  task_code: string;
  phase: string;
  title: string;
  description?: string;
  timeline: string;
  start_date: string;
  end_date: string;
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
  status: 'Pending' | 'Ongoing' | 'In Progress' | 'Finished';
  dependencies: string[];
  deliverables?: string;
  effort?: string;
  created_at: string;
  updated_at: string;
}

export interface RoadmapSummary {
  milestone_30_progress: number;
  milestone_30_completed: number;
  milestone_30_total: number;
  milestone_60_progress: number;
  milestone_60_completed: number;
  milestone_60_total: number;
  milestone_90_progress: number;
  milestone_90_completed: number;
  milestone_90_total: number;
  total_tasks: number;
  completed_tasks: number;
  overall_progress: number;
}

export type RoadmapChecklistStatus = 'Not started' | 'In progress' | 'Completed' | 'Not applicable';

export interface RoadmapChecklistItem {
  item: string;
  status: RoadmapChecklistStatus;
}

export interface RoadmapPlanningInputs {
  start_date: string;
  horizon_weeks: number;
  checklist: RoadmapChecklistItem[];
  completed_work: string;
  in_progress_work: string;
  team_capacity: string;
  constraints: string;
  target_outcome: string;
  custom_items: string[];
}

export interface CopilotMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}
