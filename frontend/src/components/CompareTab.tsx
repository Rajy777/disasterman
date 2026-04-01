import { useState } from 'react'
import { compare } from '../api/client'
import { DisasterMap } from './DisasterMap'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { CompareResult, SimResult, TaskInfo } from '../types'

interface Props {
  tasks: TaskInfo[]
}

const AGENT_META: Record<string, { label: string; color: string; desc: string }> = {
  random:    { label: 'Random Agent',      color: '#ef4444', desc: 'Picks random valid actions' },
  greedy:    { label: 'Greedy Heuristic',  color: '#f97316', desc: 'Severity-first rule-based' },
  ai_4stage: { label: '4-Stage AI',        color: '#22c55e', desc: 'PyTorch + Triage + Planner + Action' },
}

interface MiniSimProps {
  result: SimResult
  falseSOSZones: string[]
  stepIndex: number
}

function MiniSimPanel({ result, falseSOSZones, stepIndex }: MiniSimProps) {
  const meta = AGENT_META[result.agent] ?? { label: result.agent, color: '#6b7280', desc: '' }
  const step = result.steps[Math.min(stepIndex, result.steps.length - 1)]
  const obs = step?.observation
  const isDone = stepIndex >= result.steps.length - 1

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-semibold text-sm" style={{ color: meta.color }}>{meta.label}</div>
          <div className="text-xs text-zinc-500">{meta.desc}</div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold mono" style={{ color: isDone && result.final_score != null ? meta.color : '#71717a' }}>
            {isDone && result.final_score != null ? result.final_score.toFixed(4) : '—'}
          </div>
          <div className="text-xs text-zinc-600">final score</div>
        </div>
      </div>
      {obs ? (
        <DisasterMap
          zones={obs.zones}
          action={step?.action}
          falseSOSZones={falseSOSZones}
          pytorchScores={step?.reasoning?.pytorch_scores}
          compact
        />
      ) : (
        <div className="h-20 flex items-center justify-center text-zinc-600 text-sm">
          {result.note ?? 'No data'}
        </div>
      )}
    </div>
  )
}

