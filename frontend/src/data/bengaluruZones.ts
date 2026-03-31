export interface ZoneGeo {
  zone_id: string
  label: string
  area: string
  lat: number
  lng: number
}

export const BENGALURU_CENTER: [number, number] = [12.9716, 77.5946]

export const ZONE_GEO: Record<string, ZoneGeo> = {
  A: { zone_id: 'A', label: 'Majestic Command', area: 'Majestic / Anand Rao', lat: 12.9762, lng: 77.5713 },
  B: { zone_id: 'B', label: 'Koramangala South', area: 'Koramangala 4th Block', lat: 12.9352, lng: 77.6245 },
  C: { zone_id: 'C', label: 'Whitefield East', area: 'ITPL / Whitefield', lat: 12.9698, lng: 77.7499 },
  D: { zone_id: 'D', label: 'Yelahanka North', area: 'Yelahanka New Town', lat: 13.1005, lng: 77.5963 },
  E: { zone_id: 'E', label: 'Bellandur Lake', area: 'Bellandur / ORR', lat: 12.9279, lng: 77.6729 },
  F: { zone_id: 'F', label: 'Rajajinagar West', area: 'Rajajinagar', lat: 12.9918, lng: 77.5567 },
  G: { zone_id: 'G', label: 'Hebbal Junction', area: 'Hebbal', lat: 13.0358, lng: 77.597 },
  H: { zone_id: 'H', label: 'Electronic City', area: 'Phase 1', lat: 12.8452, lng: 77.6631 },
  I: { zone_id: 'I', label: 'Indiranagar Core', area: '100 Feet Road', lat: 12.9784, lng: 77.6408 },
  J: { zone_id: 'J', label: 'Jayanagar South', area: '4th Block', lat: 12.925, lng: 77.5938 },
}

export function getZoneGeo(zoneId: string): ZoneGeo {
  return ZONE_GEO[zoneId] ?? {
    zone_id: zoneId,
    label: `Zone ${zoneId}`,
    area: 'Bengaluru',
    lat: BENGALURU_CENTER[0],
    lng: BENGALURU_CENTER[1],
  }
}

