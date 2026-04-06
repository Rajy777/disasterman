import type { ZoneObs, Action, PyTorchScore } from '../types'

interface Props {
  zones: ZoneObs[]
  action?: Action | null
  falseSOSZones?: string[]
  pytorchScores?: PyTorchScore[]
  compact?: boolean
}

function severityColor(z: ZoneObs, isFalseSOS: boolean, isCompleted: boolean): string {
  if (isFalseSOS) return 'border-zinc-600 bg-zinc-900 opacity-60'
  if (isCompleted) return 'border-green-600 bg-green-950'
  if (z.severity >= 0.8) return 'border-red-500 bg-red-950'
  if (z.severity >= 0.6) return 'border-orange-500 bg-orange-950'
  return 'border-yellow-600 bg-yellow-950'
}

function severityBadgeColor(z: ZoneObs): string {
  if (z.severity >= 0.8) return 'bg-red-500'
  if (z.severity >= 0.6) return 'bg-orange-500'
  return 'bg-yellow-500'
}

export function DisasterMap({ zones, action, falseSOSZones = [], pytorchScores = [], compact = false }: Props) {
  const scoreMap = Object.fromEntries(pytorchScores.map(s => [s.zone_id, s]))
  const actionTarget = action?.to_zone ?? action?.from_zone

  const pad = compact ? 'p-2' : 'p-3'
  const gap = compact ? 'gap-2' : 'gap-3'
  const cols = zones.length <= 1 ? 'grid-cols-1' :
    zones.length <= 3 ? 'grid-cols-3' :
    zones.length <= 5 ? 'grid-cols-3' :
    'grid-cols-5'

  return (
    <div className={`grid ${cols} ${gap}`}>
      {zones.map(z => {
        const isFalseSOS = falseSOSZones.includes(z.zone_id)
        const isCompleted = z.casualties_remaining === 0 && z.supply_gap === 0 && !isFalseSOS
        const isTarget = actionTarget === z.zone_id
        const score = scoreMap[z.zone_id]

        const borderClass = severityColor(z, isFalseSOS, isCompleted)
        const pulseClass = isTarget
          ? (isCompleted ? 'zone-pulse-green' : 'zone-pulse')
          : ''

        return (
          <div
            key={z.zone_id}
            className={`border rounded-lg ${pad} ${borderClass} ${pulseClass} transition-all duration-300 relative`}
          >
            {/* Zone header */}
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold text-white mono text-sm">Zone {z.zone_id}</span>
              <div className="flex gap-1 items-center">
                {z.road_blocked && !isFalseSOS && (
                  <span title="Road blocked" className="text-xs">🚧</span>
                )}
                {z.sos_active && !isFalseSOS && (
                  <span title="SOS active" className="text-xs">🆘</span>
                )}
                {isFalseSOS && (
                  <span title="False SOS" className="text-xs">⚠️</span>
                )}
                {isCompleted && (
                  <span title="Completed" className="text-xs">✅</span>
                )}
                {isTarget && action?.action === 'airlift' && (
                  <span className="text-xs">🚁</span>
                )}
              </div>
            </div>

            {isFalseSOS ? (
              <p className="text-xs text-zinc-500 italic">False SOS — no casualties</p>
            ) : (
              <>
                {!compact && (
                  <div className={`h-1 rounded mb-2 ${severityBadgeColor(z)}`}
                    style={{ width: `${Math.round(z.severity * 100)}%` }} />
                )}
                <div className="space-y-0.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Casualties</span>
                    <span className={`mono font-medium ${z.casualties_remaining > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {z.casualties_remaining}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Supply gap</span>
                    <span className={`mono font-medium ${z.supply_gap > 0 ? 'text-orange-400' : 'text-green-400'}`}>
                      {z.supply_gap}
                    </span>
                  </div>
                  {!compact && (
                    <div className="flex justify-between text-xs">
                      <span className="text-zinc-400">Teams</span>
                      <span className="mono font-medium text-blue-400">{z.teams_present}</span>
                    </div>
                  )}
                  {score && !compact && (
                    <div className="flex justify-between text-xs mt-1 pt-1 border-t border-zinc-700">
                      <span className="text-zinc-500">PyTorch</span>
                      <span className={`mono text-xs ${score.score > 0.6 ? 'text-purple-400' : score.score > 0.3 ? 'text-zinc-300' : 'text-zinc-600'}`}>
                        {score.score.toFixed(3)}
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Action highlight overlay */}
            {isTarget && (
              <div className="absolute inset-0 rounded-lg border-2 border-white/20 pointer-events-none" />
            )}
          </div>
        )
      })}
    </div>
  )
}
