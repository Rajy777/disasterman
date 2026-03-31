import { useSyncExternalStore } from 'react'
import type {
  SimResult,
  SimStep,
  StageName,
  StreamDoneEvent,
  StreamMetaEvent,
  StreamStageEvent,
} from '../types'

type StreamStatus = 'idle' | 'connecting' | 'running' | 'completed' | 'error'

interface LiveSimState {
  status: StreamStatus
  meta: StreamMetaEvent | null
  steps: SimStep[]
  stageTimeline: Record<number, StreamStageEvent[]>
  activeStage: StageName | null
  currentStepIndex: number
  done: StreamDoneEvent | null
  error: string | null
  setConnecting: () => void
  setMeta: (meta: StreamMetaEvent) => void
  pushStage: (event: StreamStageEvent) => void
  pushStep: (step: SimStep) => void
  setDone: (done: StreamDoneEvent) => void
  setError: (msg: string) => void
  setCurrentStepIndex: (index: number) => void
  reset: () => void
  toResult: () => SimResult | null
}

type MutableLiveSimState = Omit<
  LiveSimState,
  'setConnecting' | 'setMeta' | 'pushStage' | 'pushStep' | 'setDone' | 'setError' | 'setCurrentStepIndex' | 'reset' | 'toResult'
>

const initialState = (): MutableLiveSimState => ({
  status: 'idle',
  meta: null,
  steps: [],
  stageTimeline: {},
  activeStage: null,
  currentStepIndex: 0,
  done: null,
  error: null,
})

const listeners = new Set<() => void>()
const state: MutableLiveSimState = initialState()

function emit() {
  listeners.forEach((listener) => listener())
}

function update(mutator: (draft: MutableLiveSimState) => void) {
  mutator(state)
  emit()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

const api: LiveSimState = {
  ...state,
  setConnecting: () => {
    update((draft) => {
      Object.assign(draft, initialState(), { status: 'connecting' as const })
    })
  },
  setMeta: (meta) => {
    update((draft) => {
      draft.meta = meta
      draft.status = 'running'
      draft.error = null
    })
  },
  pushStage: (event) => {
    update((draft) => {
      draft.status = 'running'
      draft.activeStage = event.stage
      draft.stageTimeline[event.step] = [...(draft.stageTimeline[event.step] ?? []), event]
    })
  },
  pushStep: (step) => {
    update((draft) => {
      draft.status = 'running'
      draft.steps.push(step)
      draft.currentStepIndex = draft.steps.length - 1
      draft.activeStage = null
    })
  },
  setDone: (done) => {
    update((draft) => {
      draft.done = done
      draft.status = 'completed'
      draft.activeStage = null
    })
  },
  setError: (msg) => {
    update((draft) => {
      draft.error = msg
      draft.status = 'error'
      draft.activeStage = null
    })
  },
  setCurrentStepIndex: (index) => {
    update((draft) => {
      draft.currentStepIndex = Math.max(0, index)
    })
  },
  reset: () => {
    update((draft) => {
      Object.assign(draft, initialState())
    })
  },
  toResult: () => {
    if (state.steps.length === 0 || !state.meta) return null
    return {
      task_id: state.meta.task_id,
      agent: state.meta.agent,
      final_score: state.done?.final_score ?? null,
      cumulative_reward: state.done?.cumulative_reward ?? 0,
      steps_taken: state.done?.steps_taken ?? state.steps.length,
      steps: state.steps,
      note: state.done ? undefined : 'Live stream in progress',
    }
  },
}

function snapshot(): LiveSimState {
  return {
    ...state,
    setConnecting: api.setConnecting,
    setMeta: api.setMeta,
    pushStage: api.pushStage,
    pushStep: api.pushStep,
    setDone: api.setDone,
    setError: api.setError,
    setCurrentStepIndex: api.setCurrentStepIndex,
    reset: api.reset,
    toResult: api.toResult,
  }
}

export function useLiveSimStore<T>(selector: (store: LiveSimState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(snapshot()),
    () => selector(snapshot()),
  )
}
