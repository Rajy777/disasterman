import type {
  SimResult,
  CompareResult,
  TaskInfo,
  SimStep,
  StreamDoneEvent,
  StreamMetaEvent,
  StreamStageEvent,
} from '../types'

const rawEnvBase = import.meta.env.VITE_API_URL?.trim()
const normalizedEnvBase = rawEnvBase ? rawEnvBase.replace(/\/+$/, '') : ''
const BASE = normalizedEnvBase || (import.meta.env.PROD ? '/api' : 'http://localhost:7860')

export class ApiError extends Error {
  status: number
  body: string
  url: string

  constructor(status: number, body: string, url: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.url = url
  }
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${BASE}${normalizedPath}`
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = buildUrl(path)

  try {
    const res = await fetch(url, options)
    if (!res.ok) {
      const err = await res.text()
      throw new ApiError(res.status, err, url, `API error ${res.status}: ${err}`)
    }
    return res.json() as Promise<T>
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    const message = error instanceof Error ? error.message : String(error)
    throw new ApiError(0, message, url, `Network error: ${message}`)
  }
}

export function getApiInfo() {
  return {
    base: BASE,
    mode: normalizedEnvBase ? 'direct' : import.meta.env.PROD ? 'proxy' : 'local',
    env: normalizedEnvBase || '(not set)',
  } as const
}

export async function fetchTasks(): Promise<TaskInfo[]> {
  const data = await request<{ tasks: TaskInfo[] }>('/tasks')
  return data.tasks
}

export async function simulate(
  taskId: string,
  agent: 'greedy' | 'random' | 'ai_4stage' = 'greedy',
): Promise<SimResult> {
  return request<SimResult>(`/simulate/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent }),
  })
}

export async function compare(taskId: string): Promise<CompareResult> {
  return request<CompareResult>(`/compare/${taskId}`, { method: 'POST' })
}

type StreamCallbacks = {
  onMeta: (event: StreamMetaEvent) => void
  onStage: (event: StreamStageEvent) => void
  onStep: (step: SimStep) => void
  onDone: (event: StreamDoneEvent) => void
  onError: (message: string) => void
}

export function buildSseUrl(taskId: string, agent: 'greedy' | 'random' | 'ai_4stage'): string {
  const streamPath = `/simulate/stream/${taskId}?agent=${encodeURIComponent(agent)}`
  if (BASE.startsWith('http://') || BASE.startsWith('https://')) {
    return `${BASE}${streamPath}`
  }
  if (typeof window !== 'undefined') {
    return `${window.location.origin}${BASE}${streamPath}`
  }
  return `${BASE}${streamPath}`
}

export function streamSimulation(
  taskId: string,
  agent: 'greedy' | 'random' | 'ai_4stage',
  callbacks: StreamCallbacks,
): () => void {
  const url = buildSseUrl(taskId, agent)
  const source = new EventSource(url)

  source.addEventListener('meta', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as StreamMetaEvent
    callbacks.onMeta(data)
  })

  source.addEventListener('stage', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as StreamStageEvent
    callbacks.onStage(data)
  })

  source.addEventListener('step', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as SimStep
    callbacks.onStep(data)
  })

  source.addEventListener('done', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as StreamDoneEvent
    callbacks.onDone(data)
    source.close()
  })

  source.addEventListener('error', (event) => {
    const payload = (event as MessageEvent).data
    if (payload) {
      try {
        const parsed = JSON.parse(payload) as { detail?: string }
        callbacks.onError(parsed.detail || payload)
      } catch {
        callbacks.onError(payload)
      }
    } else {
      callbacks.onError(`SSE stream failed (${url})`)
    }
    source.close()
  })

  return () => source.close()
}
