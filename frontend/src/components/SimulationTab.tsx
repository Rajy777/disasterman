import { useEffect, useRef } from 'react'
import { simulate, streamSimulation } from '../api/client'
import { useSimulation } from '../hooks/useSimulation'
import { DisasterMap } from './DisasterMap'
import { ResourceBar } from './ResourceBar'
import { EventFeed } from './EventFeed'
import { AgentReasoningPanel } from './AgentReasoningPanel'
import { ScorePanel } from './ScorePanel'
import { ScoreGraph } from './ScoreGraph'
import { ProbabilityMatrix } from './ProbabilityMatrix'
import type { TaskInfo } from '../types'
import { useLiveSimStore } from '../store/liveSimStore'
import { CopilotQaPanel } from './CopilotQaPanel'

interface Props {
  tasks: TaskInfo[]
  selectedTask: string
  setSelectedTask: (t: string) => void
  selectedAgent: 'greedy' | 'random' | 'ai_4stage'
  setSelectedAgent: (a: 'greedy' | 'random' | 'ai_4stage') => void
}

const AGENT_LABELS: Record<string, string> = {
  greedy: 'Greedy Heuristic',
  random: 'Random Agent',
  ai_4stage: '4-Stage AI (Groq)',
}

const DIFFICULTY_COLOR: Record<string, string> = {
  easy: 'text-green-400',
  medium: 'text-orange-400',
  hard: 'text-red-400',
}

