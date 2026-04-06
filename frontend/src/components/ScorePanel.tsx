import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { SimResult } from '../types'

interface Props {
  result: SimResult
  currentStepIndex: number
}

export function ScorePanel({ result, currentStepIndex }: Props) {
  const progress = result.steps.length > 0
    ? (currentStepIndex + 1) / result.steps.length
    : 1

  const cumulativeReward = result.steps
    .slice(0, currentStepIndex + 1)
    .reduce((sum, s) => sum + s.reward, 0)

  const displayScore = result.final_score != null
    ? (currentStepIndex >= result.steps.length - 1 ? result.final_score : null)
    : null

  const scoreColor =
    displayScore == null ? 'text-zinc-400' :
    displayScore >= 0.6 ? 'text-green-400' :
    displayScore >= 0.35 ? 'text-orange-400' :
    'text-red-400'

  const rewardData = result.steps.slice(0, currentStepIndex + 1).map((s) => ({
    step: s.step,
    reward: parseFloat(s.reward.toFixed(3)),
  }))

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium">Score</h3>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className={`text-2xl font-bold mono ${scoreColor}`}>
              {displayScore != null ? displayScore.toFixed(4) : '—'}
            </div>
            <div className="text-xs text-zinc-600">final score</div>
          </div>
          <div className="text-right">
            <div className={`text-lg font-semibold mono ${cumulativeReward >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {cumulativeReward >= 0 ? '+' : ''}{cumulativeReward.toFixed(3)}
            </div>
            <div className="text-xs text-zinc-600">cumulative reward</div>
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-zinc-500 mb-1">
          <span>Step {currentStepIndex + 1}</span>
          <span>{result.steps_taken} total</span>
        </div>
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 score-bar-fill rounded-full"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>

      {/* Reward chart */}
      {rewardData.length > 1 && (
        <div className="h-28">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rewardData} margin={{ top: 2, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="step" tick={{ fontSize: 9, fill: '#52525b' }} />
              <YAxis tick={{ fontSize: 9, fill: '#52525b' }} domain={[-1, 1]} />
              <Tooltip
                contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: '#a1a1aa' }}
              />
              <Bar dataKey="reward" radius={[2, 2, 0, 0]}>
                {rewardData.map((d, idx) => (
                  <Cell key={idx} fill={d.reward >= 0 ? '#22c55e' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
