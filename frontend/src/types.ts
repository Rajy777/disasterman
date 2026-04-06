export type AgentId = 'greedy' | 'random' | 'ai_4stage'

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
  note?: string
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

export interface DemoScenarioSummary {
  scenario_id: string
  title: string
  disaster_type: string
  narrative: string
  duration_steps: number
  default_agent: AgentId
  tags: string[]
  center: [number, number]
  zoom: number
}

export interface DemoLocation {
  node_id: string
  label: string
  area: string
  coordinates: [number, number]
  kind: 'hq' | 'incident' | 'support' | 'false_alert' | 'medical' | 'staging'
  description: string
  zone_id?: string | null
}

export interface DemoRoute {
  route_id: string
  label: string
  mode: 'road' | 'air'
  from_node: string
  to_node: string
  path: [number, number][]
  zone_id?: string | null
}

export interface DemoMapOverlay {
  overlay_id: string
  label: string
  kind: 'flood_zone' | 'fire_zone' | 'collapse_zone' | 'blocked_corridor' | 'false_alert' | 'support_zone'
  geometry: 'polygon' | 'polyline' | 'circle'
  coordinates: [number, number][]
  radius_m?: number | null
  severity: 'low' | 'medium' | 'high'
  active: boolean
  note: string
  zone_id?: string | null
}

export interface DemoScenarioDetail extends DemoScenarioSummary {
  bounds: [number, number][]
  hq_node_id: string
  allowed_agents: AgentId[]
  locations: DemoLocation[]
  routes: DemoRoute[]
  overlays: DemoMapOverlay[]
}

export interface DemoResourcePosition {
  resource_id: string
  kind: 'hq' | 'team' | 'supply' | 'airlift'
  label: string
  coordinates: [number, number]
  count: number
  status: 'ready' | 'deployed' | 'support' | 'airborne'
  assigned_zone?: string | null
  note: string
}

export interface DemoResourceMovement {
  movement_id: string
  kind: 'team' | 'supply' | 'airlift'
  label: string
  route_id: string
  path: [number, number][]
  from_node: string
  to_node: string
  units: number
  progress: number
  color: string
  action: string
  note: string
}

export interface DemoMapState {
  center: [number, number]
  zoom: number
  bounds: [number, number][]
  overlays: DemoMapOverlay[]
  resource_positions: DemoResourcePosition[]
  recent_movements: DemoResourceMovement[]
  action_target?: string | null
  step_label: string
}

export interface DemoStep extends SimStep {
  map_state: DemoMapState
}

export interface DemoRunResult {
  scenario: DemoScenarioDetail
  agent: string
  model?: string | null
  final_score: number | null
  cumulative_reward: number
  steps_taken: number
  steps: DemoStep[]
  note?: string | null
}

export interface DemoStreamMetaEvent {
  scenario: DemoScenarioDetail
  scenario_id: string
  agent: AgentId
  model: string
}

export interface DemoStreamDoneEvent {
  scenario_id: string
  agent: AgentId
  model?: string
  final_score: number
  cumulative_reward: number
  steps_taken: number
  note?: string | null
}

export interface DemoScenarioCatalog {
  scenarios: DemoScenarioSummary[]
  available_agents: AgentId[]
  ai_available: boolean
}