export function SimulationTab({
  tasks, selectedTask, setSelectedTask, selectedAgent, setSelectedAgent,
}: Props) {
  const sim = useSimulation()
  const liveStatus = useLiveSimStore((s) => s.status)
  const liveMeta = useLiveSimStore((s) => s.meta)
  const liveSteps = useLiveSimStore((s) => s.steps)
  const liveStageTimeline = useLiveSimStore((s) => s.stageTimeline)
  const liveActiveStage = useLiveSimStore((s) => s.activeStage)
  const liveCurrentStepIndex = useLiveSimStore((s) => s.currentStepIndex)
  const liveDone = useLiveSimStore((s) => s.done)
  const liveError = useLiveSimStore((s) => s.error)
  const setLiveConnecting = useLiveSimStore((s) => s.setConnecting)
  const setLiveMeta = useLiveSimStore((s) => s.setMeta)
  const pushLiveStage = useLiveSimStore((s) => s.pushStage)
  const pushLiveStep = useLiveSimStore((s) => s.pushStep)
  const setLiveDone = useLiveSimStore((s) => s.setDone)
  const setLiveError = useLiveSimStore((s) => s.setError)
  const setLiveCurrentStepIndex = useLiveSimStore((s) => s.setCurrentStepIndex)
  const resetLive = useLiveSimStore((s) => s.reset)
  const streamCleanupRef = useRef<(() => void) | null>(null)
  const task = tasks.find(t => t.task_id === selectedTask)

  const run = () => {
    if (streamCleanupRef.current) {
      streamCleanupRef.current()
      streamCleanupRef.current = null
    }
    setLiveConnecting()
    let sawStep = false

    const fallbackToReplay = () => {
      if (streamCleanupRef.current) {
        streamCleanupRef.current()
        streamCleanupRef.current = null
      }
      resetLive()
      void sim.load(() => simulate(selectedTask, selectedAgent))
    }

    try {
      streamCleanupRef.current = streamSimulation(selectedTask, selectedAgent, {
        onMeta: (meta) => setLiveMeta(meta),
        onStage: (event) => pushLiveStage(event),
        onStep: (step) => {
          sawStep = true
          pushLiveStep(step)
        },
        onDone: (done) => {
          setLiveDone(done)
          streamCleanupRef.current = null
        },
        onError: (message) => {
          streamCleanupRef.current = null
          if (!sawStep) {
            fallbackToReplay()
            return
          }
          setLiveError(message)
        },
      })
    } catch {
      fallbackToReplay()
    }
  }

  const liveResult = (liveMeta && liveSteps.length > 0)
    ? {
        task_id: liveMeta.task_id,
        agent: liveMeta.agent,
        final_score: liveDone?.final_score ?? null,
        cumulative_reward: liveDone?.cumulative_reward ?? 0,
        steps_taken: liveDone?.steps_taken ?? liveSteps.length,
        steps: liveSteps,
      }
    : null
  const usingLive = liveStatus !== 'idle'
  const liveCurrentStep = liveResult ? liveResult.steps[liveCurrentStepIndex] ?? null : null

  const obs = (liveCurrentStep?.observation ?? sim.currentStep?.observation) ?? null
  const action = (liveCurrentStep?.action ?? sim.currentStep?.action) ?? null
  const reasoning = (liveCurrentStep?.reasoning ?? sim.currentStep?.reasoning) ?? null

  const currentResult = (usingLive ? liveResult : sim.result)
  const currentStepIndex = usingLive ? liveCurrentStepIndex : sim.currentStepIndex
  const playbackLength = currentResult?.steps.length ?? 0
  const isLoading = sim.isLoading || liveStatus === 'connecting'
  const mergedError = liveError ?? sim.error

  const falseSOSZones = task?.false_sos_zones ?? []

  useEffect(() => {
    return () => {
      if (streamCleanupRef.current) {
        streamCleanupRef.current()
        streamCleanupRef.current = null
      }
      resetLive()
    }
  }, [resetLive])

  const currentStageEvents = reasoning
    ? liveStageTimeline[liveCurrentStep?.step ?? -1] ?? []
    : []

  return (
    <div className="space-y-6 relative z-10 w-full h-full max-w-[1400px] mx-auto">
      {/* Controls */}
      <div className="glass-panel overflow-hidden rounded-xl shadow-2xl relative">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-indigo-400 to-purple-500 opacity-60"></div>
        <div className="p-6">
          <div className="flex flex-wrap gap-6 items-end">
          {/* Task selector */}
          <div className="flex-1 min-w-[240px]">
            <label className="block text-xs uppercase tracking-widest text-indigo-300/80 font-bold mb-2">Simulated Disaster Task</label>
            <select
              value={selectedTask}
              onChange={e => setSelectedTask(e.target.value)}
              className="w-full bg-zinc-950/60 border border-zinc-800/80 rounded-lg px-4 py-3 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 shadow-inner"
            >
              {tasks.map(t => (
                <option key={t.task_id} value={t.task_id}>
                  {t.name} ({t.difficulty})
                </option>
              ))}
            </select>
          </div>

          {/* Agent selector */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs uppercase tracking-widest text-indigo-300/80 font-bold mb-2">Deployed Agent Model</label>
            <select
              value={selectedAgent}
              onChange={e => setSelectedAgent(e.target.value as 'greedy' | 'random' | 'ai_4stage')}
              className="w-full bg-zinc-950/60 border border-zinc-800/80 rounded-lg px-4 py-3 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 shadow-inner"
            >
              {Object.entries(AGENT_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          {/* Speed */}
          <div>
            <label className="block text-xs uppercase tracking-widest text-zinc-500 font-bold mb-2">Execution Rate</label>
            <div className="flex rounded-lg overflow-hidden border border-zinc-800 bg-zinc-950/40">
              {(['slow', 'normal', 'fast'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => sim.setSpeed(s)}
                  className={`px-4 py-3 text-xs capitalize transition-all font-medium ${
                    sim.speed === s
                      ? 'bg-zinc-700/80 text-white shadow-inner'
                      : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              onClick={run}
              disabled={isLoading}
              className="px-6 py-3 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-bold tracking-wide transition-all shadow-[0_0_15px_rgba(220,38,38,0.4)]"
            >
              {isLoading ? 'Running AI…' : '▶ Run'}
            </button>
            {sim.result && !usingLive && (
              <>
                <button
                  onClick={sim.isPlaying ? sim.pause : sim.play}
                  className="px-3 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors"
                >
                  {sim.isPlaying ? '⏸' : '▷'}
                </button>
                <button
                  onClick={sim.reset}
                  className="px-3 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors"
                >
                  ↺
                </button>
              </>
            )}
            {usingLive && playbackLength > 0 && (
              <>
                <button
                  onClick={() => setLiveCurrentStepIndex(Math.max(0, currentStepIndex - 1))}
                  className="px-3 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors"
                >
                  ←
                </button>
                <button
                  onClick={() => setLiveCurrentStepIndex(Math.min(playbackLength - 1, currentStepIndex + 1))}
                  className="px-3 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors"
                >
                  →
                </button>
              </>
            )}
          </div>
        </div>
        </div>

        {/* Task info */}
        {task && (
          <div className="bg-black/20 border-t border-zinc-800/50 px-6 py-3 flex gap-6 text-xs text-zinc-400 font-mono tracking-wider">
            <span className={DIFFICULTY_COLOR[task.difficulty]}>{task.difficulty.toUpperCase()}</span>
            <span>{task.zones} zones</span>
            <span>{task.max_steps} steps</span>
            {task.false_sos_zones.length > 0 && (
              <span className="text-yellow-600">⚠️ {task.false_sos_zones.length} false SOS zones</span>
            )}
          </div>
        )}
      </div>

      {/* Fallback note (e.g. AI key missing → ran greedy instead) */}
      {liveMeta?.note && (
        <div className="bg-amber-950 border border-amber-800 rounded-xl p-4 text-amber-200 text-sm">
          {liveMeta.note}
        </div>
      )}

      {/* Error */}
      {mergedError && (
        <div className="bg-red-950 border border-red-800 rounded-xl p-4 text-red-300 text-sm">
          {mergedError}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16 text-zinc-400">
          <div className="text-4xl mb-4 animate-spin">⚙</div>
          <p className="text-sm">Running {AGENT_LABELS[selectedAgent]}…</p>
          <p className="text-xs text-zinc-600 mt-1">
            {selectedAgent === 'ai_4stage'
              ? 'This takes ~30–60s (PyTorch → Triage → Planner → Action per step)'
              : 'Computing greedy heuristic…'}
          </p>
        </div>
      )}

      {/* Empty State / Welcome Screen */}
      {!currentResult && !isLoading && !mergedError && (
        <div className="flex flex-col items-center justify-center p-20 glass-panel rounded-2xl relative overflow-hidden mt-8">
          <div className="absolute inset-0 bg-blue-900/10" style={{ backgroundImage: 'radial-gradient(circle at 50% -20%, rgba(59,130,246,0.15), transparent 60%)' }}></div>
          <div className="text-8xl mb-6 opacity-30 blur-[2px] filter">🌐</div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-zinc-100 to-zinc-500 bg-clip-text text-transparent mb-3 z-10">Waiting for Initialization</h2>
          <p className="text-zinc-500 max-w-lg text-center z-10 text-sm leading-relaxed">
            Select an Agent and Task above, then click <span className="text-red-400 font-semibold">Run</span> to begin simulating the 
            crisis management network. Dynamic rendering and PyTorch analysis will load upon connection.
          </p>
        </div>
      )}

      {/* Main content */}
      {currentResult && obs && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in duration-700">
          {/* Left: Map + resources */}
          <div className="lg:col-span-2 space-y-4">
            <div className="glass-panel rounded-xl p-5 shadow-xl relative overflow-hidden">
               <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 blur-[50px] rounded-full pointer-events-none"></div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium">
                  Disaster Map — Step {(liveCurrentStep?.step ?? sim.currentStep?.step) ?? 0} / {currentResult.steps_taken}
                </h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  obs.weather === 'clear' ? 'bg-green-900 text-green-400' :
                  obs.weather === 'storm' ? 'bg-yellow-900 text-yellow-400' :
                  'bg-blue-900 text-blue-400'
                }`}>
                  {obs.weather === 'clear' ? '☀️ Clear' : obs.weather === 'storm' ? '⛈ Storm' : '🌊 Flood'}
                </span>
              </div>
              <DisasterMap
                zones={obs.zones}
                action={action}
                falseSOSZones={falseSOSZones}
                pytorchScores={reasoning?.pytorch_scores}
                compact={false}
              />
            </div>
            <ResourceBar
              resources={obs.resources}
              initial={currentResult.steps[0]?.observation.resources}
            />
          </div>

          {/* Right: Score + reasoning + feed */}
          <div className="space-y-4 relative z-10">
            <ScorePanel result={currentResult} currentStepIndex={currentStepIndex} />
            <ScoreGraph steps={currentResult.steps} currentStepIndex={currentStepIndex} />
            
            {reasoning && reasoning.pytorch_scores && (
              <ProbabilityMatrix scores={reasoning.pytorch_scores} />
            )}

            {reasoning && (
              <AgentReasoningPanel
                reasoning={reasoning}
                agent={AGENT_LABELS[currentResult.agent] ?? currentResult.agent}
                activeStage={liveActiveStage}
                stageEvents={currentStageEvents}
              />
            )}
            {obs && reasoning && (
              <CopilotQaPanel
                observation={obs}
                reasoning={reasoning}
                currentAction={action}
                taskName={task?.name ?? selectedTask}
              />
            )}
          </div>
        </div>
      )}

      {/* Event feed (full width below) */}
      {currentResult && currentResult.steps.length > 0 && (
        <EventFeed steps={currentResult.steps} currentStepIndex={currentStepIndex} />
      )}

      {/* Step scrubber */}
      {currentResult && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">
            Step Scrubber — {currentStepIndex + 1} / {currentResult.steps_taken}
          </label>
          <input
            type="range"
            min={0}
            max={Math.max(0, currentResult.steps.length - 1)}
            value={Math.min(currentStepIndex, Math.max(0, currentResult.steps.length - 1))}
            onChange={e => {
              const value = parseInt(e.target.value)
              if (usingLive) {
                setLiveCurrentStepIndex(value)
              } else {
                sim.seekTo(value)
              }
            }}
            className="w-full accent-red-500"
          />
        </div>
      )}
    </div>
  )
}
