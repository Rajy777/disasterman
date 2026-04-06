import type { Action, Observation, Reasoning } from '../types'

interface Props {
  observation: Observation
  reasoning: Reasoning
  currentAction: Action | null
  taskName: string
}

function summarizeObservation(observation: Observation): string {
  const activeZones = observation.zones.filter((zone) => zone.casualties_remaining > 0 || zone.supply_gap > 0)
  const blocked = activeZones.filter((zone) => zone.road_blocked).map((zone) => zone.zone_id)
  const critical = activeZones
    .filter((zone) => zone.severity >= 0.75)
    .map((zone) => zone.zone_id)

  const parts = [
    `${activeZones.length} active zone${activeZones.length === 1 ? '' : 's'}`,
    critical.length > 0 ? `critical: ${critical.join(', ')}` : 'no critical zones',
    blocked.length > 0 ? `blocked: ${blocked.join(', ')}` : 'roads mostly open',
  ]

  return parts.join(' | ')
}

export function CopilotQaPanel({ observation, reasoning, currentAction, taskName }: Props) {
  const actionLabel = currentAction
    ? `${currentAction.action}${currentAction.to_zone ? ` -> ${currentAction.to_zone}` : currentAction.from_zone ? ` <- ${currentAction.from_zone}` : ''}`
    : 'No action selected'

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium">Quick QA</h3>
        <span className="text-xs text-zinc-400">{taskName}</span>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-300">
        {summarizeObservation(observation)}
      </div>

      <div className="grid grid-cols-1 gap-2 text-xs text-zinc-400">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
          <div className="text-zinc-500 mb-1">Current action</div>
          <div className="text-zinc-200">{actionLabel}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
          <div className="text-zinc-500 mb-1">Triage summary</div>
          <div>{reasoning.triage_summary || 'No triage summary yet.'}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
          <div className="text-zinc-500 mb-1">Planner summary</div>
          <div>{reasoning.plan_decision || 'No planner summary yet.'}</div>
        </div>
      </div>
    </div>
  )
}
