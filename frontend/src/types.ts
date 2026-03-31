export interface ZoneObs {
  zone_id: string
  casualties_remaining: number
  supply_gap: number
  severity: number
  road_blocked: boolean
  teams_present: number
  sos_active: boolean
}

export interface Resources {
  teams_available: number
  supply_stock: number
  airlifts_remaining: number
  teams_in_transit: Record<string, number>
}

export interface Observation {
  zones: ZoneObs[]
  resources: Resources
  step_number: number
  steps_remaining: number
  weather: 'clear' | 'storm' | 'flood'
  last_action_result: string
}

export interface Action {
  action: string
  to_zone?: string
  from_zone?: string
  units?: number
  type?: string
}

export interface PyTorchScore {
  zone_id: string
  score: number
  is_false_sos_suspect: boolean
}

export type StageName = 'pytorch' | 'triage' | 'planner' | 'action'

export interface TriageAlert {
  zone_id: string
  steps_until_deadline?: number
}

export interface TriageDetails {
  false_sos_suspects: string[]
  deadline_alerts: TriageAlert[]
  reserve_airlift_for?: string | null
  confidence?: number
  priority_zones?: string[]
}

export interface PlannerStep {
  step_offset: number
  action: string
  zone?: string | null
  units?: number | null
  reason?: string
}

export interface PlannerDetails {
  primary_zone?: string | null
  primary_action_type?: string
  critical_decision?: string
  step_plan?: PlannerStep[]
}

export interface ValidatorDetails {
  valid: boolean
  fallback_used: boolean
  constraints_checked: string[]
}

export interface Reasoning {
  pytorch_scores: PyTorchScore[]
  triage_summary: string
  plan_decision: string
  action_rationale: string
  triage?: TriageDetails
  plan?: PlannerDetails
  validator?: ValidatorDetails
  stage_timings_ms?: Partial<Record<StageName, number>>
  rejected_actions?: string[]
}

export interface SimStep {
  step: number
  observation: Observation
  action: Action
  reward: number
  reasoning: Reasoning
}

export interface SimResult {
  task_id: string
  agent: string
  final_score: number | null
  cumulative_reward: number
  steps_taken: number
  steps: SimStep[]
  note?: string
}

export interface CompareResult {
  task_id: string
  agents: {
    random?: SimResult
    greedy?: SimResult
    ai_4stage?: SimResult
  }
}

export interface TaskInfo {
  task_id: string
  name: string
  difficulty: string
  max_steps: number
  zones: number
  resources: Record<string, number>
  false_sos_zones: string[]
}

export interface StreamMetaEvent {
  task_id: string
  agent: string
  model: string
}

export interface StreamStageEvent {
  step: number
  stage: StageName
  duration_ms: number
  summary: string
  payload: unknown
}

export interface StreamDoneEvent {
  task_id: string
  agent: string
  model?: string
  final_score: number
  cumulative_reward: number
  steps_taken: number
}