export function CompareTab({ tasks }: Props) {
  const [selectedTask, setSelectedTask] = useState(() => tasks[1]?.task_id ?? tasks[0]?.task_id ?? 'task_2')
  const [result, setResult] = useState<CompareResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stepIndex, setStepIndex] = useState(0)

  const task = tasks.find(t => t.task_id === selectedTask)
  const falseSOSZones = task?.false_sos_zones ?? []

  const runCompare = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    setStepIndex(0)
    try {
      const r = await compare(selectedTask)
      setResult(r)
      // Auto-advance step index to the end of the longest replay.
      const maxSteps = Math.max(
        r.agents.random?.steps.length ?? 0,
        r.agents.greedy?.steps.length ?? 0,
        r.agents.ai_4stage?.steps.length ?? 0,
      )
      if (maxSteps > 0) {
        let i = 0
        const timer = setInterval(() => {
          i++
          setStepIndex(i)
          if (i >= maxSteps - 1) clearInterval(timer)
        }, 800)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const scoredAgents = result
    ? ([
        { key: 'random', label: AGENT_META.random.label, score: result.agents.random?.final_score, fill: AGENT_META.random.color },
        { key: 'greedy', label: AGENT_META.greedy.label, score: result.agents.greedy?.final_score, fill: AGENT_META.greedy.color },
        { key: 'ai_4stage', label: AGENT_META.ai_4stage.label, score: result.agents.ai_4stage?.final_score, fill: AGENT_META.ai_4stage.color },
      ].filter((agent): agent is { key: string; label: string; score: number; fill: string } => typeof agent.score === 'number'))
    : []

  const scoreData = scoredAgents.map(agent => ({
    name: agent.label,
    score: agent.score,
    fill: agent.fill,
  }))

  const maxSteps = result
    ? Math.max(
        result.agents.random?.steps.length ?? 0,
        result.agents.greedy?.steps.length ?? 0,
        result.agents.ai_4stage?.steps.length ?? 0,
      )
    : 0

  let comparisonSummary = 'Run a comparison to inspect how the agents behave on the same task.'
  if (result && result.agents.ai_4stage?.final_score == null) {
    comparisonSummary = result.agents.ai_4stage?.note ?? '4-Stage AI is unavailable in this environment, so only the heuristic baselines are being compared.'
  } else if (scoredAgents.length > 0) {
    const leader = scoredAgents.reduce((best, agent) => agent.score > best.score ? agent : best)
    comparisonSummary = `${leader.label} leads this run at ${leader.score.toFixed(4)}.`
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-48">
          <label className="block text-xs text-zinc-500 mb-1.5 uppercase tracking-wider">Task</label>
          <select
            value={selectedTask}
            onChange={e => setSelectedTask(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none"
          >
            {tasks.map(t => (
              <option key={t.task_id} value={t.task_id}>{t.name} ({t.difficulty})</option>
            ))}
          </select>
        </div>
        <button
          onClick={runCompare}
          disabled={loading}
          className="px-5 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? 'Running all 3 agents…' : '▶ Compare Agents'}
        </button>
      </div>

      {error && (
        <div className="bg-red-950 border border-red-800 rounded-xl p-4 text-red-300 text-sm">{error}</div>
      )}

      {loading && (
        <div className="flex flex-col items-center py-16 text-zinc-400">
          <div className="text-4xl mb-4 animate-spin">⚙</div>
          <p className="text-sm">Running available agents in parallel…</p>
        </div>
      )}

      {result && !loading && (
        <>
          {/* Score comparison bar chart */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium mb-4">Final Score Comparison</h3>
            <div className="h-36">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoreData} margin={{ top: 4, right: 20, left: -10, bottom: 0 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#a1a1aa' }} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: '#52525b' }} />
                  <Tooltip
                    contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', borderRadius: 8 }}
                    formatter={(v) => typeof v === 'number' ? v.toFixed(4) : String(v)}
                  />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                    {scoreData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-zinc-600 text-center mt-2">
              {comparisonSummary}
            </p>
          </div>

          {/* Step scrubber */}
          {maxSteps > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <label className="text-xs text-zinc-500 uppercase tracking-wider block mb-2">
                Replay Step {Math.min(stepIndex + 1, maxSteps)} / {maxSteps}
              </label>
              <input
                type="range"
                min={0}
                max={maxSteps - 1}
                value={stepIndex}
                onChange={e => setStepIndex(parseInt(e.target.value))}
                className="w-full accent-red-500"
              />
            </div>
          )}

          {/* Side-by-side maps */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(['random', 'greedy', 'ai_4stage'] as const).map(agent => {
              const agentResult = result.agents[agent]
              if (!agentResult) return null
              return (
                <MiniSimPanel
                  key={agent}
                  result={agentResult}
                  falseSOSZones={falseSOSZones}
                  stepIndex={stepIndex}
                />
              )
            })}
          </div>
        </>
      )}

      {/* Explainer */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-3">Agent Profiles</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-zinc-400">
          <div>
            <div className="text-red-400 font-medium mb-1">Random Agent</div>
            <p>Picks any valid action randomly. Useful as a floor, but it can waste scarce airlifts, miss deadlines, and react poorly to changing conditions.</p>
          </div>
          <div>
            <div className="text-orange-400 font-medium mb-1">Greedy Heuristic</div>
            <p>Follows fixed rules: recall → airlift → deploy → supply. It benefits from PyTorch zone ranking and false-SOS filtering, but it still has no lookahead and stays fairly rigid.</p>
          </div>
          <div>
            <div className="text-green-400 font-medium mb-1">4-Stage AI Pipeline</div>
            <p>When enabled, it combines PyTorch scoring, LLM triage, a short-horizon planner, and a hard validator. That gives it the strongest decision loop, but it depends on an API key.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
