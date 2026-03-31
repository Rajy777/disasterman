import type { Action, PyTorchScore, ZoneObs } from '../types'
import { BENGALURU_CENTER, getZoneGeo } from '../data/bengaluruZones'

interface Props {
  zones: ZoneObs[]
  action?: Action | null
  falseSOSZones?: string[]
  pytorchScores?: PyTorchScore[]
  compact?: boolean
}

type ProjectedPoint = {
  x: number
  y: number
}

function markerColor(zone: ZoneObs, isFalseSOS: boolean, isCompleted: boolean): string {
  if (isFalseSOS) return '#71717a'
  if (isCompleted) return '#22c55e'
  if (zone.severity >= 0.8) return '#ef4444'
  if (zone.severity >= 0.6) return '#f59e0b'
  return '#eab308'
}

function iconForAction(action?: Action | null): string {
  if (!action) return 'HQ'
  if (action.action === 'deploy_team') return 'TEAM'
  if (action.action === 'send_supplies') return 'SUPPLY'
  if (action.action === 'airlift') return 'AIRLIFT'
  if (action.action === 'recall_team') return 'RECALL'
  return 'WAIT'
}

function clampPercent(value: number): number {
  return Math.max(4, Math.min(96, value))
}

export function DisasterMap({ zones, action, falseSOSZones = [], pytorchScores = [], compact = false }: Props) {
  const scoreMap = Object.fromEntries(pytorchScores.map((score) => [score.zone_id, score]))
  const actionTarget = action?.to_zone ?? action?.from_zone
  const targetGeo = actionTarget ? getZoneGeo(actionTarget) : null
  const routeColor = action?.action === 'airlift' ? '#a855f7' : action?.action === 'send_supplies' ? '#f97316' : '#38bdf8'
  const mapHeight = compact ? 250 : 430

  const allGeos = [
    ...zones.map((zone) => getZoneGeo(zone.zone_id)),
    { zone_id: 'HQ', label: 'HQ', area: 'Command Center', lat: BENGALURU_CENTER[0], lng: BENGALURU_CENTER[1] },
    ...(targetGeo ? [{ zone_id: actionTarget ?? 'target', label: 'Target', area: 'Selected action target', lat: targetGeo.lat, lng: targetGeo.lng }] : []),
  ]

  const latitudes = allGeos.map((geo) => geo.lat)
  const longitudes = allGeos.map((geo) => geo.lng)
  const minLat = Math.min(...latitudes)
  const maxLat = Math.max(...latitudes)
  const minLng = Math.min(...longitudes)
  const maxLng = Math.max(...longitudes)
  const latSpan = Math.max(0.01, maxLat - minLat)
  const lngSpan = Math.max(0.01, maxLng - minLng)
  const latPad = latSpan * 0.15
  const lngPad = lngSpan * 0.15

  const project = (lat: number, lng: number): ProjectedPoint => ({
    x: clampPercent(((lng - (minLng - lngPad)) / (lngSpan + lngPad * 2)) * 100),
    y: clampPercent((1 - ((lat - (minLat - latPad)) / (latSpan + latPad * 2))) * 100),
  })

  const hq = project(BENGALURU_CENTER[0], BENGALURU_CENTER[1])
  const targetPoint = targetGeo ? project(targetGeo.lat, targetGeo.lng) : null

  return (
    <div className="rounded-xl overflow-hidden border border-zinc-800 bg-zinc-950 relative">
      <div
        className="relative w-full"
        style={{
          height: mapHeight,
          background:
            'radial-gradient(circle at 20% 20%, rgba(59,130,246,0.18), transparent 30%), radial-gradient(circle at 80% 15%, rgba(249,115,22,0.12), transparent 28%), linear-gradient(180deg, #0f172a 0%, #111827 55%, #0b1220 100%)',
        }}
      >
        <div
          className="absolute inset-0 opacity-25"
          style={{
            backgroundImage:
              'linear-gradient(rgba(148,163,184,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.12) 1px, transparent 1px)',
            backgroundSize: compact ? '28px 28px' : '36px 36px',
          }}
        />

        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
          {targetPoint ? (
            <line
              x1={hq.x}
              y1={hq.y}
              x2={targetPoint.x}
              y2={targetPoint.y}
              stroke={routeColor}
              strokeWidth="1"
              strokeDasharray="3 2"
              opacity="0.95"
            />
          ) : null}

          <circle cx={hq.x} cy={hq.y} r="1.8" fill="#f8fafc" opacity="0.9" />
          <text x={hq.x + 1.4} y={hq.y - 1.4} fill="#e2e8f0" fontSize="3">HQ</text>

          {zones.map((zone) => {
            const geo = getZoneGeo(zone.zone_id)
            const point = project(geo.lat, geo.lng)
            const isFalseSOS = falseSOSZones.includes(zone.zone_id)
            const isCompleted = zone.casualties_remaining === 0 && zone.supply_gap === 0 && !isFalseSOS
            const isCritical = zone.severity >= 0.8 && !isFalseSOS && !isCompleted
            const isTarget = actionTarget === zone.zone_id
            const baseColor = markerColor(zone, isFalseSOS, isCompleted)
            const score = scoreMap[zone.zone_id]
            const label = `Zone ${zone.zone_id} (${geo.area})`
            const details = [
              `Severity ${zone.severity.toFixed(2)}`,
              `${zone.casualties_remaining} casualties`,
              `${zone.supply_gap} supply gap`,
              `${zone.teams_present} teams`,
              zone.road_blocked ? 'Road blocked' : 'Road open',
              score ? `PyTorch ${score.score.toFixed(3)}` : null,
              isFalseSOS ? 'False SOS suspect' : null,
            ].filter(Boolean).join(' | ')

            return (
              <g key={zone.zone_id}>
                <title>{`${label}: ${details}`}</title>
                {isCritical ? (
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={compact ? '3.4' : '3.8'}
                    fill={baseColor}
                    opacity="0.15"
                  />
                ) : null}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={isTarget ? (compact ? '2.6' : '2.9') : (compact ? '2.1' : '2.4')}
                  fill={baseColor}
                  stroke={isTarget ? '#ffffff' : '#111827'}
                  strokeWidth={isTarget ? '0.8' : '0.5'}
                  opacity={isFalseSOS ? '0.45' : '0.95'}
                />
                <text
                  x={point.x}
                  y={point.y + (compact ? 6 : 5.5)}
                  fill="#f8fafc"
                  fontSize={compact ? '3' : '2.8'}
                  textAnchor="middle"
                >
                  {zone.zone_id}
                </text>
              </g>
            )
          })}
        </svg>

        {targetPoint ? (
          <div
            className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/30 bg-zinc-950/90 px-2 py-1 text-[10px] text-zinc-100 shadow-lg"
            style={{ left: `${targetPoint.x}%`, top: `${Math.max(8, targetPoint.y - 7)}%` }}
          >
            {iconForAction(action)}
          </div>
        ) : null}

        <div className="absolute left-3 top-3 rounded-lg border border-zinc-800 bg-zinc-950/90 px-3 py-2 text-[11px] text-zinc-300">
          Bengaluru field overlay
        </div>

        <div className="absolute right-2 bottom-2 bg-zinc-950/90 border border-zinc-800 rounded-lg p-2 text-[11px] text-zinc-300 space-y-1">
          <div className="font-semibold text-zinc-200">Legend</div>
          <div><span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-2" />Critical</div>
          <div><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-2" />Warning</div>
          <div><span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-2" />Resolved</div>
          <div><span className="inline-block w-2 h-2 rounded-full bg-zinc-500 mr-2" />False SOS</div>
        </div>
      </div>
    </div>
  )
}
