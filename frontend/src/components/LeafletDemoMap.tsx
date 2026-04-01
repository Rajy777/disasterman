import { useEffect } from 'react'
import {
  Circle,
  CircleMarker,
  MapContainer,
  Pane,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet'
import type { LatLngBoundsExpression, LatLngExpression, LatLngTuple } from 'leaflet'
import type {
  DemoLocation,
  DemoMapOverlay,
  DemoMapState,
  DemoResourceMovement,
  DemoResourcePosition,
  DemoScenarioDetail,
} from '../types'

interface Props {
  scenario: DemoScenarioDetail
  mapState?: DemoMapState | null
}

function MapViewport({
  bounds,
  center,
  zoom,
}: {
  bounds: LatLngTuple[]
  center: LatLngTuple
  zoom: number
}) {
  const map = useMap()

  useEffect(() => {
    if (bounds.length >= 2) {
      map.fitBounds(bounds as LatLngBoundsExpression, { padding: [28, 28] })
      return
    }
    map.setView(center as LatLngExpression, zoom)
  }, [map, bounds, center, zoom])

  return null
}

function overlayColor(overlay: DemoMapOverlay): string {
  if (overlay.kind === 'flood_zone') return '#38bdf8'
  if (overlay.kind === 'fire_zone') return '#f97316'
  if (overlay.kind === 'collapse_zone') return '#facc15'
  if (overlay.kind === 'blocked_corridor') return '#ef4444'
  if (overlay.kind === 'false_alert') return '#a1a1aa'
  return '#22c55e'
}

function overlayFillOpacity(overlay: DemoMapOverlay): number {
  if (overlay.kind === 'blocked_corridor') return 0
  if (overlay.kind === 'false_alert') return 0.12
  return overlay.severity === 'high' ? 0.24 : overlay.severity === 'medium' ? 0.18 : 0.12
}

function locationStyle(location: DemoLocation) {
  if (location.kind === 'hq') return { color: '#f8fafc', radius: 8, fillOpacity: 0.9 }
  if (location.kind === 'false_alert') return { color: '#71717a', radius: 6, fillOpacity: 0.65 }
  if (location.kind === 'medical') return { color: '#84cc16', radius: 6, fillOpacity: 0.86 }
  if (location.kind === 'support') return { color: '#10b981', radius: 6, fillOpacity: 0.84 }
  return { color: '#fb7185', radius: 7, fillOpacity: 0.82 }
}

function resourceStyle(resource: DemoResourcePosition) {
  if (resource.kind === 'hq') return { color: '#e2e8f0', radius: 10, fillOpacity: 0.92 }
  if (resource.kind === 'airlift') return { color: '#c084fc', radius: 6 + Math.min(resource.count, 3), fillOpacity: 0.9 }
  if (resource.kind === 'supply') return { color: '#f97316', radius: 5 + Math.min(resource.count, 4), fillOpacity: 0.88 }
  return { color: resource.status === 'deployed' ? '#38bdf8' : '#60a5fa', radius: 5 + Math.min(resource.count, 4), fillOpacity: 0.88 }
}

function interpolatePoint(path: LatLngTuple[], progress: number): LatLngTuple {
  if (path.length <= 1) return path[0] ?? [12.9716, 77.5946]

  const clamped = Math.max(0, Math.min(1, progress))
  const lengths: number[] = []
  let totalLength = 0

  for (let index = 0; index < path.length - 1; index += 1) {
    const start = path[index]
    const end = path[index + 1]
    const length = Math.hypot(end[0] - start[0], end[1] - start[1])
    lengths.push(length)
    totalLength += length
  }

  if (totalLength === 0) return path[path.length - 1]

  let targetLength = totalLength * clamped
  for (let index = 0; index < lengths.length; index += 1) {
    if (targetLength > lengths[index]) {
      targetLength -= lengths[index]
      continue
    }
    const start = path[index]
    const end = path[index + 1]
    const ratio = lengths[index] === 0 ? 0 : targetLength / lengths[index]
    return [
      start[0] + (end[0] - start[0]) * ratio,
      start[1] + (end[1] - start[1]) * ratio,
    ]
  }

  return path[path.length - 1]
}

function routeStyle(mode: 'road' | 'air') {
  if (mode === 'air') {
    return { color: '#a855f7', weight: 2, opacity: 0.28, dashArray: '6 6' }
  }
  return { color: '#475569', weight: 2.5, opacity: 0.35, dashArray: '4 8' }
}

function MovementMarkers({ movements }: { movements: DemoResourceMovement[] }) {
  return (
    <>
      {movements.map((movement) => {
        const point = interpolatePoint(movement.path as LatLngTuple[], movement.progress)
        return (
          <CircleMarker
            key={movement.movement_id}
            center={point}
            radius={7}
            pathOptions={{
              color: '#f8fafc',
              weight: 2,
              fillColor: movement.color,
              fillOpacity: 0.95,
            }}
          >
            <Tooltip direction="top" opacity={0.96}>
              <div className="space-y-1">
                <div className="font-semibold">{movement.label}</div>
                <div>{movement.note}</div>
              </div>
            </Tooltip>
          </CircleMarker>
        )
      })}
    </>
  )
}

export function LeafletDemoMap({ scenario, mapState }: Props) {
  const overlays = (mapState?.overlays ?? scenario.overlays).filter((overlay) => overlay.active)
  const resources = mapState?.resource_positions ?? []
  const movements = mapState?.recent_movements ?? []
  const actionTarget = mapState?.action_target ?? null
  const activeLocation = actionTarget
    ? scenario.locations.find((location) => location.zone_id === actionTarget || location.node_id === actionTarget) ?? null
    : null

  return (
    <div className="relative overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950">
      <div className="absolute inset-x-0 top-0 z-[500] flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 bg-zinc-950/92 px-4 py-3 backdrop-blur">
        <div>
          <div className="text-[11px] uppercase tracking-[0.28em] text-zinc-500">Live {scenario.disaster_type} Demo</div>
          <div className="text-sm font-semibold text-white">{scenario.title}</div>
        </div>
        <div className="max-w-sm text-right text-xs text-zinc-300">
          {mapState?.step_label ?? `HQ anchored near ${scenario.locations.find((location) => location.node_id === scenario.hq_node_id)?.area ?? 'Electronic City'}.`}
        </div>
      </div>

      <MapContainer
        center={scenario.center}
        zoom={scenario.zoom}
        scrollWheelZoom
        className="h-[560px] w-full"
      >
        <MapViewport bounds={scenario.bounds} center={scenario.center} zoom={scenario.zoom} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <Pane name="scenario-routes" style={{ zIndex: 360 }}>
          {scenario.routes.map((route) => (
            <Polyline
              key={route.route_id}
              positions={route.path}
              pathOptions={routeStyle(route.mode)}
            >
              <Tooltip direction="center" sticky opacity={0.9}>
                {route.label}
              </Tooltip>
            </Polyline>
          ))}
        </Pane>

        <Pane name="overlays" style={{ zIndex: 390 }}>
          {overlays.map((overlay) => {
            const color = overlayColor(overlay)
            if (overlay.geometry === 'polygon') {
              return (
                <Polygon
                  key={overlay.overlay_id}
                  positions={overlay.coordinates}
                  pathOptions={{
                    color,
                    weight: 2,
                    opacity: 0.7,
                    fillColor: color,
                    fillOpacity: overlayFillOpacity(overlay),
                  }}
                >
                  <Popup>
                    <div className="space-y-1 text-sm">
                      <div className="font-semibold">{overlay.label}</div>
                      <div>{overlay.note}</div>
                    </div>
                  </Popup>
                </Polygon>
              )
            }
            if (overlay.geometry === 'polyline') {
              return (
                <Polyline
                  key={overlay.overlay_id}
                  positions={overlay.coordinates}
                  pathOptions={{
                    color,
                    weight: 4,
                    opacity: 0.82,
                    dashArray: overlay.kind === 'blocked_corridor' ? '8 10' : undefined,
                  }}
                >
                  <Popup>
                    <div className="space-y-1 text-sm">
                      <div className="font-semibold">{overlay.label}</div>
                      <div>{overlay.note}</div>
                    </div>
                  </Popup>
                </Polyline>
              )
            }
            return (
              <Circle
                key={overlay.overlay_id}
                center={overlay.coordinates[0]}
                radius={overlay.radius_m ?? 380}
                pathOptions={{
                  color,
                  weight: 2,
                  opacity: 0.72,
                  fillColor: color,
                  fillOpacity: overlayFillOpacity(overlay),
                }}
              >
                <Popup>
                  <div className="space-y-1 text-sm">
                    <div className="font-semibold">{overlay.label}</div>
                    <div>{overlay.note}</div>
                  </div>
                </Popup>
              </Circle>
            )
          })}
        </Pane>

        <Pane name="action-target" style={{ zIndex: 430 }}>
          {activeLocation ? (
            <Circle
              center={activeLocation.coordinates}
              radius={680}
              pathOptions={{
                color: '#f8fafc',
                weight: 2,
                opacity: 0.85,
                fillOpacity: 0,
                dashArray: '10 10',
              }}
            />
          ) : null}
        </Pane>

        <Pane name="locations" style={{ zIndex: 440 }}>
          {scenario.locations.map((location) => {
            const style = locationStyle(location)
            return (
              <CircleMarker
                key={location.node_id}
                center={location.coordinates}
                radius={style.radius}
                pathOptions={{
                  color: '#020617',
                  weight: 1.5,
                  fillColor: style.color,
                  fillOpacity: style.fillOpacity,
                }}
              >
                <Tooltip direction="top" opacity={0.96}>
                  <div className="space-y-1 text-xs">
                    <div className="font-semibold">{location.label}</div>
                    <div>{location.area}</div>
                  </div>
                </Tooltip>
                <Popup>
                  <div className="space-y-1 text-sm">
                    <div className="font-semibold">{location.label}</div>
                    <div className="text-zinc-600">{location.area}</div>
                    <div>{location.description}</div>
                  </div>
                </Popup>
              </CircleMarker>
            )
          })}
        </Pane>

        <Pane name="resource-paths" style={{ zIndex: 470 }}>
          {movements.map((movement) => (
            <Polyline
              key={movement.movement_id}
              positions={movement.path}
              pathOptions={{
                color: movement.color,
                weight: 4,
                opacity: 0.92,
                dashArray: movement.kind === 'airlift' ? '8 10' : undefined,
              }}
            >
              <Tooltip direction="center" opacity={0.95} sticky>
                <div className="space-y-1 text-xs">
                  <div className="font-semibold">{movement.label}</div>
                  <div>{movement.note}</div>
                </div>
              </Tooltip>
            </Polyline>
          ))}
        </Pane>

        <Pane name="movement-markers" style={{ zIndex: 490 }}>
          <MovementMarkers movements={movements} />
        </Pane>

        <Pane name="resources" style={{ zIndex: 520 }}>
          {resources.map((resource) => {
            const style = resourceStyle(resource)
            return (
              <CircleMarker
                key={resource.resource_id}
                center={resource.coordinates}
                radius={style.radius}
                pathOptions={{
                  color: '#ffffff',
                  weight: resource.kind === 'hq' ? 2 : 1.6,
                  fillColor: style.color,
                  fillOpacity: style.fillOpacity,
                }}
              >
                <Tooltip direction="top" opacity={0.96}>
                  <div className="space-y-1 text-xs">
                    <div className="font-semibold">{resource.label}</div>
                    <div>{resource.count > 1 ? `${resource.count} units` : '1 unit'}</div>
                  </div>
                </Tooltip>
                <Popup>
                  <div className="space-y-1 text-sm">
                    <div className="font-semibold">{resource.label}</div>
                    <div>Count: {resource.count}</div>
                    <div>Status: {resource.status}</div>
                    {resource.assigned_zone ? <div>Assigned zone: {resource.assigned_zone}</div> : null}
                    <div>{resource.note}</div>
                  </div>
                </Popup>
              </CircleMarker>
            )
          })}
        </Pane>
      </MapContainer>

      <div className="pointer-events-none absolute bottom-4 left-4 z-[500] flex max-w-sm flex-wrap gap-2">
        {[
          { label: 'HQ / control', color: '#e2e8f0' },
          { label: 'Incident node', color: '#fb7185' },
          { label: 'Support hub', color: '#10b981' },
          { label: 'Medical node', color: '#84cc16' },
          { label: 'False alert', color: '#71717a' },
          { label: 'Relief stock', color: '#f97316' },
          { label: 'Rescue teams', color: '#38bdf8' },
          { label: 'Airlift', color: '#c084fc' },
        ].map((item) => (
          <span
            key={item.label}
            className="rounded-full border border-zinc-700 bg-zinc-950/90 px-3 py-1 text-[11px] text-zinc-200 shadow"
          >
            <span
              className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle"
              style={{ backgroundColor: item.color }}
            />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  )
}
