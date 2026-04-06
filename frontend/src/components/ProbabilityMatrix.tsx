import React from 'react'
import { motion } from 'framer-motion'
import type { PyTorchScore } from '../types'

interface Props {
  scores: PyTorchScore[]
}

// Convert 0.0 -> 1.0 urgency score into a color.
function getHeatmapColor(score: number, isFalseSos: boolean) {
  if (isFalseSos || score === 0) {
    return 'bg-purple-900/50 text-purple-300 neon-border-purple'
  }
  
  if (score > 0.75) return 'bg-red-900/50 text-red-300 neon-border-red'
  if (score > 0.4) return 'bg-orange-900/50 border-orange-500 text-orange-300'
  if (score > 0.1) return 'bg-yellow-900/50 border-yellow-500 text-yellow-300'
  
  return 'bg-green-900/30 text-green-500 neon-border-green'
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: { opacity: 1, scale: 1, transition: { type: 'spring' as any, stiffness: 300, damping: 24 } }
}

export function ProbabilityMatrix({ scores }: Props) {
  if (!scores || scores.length === 0) return null

  // Sort alphabetically
  const sorted = [...scores].sort((a, b) => a.zone_id.localeCompare(b.zone_id))

  return (
    // @ts-ignore
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-zinc-900 glass-panel rounded-xl p-4 mt-4"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-widest text-zinc-500 font-medium">PyTorch Probability Matrix</h3>
        <span className="text-[10px] bg-zinc-800 px-2 py-0.5 rounded text-zinc-400 border border-zinc-700">inference_latency ~1ms</span>
      </div>
      
      // @ts-ignore
      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-2 sm:grid-cols-5 gap-3"
      >
        {sorted.map(s => {
          const style = getHeatmapColor(s.score, s.is_false_sos_suspect)
          return (
            // @ts-ignore
            <motion.div 
              variants={itemVariants}
              key={s.zone_id} 
              className={`flex flex-col items-center justify-center p-3 rounded-lg border transition-colors duration-300 relative overflow-hidden ${style}`}
            >
              <span className="text-xs font-bold z-10 tracking-widest uppercase mb-1">{s.zone_id}</span>
              <div className="text-[14px] mono font-semibold z-10 flex items-baseline gap-1">
                {(s.score * 100).toFixed(0)}<span className="text-[10px] opacity-70">%</span>
              </div>
              
              {s.is_false_sos_suspect && (
                <div className="absolute inset-0 bg-purple-500/10 pointer-events-none" style={{ backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 5px, rgba(168, 85, 247, 0.2) 5px, rgba(168, 85, 247, 0.2) 10px)' }}></div>
              )}
            </motion.div>
          )
        })}
      </motion.div>
    </motion.div>
  )
}
