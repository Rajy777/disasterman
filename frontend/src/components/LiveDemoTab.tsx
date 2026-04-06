import { useEffect, useRef, useState } from 'react'
import {
  ApiError,
  fetchDemoScenarios,
  runDemoScenario,
  streamDemoScenario,
} from '../api/client'
import type {
  AgentId,
  DemoRunResult,
  DemoScenarioCatalog,
  DemoScenarioDetail,
  DemoScenarioSummary,
  DemoStep,
  DemoStreamDoneEvent,
  DemoStreamMetaEvent,
  SimResult,
  StageName,
  StreamStageEvent,
} from '../types'
import { AgentReasoningPanel } from './AgentReasoningPanel'
import { CopilotQaPanel } from './CopilotQaPanel'
import { EventFeed } from './EventFeed'
import { LeafletDemoMap } from './LeafletDemoMap'
import { ScorePanel } from './ScorePanel'
import { CommsInterceptTerminal } from './CommsInterceptTerminal'

const AGENT_LABELS: Record<AgentId, string> = {
  ai_4stage: '4-Stage AI',
  greedy: 'Greedy Heuristic',
  random: 'Random Baseline',
}

const SPEED_MS = {
  slow: 1800,
  normal: 1000,
  fast: 450,
} as const

type PlaybackSpeed = keyof typeof SPEED_MS
type DemoStatus = 'idle' | 'connecting' | 'streaming' | 'fallback' | 'completed' | 'error'

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return String(error)
}

function statusBadge(status: DemoStatus): string {
  if (status === 'connecting') return 'Connecting live stream'
  if (status === 'streaming') return 'Streaming live'
  if (status === 'fallback') return 'Replay fallback'
  if (status === 'completed') return 'Run complete'
  if (status === 'error') return 'Run failed'
  return 'Ready'
}

function statusClasses(status: DemoStatus): string {
  if (status === 'connecting') return 'bg-sky-950 text-sky-300 border-sky-800'
  if (status === 'streaming') return 'bg-emerald-950 text-emerald-300 border-emerald-800'
  if (status === 'fallback') return 'bg-amber-950 text-amber-300 border-amber-800'
  if (status === 'completed') return 'bg-zinc-800 text-zinc-200 border-zinc-700'
  if (status === 'error') return 'bg-red-950 text-red-300 border-red-800'
  return 'bg-zinc-900 text-zinc-400 border-zinc-800'
}

function toScoreResult(result: DemoRunResult, scenarioId: string): SimResult {
  return {
    task_id: scenarioId,
    agent: result.agent,
    final_score: result.final_score,
    cumulative_reward: result.cumulative_reward,
    steps_taken: result.steps_taken,
    steps: result.steps,
    note: result.note ?? undefined,
  }
}

