import { useRef, useEffect } from 'react'
import type { SimStep } from '../types'

interface Props {
  steps: SimStep[]
  currentStepIndex: number
}

function actionLabel(step: SimStep): string {
  const a = step.action
  if (a.action === 'deploy_team') return `deploy ${a.units} teams → Zone ${a.to_zone}`
  if (a.action === 'send_supplies') return `supply ${a.units} units → Zone ${a.to_zone}`
  if (a.action === 'airlift') return `🚁 airlift (${a.type}) → Zone ${a.to_zone}`
  if (a.action === 'recall_team') return `recall ${a.units} teams ← Zone ${a.from_zone}`
  return 'wait'
}

function actionColor(action: string): string {
  if (action === 'deploy_team') return 'text-blue-400'
  if (action === 'send_supplies') return 'text-orange-400'
  if (action === 'airlift') return 'text-purple-400'
  if (action === 'recall_team') return 'text-yellow-400'
  return 'text-zinc-500'
}

export function EventFeed({ steps, currentStepIndex }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const visibleSteps = steps.slice(0, currentStepIndex + 1)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentStepIndex])

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 h-64 overflow-y-auto">
      <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium mb-3">Event Log</h3>
      <div className="space-y-1">
        {visibleSteps.map((step, i) => {
          const isDamBreak = step.observation.weather === 'flood' &&
            step.observation.step_number === 7 &&
            step.observation.zones.find(z => z.zone_id === 'E')
          return (
            <div key={i} className={`flex gap-3 text-xs step-fade-in ${i === currentStepIndex ? 'opacity-100' : 'opacity-70'}`}>
              <span className="mono text-zinc-600 w-8 shrink-0">S{step.step.toString().padStart(2, '0')}</span>
              {isDamBreak && i === currentStepIndex && (
                <span className="text-yellow-400 font-medium mr-1">⚡ DAM BREAK |</span>
              )}
              <span className={`${actionColor(step.action.action)} font-medium`}>
                {actionLabel(step)}
              </span>
              <span className={`ml-auto mono shrink-0 ${step.reward >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {step.reward >= 0 ? '+' : ''}{step.reward.toFixed(3)}
              </span>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
