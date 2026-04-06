import type { Resources } from '../types'

interface Props {
  resources: Resources
  initial?: Resources
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-zinc-400">{label}</span>
        <span className="mono text-white font-medium">{value} / {max}</span>
      </div>
      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full score-bar-fill ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function ResourceBar({ resources, initial }: Props) {
  const initTeams = initial?.teams_available ?? resources.teams_available
  const initSupply = initial?.supply_stock ?? resources.supply_stock
  const initAirlifts = initial?.airlifts_remaining ?? resources.airlifts_remaining

  const transit = Object.entries(resources.teams_in_transit ?? {})

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium">HQ Resources</h3>
      <Bar label="Rescue Teams" value={resources.teams_available} max={initTeams} color="bg-blue-500" />
      <Bar label="Supply Stock" value={resources.supply_stock} max={initSupply} color="bg-orange-500" />
      <Bar label="Airlifts" value={resources.airlifts_remaining} max={Math.max(1, initAirlifts)} color="bg-purple-500" />
      {transit.length > 0 && (
        <div className="text-xs text-zinc-400 pt-1 border-t border-zinc-800">
          In transit: {transit.map(([k, v]) => `${v} teams → ${k}`).join(' | ')}
        </div>
      )}
    </div>
  )
}