export function LiveDemoTab() {
  const [catalog, setCatalog] = useState<DemoScenarioCatalog | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [selectedScenarioId, setSelectedScenarioId] = useState('')
  const [selectedAgent, setSelectedAgent] = useState<AgentId>('ai_4stage')
  const [speed, setSpeed] = useState<PlaybackSpeed>('normal')
  const [status, setStatus] = useState<DemoStatus>('idle')
  const [result, setResult] = useState<DemoRunResult | null>(null)
  const [streamMeta, setStreamMeta] = useState<DemoStreamMetaEvent | null>(null)
  const [streamSteps, setStreamSteps] = useState<DemoStep[]>([])
  const [streamDone, setStreamDone] = useState<DemoStreamDoneEvent | null>(null)
  const [stageTimeline, setStageTimeline] = useState<Record<number, StreamStageEvent[]>>({})
  const [activeStage, setActiveStage] = useState<StageName | null>(null)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const timerRef = useRef<number | null>(null)
  const streamCleanupRef = useRef<(() => void) | null>(null)
  const fallbackTimeoutRef = useRef<number | null>(null)
  const fallbackInFlightRef = useRef(false)
  const receivedStepRef = useRef(false)
  const streamFinishedRef = useRef(false)
  const runIdRef = useRef(0)

  useEffect(() => {
    fetchDemoScenarios()
      .then((data) => {
        setCatalog(data)
        if (data.scenarios.length > 0) {
          setSelectedScenarioId(data.scenarios[0].scenario_id)
          setSelectedAgent(data.scenarios[0].default_agent)
        }
      })
      .catch((err) => {
        setCatalogError(errorMessage(err))
      })
  }, [])

  useEffect(() => {
    return () => {
      if (streamCleanupRef.current) {
        streamCleanupRef.current()
      }
      if (fallbackTimeoutRef.current) {
        window.clearTimeout(fallbackTimeoutRef.current)
      }
      if (timerRef.current) {
        window.clearInterval(timerRef.current)
      }
    }
  }, [])

  const selectedScenario: DemoScenarioSummary | null =
    catalog?.scenarios.find((scenario) => scenario.scenario_id === selectedScenarioId) ?? null

  const stopPlayback = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    setIsPlaying(false)
  }

  const clearStream = () => {
    if (streamCleanupRef.current) {
      streamCleanupRef.current()
      streamCleanupRef.current = null
    }
    if (fallbackTimeoutRef.current) {
      window.clearTimeout(fallbackTimeoutRef.current)
      fallbackTimeoutRef.current = null
    }
  }

  const resetRunState = () => {
    clearStream()
    stopPlayback()
    setStatus('idle')
    setResult(null)
    setStreamMeta(null)
    setStreamSteps([])
    setStreamDone(null)
    setStageTimeline({})
    setActiveStage(null)
    setCurrentStepIndex(0)
    setError(null)
    setNote(null)
    fallbackInFlightRef.current = false
    receivedStepRef.current = false
    streamFinishedRef.current = false
  }

  const startPlayback = (runResult: DemoRunResult, fromIndex = 0) => {
    stopPlayback()
    setCurrentStepIndex(fromIndex)
    setIsPlaying(true)

    timerRef.current = window.setInterval(() => {
      setCurrentStepIndex((index) => {
        const next = index + 1
        if (next >= runResult.steps.length) {
          stopPlayback()
          return index
        }
        return next
      })
    }, SPEED_MS[speed])
  }

  const runFallback = async (runId: number, scenarioId: string, agent: AgentId, reason: string) => {
    if (fallbackInFlightRef.current || runIdRef.current !== runId) return
    fallbackInFlightRef.current = true
    clearStream()
    setStatus('fallback')
    setNote(reason)
    setActiveStage(null)

    try {
      const fallbackResult = await runDemoScenario(scenarioId, agent)
      if (runIdRef.current !== runId) return
      setResult(fallbackResult)
      setStreamMeta(null)
      setStreamSteps([])
      setStreamDone(null)
      setStageTimeline({})
      setCurrentStepIndex(0)
      setError(null)
      setNote(fallbackResult.note ?? reason)
      setStatus('completed')
      startPlayback(fallbackResult, 0)
    } catch (fallbackError) {
      if (runIdRef.current !== runId) return
      setStatus('error')
      setError(errorMessage(fallbackError))
    }
  }

  const run = () => {
    if (!selectedScenarioId) return

    const runId = runIdRef.current + 1
    runIdRef.current = runId
    const scenarioId = selectedScenarioId
    const agent = selectedAgent

    resetRunState()
    setStatus('connecting')

    try {
      streamCleanupRef.current = streamDemoScenario(scenarioId, agent, {
        onMeta: (meta) => {
          if (runIdRef.current !== runId) return
          setStreamMeta(meta)
          setStatus('streaming')
        },
        onStage: (event) => {
          if (runIdRef.current !== runId) return
          setStatus('streaming')
          setActiveStage(event.stage)
          setStageTimeline((current) => ({
            ...current,
            [event.step]: [...(current[event.step] ?? []), event],
          }))
        },
        onStep: (step) => {
          if (runIdRef.current !== runId) return
          receivedStepRef.current = true
          if (fallbackTimeoutRef.current) {
            window.clearTimeout(fallbackTimeoutRef.current)
            fallbackTimeoutRef.current = null
          }

          let nextLength = 0
          setStreamSteps((current) => {
            const next = [...current, step]
            nextLength = next.length
            return next
          })
          setCurrentStepIndex(Math.max(0, nextLength - 1))
          setActiveStage(null)
          setStatus('streaming')
        },
        onDone: (done) => {
          if (runIdRef.current !== runId) return
          streamFinishedRef.current = true
          clearStream()
          setStreamDone(done)
          setActiveStage(null)
          setStatus('completed')
          setNote(done.note ?? null)
        },
        onError: (message) => {
          if (runIdRef.current !== runId || streamFinishedRef.current) return
          void runFallback(
            runId,
            scenarioId,
            agent,
            message || 'Live stream failed, so replay mode is taking over.',
          )
        },
      })

      fallbackTimeoutRef.current = window.setTimeout(() => {
        if (receivedStepRef.current || runIdRef.current !== runId) return
        void runFallback(
          runId,
          scenarioId,
          agent,
          'Live stream stalled before the first usable step, so replay mode is taking over.',
        )
      }, 4500)
    } catch (streamError) {
      void runFallback(
        runId,
        scenarioId,
        agent,
        `Could not start the live stream (${errorMessage(streamError)}). Replay mode is taking over.`,
      )
    }
  }

  const currentResult: DemoRunResult | null = result ?? (
    streamMeta
      ? {
          scenario: streamMeta.scenario,
          agent: streamMeta.agent,
          model: streamMeta.model,
          final_score: streamDone?.final_score ?? null,
          cumulative_reward:
            streamDone?.cumulative_reward ??
            streamSteps.reduce((total, step) => total + step.reward, 0),
          steps_taken: streamDone?.steps_taken ?? streamSteps.length,
          steps: streamSteps,
          note: streamDone?.note ?? note ?? (status === 'streaming' ? 'Live stream in progress.' : undefined),
        }
      : null
  )

  const activeScenarioDetail: DemoScenarioDetail | null = currentResult?.scenario ?? streamMeta?.scenario ?? null
  const currentStep =
    currentResult && currentResult.steps.length > 0
      ? currentResult.steps[Math.min(currentStepIndex, currentResult.steps.length - 1)] ?? null
      : null
  const currentStageEvents = currentStep ? stageTimeline[currentStep.step] ?? [] : []
  const scoreResult = currentResult ? toScoreResult(currentResult, selectedScenarioId || 'demo') : null
  const canReplay = Boolean(currentResult && currentResult.steps.length > 0)
  const atFirstStep = !currentResult || currentStepIndex <= 0
  const atLastStep = !currentResult || currentStepIndex >= currentResult.steps.length - 1

  return (
    <div className="space-y-6">
      {catalogError ? (
        <div className="rounded-2xl border border-red-800 bg-red-950 p-4 text-sm text-red-300">
          Could not load live demo scenarios: {catalogError}
        </div>
      ) : null}

      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.3em] text-zinc-500">Reviewer Demo Mode</div>
            <h2 className="mt-1 text-xl font-semibold text-white">Bengaluru Live Disaster Demo</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-400">
              Curated city scenarios that show where teams, supplies, and airlifts move on a real map while the
              model reasons step by step. Benchmark tasks stay unchanged; this is the visual explainer layer.
            </p>
          </div>
          <span className={`rounded-full border px-3 py-1 text-xs ${statusClasses(status)}`}>
            {statusBadge(status)}
          </span>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {(catalog?.scenarios ?? []).map((scenario) => {
            const selected = scenario.scenario_id === selectedScenarioId
            return (
              <button
                key={scenario.scenario_id}
                type="button"
                onClick={() => {
                  resetRunState()
                  setSelectedScenarioId(scenario.scenario_id)
                  setSelectedAgent(scenario.default_agent)
                }}
                className={`rounded-2xl border p-4 text-left transition-all ${
                  selected
                    ? 'border-sky-500 bg-sky-950/40 shadow-[0_0_0_1px_rgba(14,165,233,0.35)]'
                    : 'border-zinc-800 bg-zinc-950 hover:border-zinc-700 hover:bg-zinc-900'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-white">{scenario.title}</div>
                  <span className="rounded-full border border-zinc-700 px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-zinc-400">
                    {scenario.disaster_type}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">{scenario.narrative}</p>
                <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-zinc-500">
                  <span>{scenario.duration_steps} steps</span>
                  <span>Default: {AGENT_LABELS[scenario.default_agent]}</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {scenario.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-zinc-800 px-2.5 py-1 text-[11px] text-zinc-300">
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            )
          })}
        </div>

        <div className="mt-5 flex flex-wrap items-end gap-4 border-t border-zinc-800 pt-5">
          <div className="min-w-56 flex-1">
            <label className="mb-1.5 block text-xs uppercase tracking-[0.25em] text-zinc-500">Agent</label>
            <select
              value={selectedAgent}
              onChange={(event) => setSelectedAgent(event.target.value as AgentId)}
              className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white focus:border-zinc-500 focus:outline-none"
            >
              {(catalog?.available_agents ?? ['ai_4stage', 'greedy', 'random']).map((agent) => (
                <option key={agent} value={agent}>
                  {AGENT_LABELS[agent]}
                  {agent === 'ai_4stage' && catalog?.ai_available === false ? ' (fallback mode)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs uppercase tracking-[0.25em] text-zinc-500">Replay Speed</label>
            <div className="overflow-hidden rounded-xl border border-zinc-700">
              {(['slow', 'normal', 'fast'] as PlaybackSpeed[]).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setSpeed(item)}
                  className={`px-3 py-2 text-xs capitalize ${
                    speed === item
                      ? 'bg-zinc-600 text-white'
                      : 'bg-zinc-950 text-zinc-400 hover:bg-zinc-900'
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={run}
              disabled={!selectedScenarioId || status === 'connecting' || status === 'fallback'}
              className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {status === 'connecting' || status === 'fallback' ? 'Launching…' : '▶ Run Live Demo'}
            </button>

            {canReplay && currentResult ? (
              <>
                <button
                  type="button"
                  onClick={() => (isPlaying ? stopPlayback() : startPlayback(currentResult, currentStepIndex))}
                  className="rounded-xl bg-zinc-800 px-3 py-2 text-sm text-white transition-colors hover:bg-zinc-700"
                >
                  {isPlaying ? '⏸ Pause' : '▷ Replay'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    stopPlayback()
                    setCurrentStepIndex((index) => Math.max(0, index - 1))
                  }}
                  disabled={atFirstStep}
                  className="rounded-xl bg-zinc-800 px-3 py-2 text-sm text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  ← Prev
                </button>
                <button
                  type="button"
                  onClick={() => {
                    stopPlayback()
                    setCurrentStepIndex((index) => Math.min(currentResult.steps.length - 1, index + 1))
                  }}
                  disabled={atLastStep}
                  className="rounded-xl bg-zinc-800 px-3 py-2 text-sm text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next →
                </button>
                <button
                  type="button"
                  onClick={() => {
                    stopPlayback()
                    setCurrentStepIndex(0)
                  }}
                  className="rounded-xl bg-zinc-800 px-3 py-2 text-sm text-white transition-colors hover:bg-zinc-700"
                >
                  ↺ Reset
                </button>
              </>
            ) : null}
          </div>
        </div>
      </div>

      {note ? (
        <div className="rounded-2xl border border-amber-800 bg-amber-950/60 p-4 text-sm text-amber-200">
          {note}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-red-800 bg-red-950 p-4 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {activeScenarioDetail ? (
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-4">
            <LeafletDemoMap scenario={activeScenarioDetail} mapState={currentStep?.map_state ?? null} />

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-xs font-medium uppercase tracking-[0.25em] text-zinc-500">Scenario Summary</h3>
                <span className="rounded-full border border-zinc-700 px-3 py-1 text-[11px] text-zinc-300">
                  {activeScenarioDetail.duration_steps} steps
                </span>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-zinc-400">{activeScenarioDetail.narrative}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {activeScenarioDetail.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-zinc-800 px-2.5 py-1 text-[11px] text-zinc-300">
                    {tag}
                  </span>
                ))}
              </div>
              {currentStep?.map_state ? (
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-3">
                    <div className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">Active Overlays</div>
                    <div className="mt-2 text-2xl font-semibold text-white">{currentStep.map_state.overlays.length}</div>
                  </div>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-3">
                    <div className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">Tracked Resources</div>
                    <div className="mt-2 text-2xl font-semibold text-white">{currentStep.map_state.resource_positions.length}</div>
                  </div>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-3">
                    <div className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">Highlighted Paths</div>
                    <div className="mt-2 text-2xl font-semibold text-white">{currentStep.map_state.recent_movements.length}</div>
                  </div>
                </div>
              ) : (
                <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950 p-4 text-sm text-zinc-400">
                  The map is ready. Start the live run to watch routes, resources, and model decisions animate on top of Bengaluru.
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4">
            {scoreResult && currentResult ? (
              <ScorePanel result={scoreResult} currentStepIndex={Math.min(currentStepIndex, currentResult.steps.length - 1)} />
            ) : (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-400">
                Score and cumulative reward will appear once the first step lands.
              </div>
            )}

            {currentStep ? (
              <>
                <AgentReasoningPanel
                  reasoning={currentStep.reasoning}
                  agent={AGENT_LABELS[currentResult?.agent as AgentId] ?? currentResult?.agent ?? 'Live Demo Agent'}
                  activeStage={activeStage}
                  stageEvents={currentStageEvents}
                />
                <CopilotQaPanel
                  observation={currentStep.observation}
                  reasoning={currentStep.reasoning}
                  currentAction={currentStep.action}
                  taskName={activeScenarioDetail.title}
                />
              </>
            ) : (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-400">
                Stage updates will stream here as soon as the backend starts emitting PyTorch, triage, planner, and action events.
              </div>
            )}
          </div>
        </div>
      ) : selectedScenario ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
          <div className="text-[11px] uppercase tracking-[0.3em] text-zinc-500">Selected Scenario</div>
          <h3 className="mt-2 text-xl font-semibold text-white">{selectedScenario.title}</h3>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-zinc-400">{selectedScenario.narrative}</p>
        </div>
      ) : null}

      {currentResult && currentResult.steps.length > 0 ? (
        <>
          <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
              <EventFeed
                steps={currentResult.steps}
                currentStepIndex={Math.min(currentStepIndex, currentResult.steps.length - 1)}
              />
              <div className="h-full min-h-[300px]">
                  <CommsInterceptTerminal 
                     steps={currentResult.steps.slice(0, Math.min(currentStepIndex, currentResult.steps.length - 1) + 1)} 
                     autoPlay={false} 
                  />
              </div>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
            <label className="mb-2 block text-xs uppercase tracking-[0.25em] text-zinc-500">
              Step Scrubber — {Math.min(currentStepIndex + 1, currentResult.steps.length)} / {currentResult.steps.length}
            </label>
            <input
              type="range"
              min={0}
              max={Math.max(0, currentResult.steps.length - 1)}
              value={Math.min(currentStepIndex, Math.max(0, currentResult.steps.length - 1))}
              onChange={(event) => {
                stopPlayback()
                setCurrentStepIndex(parseInt(event.target.value, 10))
              }}
              className="w-full accent-sky-500"
            />
          </div>
        </>
      ) : null}
    </div>
  )
}
