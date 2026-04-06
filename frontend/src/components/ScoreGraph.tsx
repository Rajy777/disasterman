import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { SimStep } from '../types'

interface Props {
  steps: SimStep[]
  currentStepIndex: number
}

export function ScoreGraph({ steps, currentStepIndex }: Props) {
  if (!steps || steps.length === 0) return null

  // Generate data points up to the currentStepIndex
  let cumulative = 0
  const data = steps.map((s, i) => {
    cumulative += s.reward
    return {
      step: s.step,
      reward: s.reward,
      cumulative: cumulative,
      isActive: i === currentStepIndex
    }
  })

  // We show all steps in the whole sequence so the x-axis scale remains stable
  // But maybe we only draw up to the current step? Recharts handles this if we just pass the full data 
  // and color the rest differently, but slicing is easier to see the progression!
  const visibleData = data.slice(0, currentStepIndex + 1)

  return (
    <div className="bg-zinc-900 glass-panel rounded-xl p-4 mt-4 h-64 flex flex-col">
      <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium mb-4">Cumulative Reward Trajectory</h3>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={visibleData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorCum" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis 
              dataKey="step" 
              stroke="#52525b" 
              tick={{ fontSize: 10, fill: '#71717a' }} 
              domain={[1, steps.length]} 
              type="number"
            />
            <YAxis 
              stroke="#52525b" 
              tick={{ fontSize: 10, fill: '#71717a' }} 
              domain={['auto', 'auto']}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', borderRadius: '8px' }}
              itemStyle={{ color: '#fafafa', fontSize: '12px' }}
              labelStyle={{ color: '#71717a', fontSize: '10px' }}
            />
            <Area 
              type="monotone" 
              dataKey="cumulative" 
              stroke="#3b82f6" 
              strokeWidth={2}
              fillOpacity={1} 
              fill="url(#colorCum)" 
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
