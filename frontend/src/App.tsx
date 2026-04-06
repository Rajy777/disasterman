import { useState, useEffect } from 'react'
import { fetchTasks, ApiError, getApiInfo } from './api/client'
import { SimulationTab } from './components/SimulationTab'
import { CompareTab } from './components/CompareTab'
import { LiveDemoTab } from './components/LiveDemoTab'
import { LandingPage } from './components/LandingPage'
import { CommandCenterTab } from './components/CommandCenterTab'
import { StrategyGeneratorTab } from './components/StrategyGeneratorTab'
import { SystemLogsTab } from './components/SystemLogsTab'
import type { TaskInfo } from './types'

type Tab = 'simulate' | 'demo' | 'compare' | 'about' | 'command' | 'strategy'

export default function App() {
  const [showLanding, setShowLanding] = useState(true)
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

  if (showLanding) {
    return <LandingPage onLaunch={() => setShowLanding(false)} />
  }

  return (
    <div className="min-h-screen text-white flex flex-col relative z-0">
      {/* Header */}
      <header className="border-b border-zinc-800/50 backdrop-blur-3xl bg-black/40 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-xl shadow-[0_0_15px_rgba(37,99,235,0.4)]">🚨</div>
            <div>
              <h1 className="text-xl font-bold leading-tight tracking-wider bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent drop-shadow-sm">DISASTERMAN</h1>
              <p className="text-[11px] text-zinc-400 uppercase tracking-widest mt-0.5">AI Disaster Relief Coordination</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
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
              className="text-xs font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white transition-all px-4 py-1.5 rounded-lg shadow-[0_0_15px_rgba(79,70,229,0.4)] hover:shadow-[0_0_25px_rgba(79,70,229,0.7)]"
            >
              API Docs ↗
            </a>
          </div>
        </div>

        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-4 pb-3 flex gap-2 overflow-x-auto">
          <button className={tabClass('strategy')} onClick={() => setTab('strategy')}>
            <span className="mr-1.5">🧠</span> STRATEGY GENERATOR
          </button>
          <button className={tabClass('command')} onClick={() => setTab('command')}>
            <span className="mr-1.5">🌐</span> COMMAND CENTER
          </button>
          <button className={tabClass('simulate')} onClick={() => setTab('simulate')}>
            <span className="mr-1.5">🎛️</span> SIMULATOR
          </button>
          <button className={tabClass('demo')} onClick={() => setTab('demo')}>
            <span className="mr-1.5">🗺️</span> LIVE GLOBAL FEED
          </button>
          <button className={tabClass('compare')} onClick={() => setTab('compare')}>
            <span className="mr-1.5">⚔️</span> MODEL ARENA
          </button>
          <button className={tabClass('about')} onClick={() => setTab('about')}>
             <span className="mr-1.5">ℹ️</span> LOGS
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

        {tab === 'command' && (
          tasks.length > 0
            ? <CommandCenterTab tasks={tasks} />
            : !tasksError && (
                <div className="flex items-center justify-center py-16 text-zinc-500 text-sm">
                  <span className="animate-spin mr-3 text-lg">⚙</span> Connecting to backend…
                </div>
              )
        )}

        {tab === 'strategy' && (
          <StrategyGeneratorTab />
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
          <SystemLogsTab />
        )}
      </main>
    </div>
  )
}
