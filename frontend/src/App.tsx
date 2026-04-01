import { useState, useEffect } from 'react'
import { fetchTasks, ApiError, getApiInfo } from './api/client'
import { SimulationTab } from './components/SimulationTab'
import { CompareTab } from './components/CompareTab'
import { LiveDemoTab } from './components/LiveDemoTab'
import type { TaskInfo } from './types'

type Tab = 'simulate' | 'demo' | 'compare' | 'about'

export default function App() {
  const [tab, setTab] = useState<Tab>('simulate')
  const [tasks, setTasks] = useState<TaskInfo[]>([])
  const [selectedTask, setSelectedTask] = useState('task_1')
  const [selectedAgent, setSelectedAgent] = useState<'greedy' | 'random' | 'ai_4stage'>('greedy')
  const [tasksError, setTasksError] = useState<string | null>(null)
  const apiInfo = getApiInfo()

  useEffect(() => {
    fetchTasks()
      .then(t => {
        setTasks(t)
        if (t.length > 0) setSelectedTask(t[0].task_id)
      })
      .catch(e => {
        if (e instanceof ApiError) {
          setTasksError(`${e.message} (url: ${e.url})`)
          return
        }
        setTasksError(String(e))
      })
  }, [])

  const tabClass = (t: Tab) =>
    `px-5 py-2.5 text-sm font-medium rounded-lg transition-colors ${
      tab === t
        ? 'bg-zinc-800 text-white'
        : 'text-zinc-500 hover:text-zinc-300'
    }`

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-950 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🚨</span>
            <div>
              <h1 className="text-lg font-bold leading-tight">DisasterMan</h1>
              <p className="text-xs text-zinc-500">AI Disaster Relief Coordination — Benchmark + Bengaluru Live Demo</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="https://github.com/Rajy777/disasterman"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-zinc-500 hover:text-white transition-colors px-3 py-1.5 border border-zinc-800 rounded-lg"
            >
              GitHub ↗
            </a>
            <a
              href="https://krishpotanwar-disasterman-scaler-demo.hf.space/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-zinc-800 hover:bg-zinc-700 text-white transition-colors px-3 py-1.5 rounded-lg"
            >
              API Docs ↗
            </a>
          </div>
        </div>

        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-4 pb-3 flex gap-1">
          <button className={tabClass('simulate')} onClick={() => setTab('simulate')}>
            🎮 Simulate
          </button>
          <button className={tabClass('demo')} onClick={() => setTab('demo')}>
            🗺️ Live Demo
          </button>
          <button className={tabClass('compare')} onClick={() => setTab('compare')}>
            ⚔️ Compare Agents
          </button>
          <button className={tabClass('about')} onClick={() => setTab('about')}>
            ℹ️ About
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {tasksError && (
          <div className="bg-red-950 border border-red-800 rounded-xl p-4 text-red-300 text-sm mb-6">
            Could not connect to backend: {tasksError}
            <br />
            <span className="text-xs text-red-500">
              API mode: {apiInfo.mode} | base: {apiInfo.base} | VITE_API_URL: {apiInfo.env}
            </span>
          </div>
        )}

        {tab === 'simulate' && (
          tasks.length > 0
            ? <SimulationTab
                tasks={tasks}
                selectedTask={selectedTask}
                setSelectedTask={setSelectedTask}
                selectedAgent={selectedAgent}
                setSelectedAgent={setSelectedAgent}
              />
            : !tasksError && (
                <div className="flex items-center justify-center py-16 text-zinc-500 text-sm">
                  <span className="animate-spin mr-3 text-lg">⚙</span> Connecting to backend…
                </div>
              )
        )}

        {tab === 'demo' && (
          <LiveDemoTab />
        )}

        {tab === 'compare' && (
          tasks.length > 0
            ? <CompareTab tasks={tasks} />
            : !tasksError && (
                <div className="flex items-center justify-center py-16 text-zinc-500 text-sm">
                  <span className="animate-spin mr-3 text-lg">⚙</span> Connecting to backend…
                </div>
              )
        )}

        {tab === 'about' && (
          <div className="max-w-3xl space-y-6">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <h2 className="text-xl font-bold mb-2">DisasterMan — DRC-Env v3</h2>
              <p className="text-zinc-400 text-sm leading-relaxed">
                An OpenEnv-compliant multi-agent AI training environment for disaster relief coordination.
                AI agents manage rescue teams, supplies, and airlifts across disaster zones under
                cascading failures, false SOS signals, and weather events.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { title: '106/106 Tests', sub: 'Passing — benchmark environment verified', icon: '✅' },
                { title: 'PyTorch MLP', sub: 'Zone priority scoring <1ms', icon: '🧠' },
                { title: 'Live City Demo', sub: 'Leaflet + SSE scenario theater', icon: '🗺️' },
              ].map(c => (
                <div key={c.title} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-center">
                  <div className="text-3xl mb-2">{c.icon}</div>
                  <div className="font-semibold text-white">{c.title}</div>
                  <div className="text-xs text-zinc-500 mt-1">{c.sub}</div>
                </div>
              ))}
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
              <h3 className="font-semibold text-white">What Makes This Different</h3>
              <div className="space-y-3 text-sm text-zinc-400">
                <p><strong className="text-white">False SOS Signals</strong> — Zones H, I, J broadcast genuine-looking distress calls with zero casualties. The AI must detect and ignore them using pattern recognition — not explicit flags.</p>
                <p><strong className="text-white">Cascading Failures</strong> — A dam breaks at step 7 of Task 3, adding 60 new casualties. The agent must dynamically replan mid-episode.</p>
                <p><strong className="text-white">Anti-Hallucination Validator</strong> — Every LLM action passes through a hard constraint checker that rejects invalid zones, overestimates, and blocked-road violations before execution.</p>
                <p><strong className="text-white">Bengaluru Live Demo</strong> — Separate reviewer mode shows curated flood, fire, and collapse scenarios on a real map with live resource routes and synchronized reasoning.</p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
