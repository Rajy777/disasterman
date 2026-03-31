import type { Reasoning, StageName, StreamStageEvent } from '../types'

interface Props {
  reasoning: Reasoning
  agent: string
  activeStage?: StageName | null
  stageEvents?: StreamStageEvent[]
}

function badgeClass(active: boolean): string {
  return active
    ? 'bg-blue-900/70 border-blue-500 text-blue-200 shadow-[0_0_20px_rgba(59,130,246,0.3)]'
    : 'bg-zinc-900 border-zinc-800 text-zinc-400'
}

function stageSummary(stage: StageName, reasoning: Reasoning): string {
  if (stage === 'pytorch') {
    const top = [...reasoning.pytorch_scores]
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map((s) => `${s.zone_id}:${s.score.toFixed(2)}`)
    return top.length > 0 ? `Top activations → ${top.join(', ')}` : 'No zone scores yet.'
  }
  if (stage === 'triage') return reasoning.triage_summary || 'Triage analysis pending.'
  if (stage === 'planner') return reasoning.plan_decision || 'Planner has no decision yet.'
  return reasoning.action_rationale || 'Action rationale pending.'
}

const STAGES: Array<{ key: StageName; title: string; icon: string }> = [
  { key: 'pytorch', title: 'PyTorch ZoneScorer', icon: '🧠' },
  { key: 'triage', title: 'Triage Agent', icon: '🔍' },
  { key: 'planner', title: 'Planner Agent', icon: '📋' },
  { key: 'action', title: 'Action Agent', icon: '✅' },
]

export function AgentReasoningPanel({ reasoning, agent, activeStage = null, stageEvents = [] }: Props) {
  const triageDetails = reasoning.triage
  const planDetails = reasoning.plan
  const validator = reasoning.validator
  const durations = reasoning.stage_timings_ms

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium">Agent Thinking Theater</h3>
        <span className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded-full">{agent}</span>
      </div>

      <div className="space-y-2">
        {STAGES.map((stage, index) => {
          const active = activeStage === stage.key
          const ev = stageEvents.find((e) => e.stage === stage.key)
          const durationMs = ev?.duration_ms ?? durations?.[stage.key]
          return (
            <div
              key={stage.key}
              className={`border rounded-lg p-2 transition-all duration-300 ${badgeClass(active)}`}
              style={{ transitionDelay: `${index * 80}ms` }}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="text-xs font-medium">
                  {stage.icon} {stage.title}
                </div>
                <div className="text-[10px] mono">
                  {typeof durationMs === 'number' ? `${durationMs.toFixed(1)} ms` : '—'}
                </div>
              </div>
              <div className="text-[11px] leading-relaxed">
                {ev?.summary || stageSummary(stage.key, reasoning)}
              </div>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 gap-2 text-xs">
        <div className="border border-zinc-800 rounded-lg p-2 bg-zinc-950">
          <div className="text-zinc-500 mb-1">False-SOS Confidence</div>
          <div className="flex items-center justify-between">
            <span className="mono">{Math.round((triageDetails?.confidence ?? 0.5) * 100)}%</span>
            <span className="text-zinc-400">{triageDetails?.false_sos_suspects?.join(', ') || 'none'}</span>
          </div>
        </div>

        <div className="border border-zinc-800 rounded-lg p-2 bg-zinc-950">
          <div className="text-zinc-500 mb-1">Planner Trade-off</div>
          <div className="text-zinc-300">{planDetails?.critical_decision || reasoning.plan_decision || 'No trade-off summary yet.'}</div>
          {planDetails?.step_plan?.length ? (
            <div className="text-zinc-500 mt-1 mono">
              {planDetails.step_plan.slice(0, 3).map((p) => `T+${p.step_offset}:${p.action}@${p.zone ?? 'HQ'}`).join(' | ')}
            </div>
          ) : null}
        </div>

        <div className="border border-zinc-800 rounded-lg p-2 bg-zinc-950">
          <div className="text-zinc-500 mb-1">Validator Checklist</div>
          <div className="text-zinc-300">
            {(validator?.constraints_checked ?? ['zone_exists', 'resource_limits', 'road_access']).join(', ')}
          </div>
          <div className="mt-1 text-zinc-500">
            {validator?.fallback_used ? 'Fallback heuristic used for safety.' : 'Primary plan passed validation.'}
          </div>
        </div>
      </div>
    </div>
  )
}

