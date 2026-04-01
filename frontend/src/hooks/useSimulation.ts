import { useState, useRef, useCallback } from 'react'
import type { SimResult, SimStep } from '../types'

interface SimState {
  result: SimResult | null
  currentStepIndex: number
  isPlaying: boolean
  isLoading: boolean
  error: string | null
}

const SPEED_MS: Record<string, number> = { slow: 2000, normal: 1000, fast: 400 }

export function useSimulation() {
  const [state, setState] = useState<SimState>({
    result: null,
    currentStepIndex: -1,
    isPlaying: false,
    isLoading: false,
    error: null,
  })
  const [speed, setSpeed] = useState<'slow' | 'normal' | 'fast'>('normal')
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const startPlayback = useCallback((_result: SimResult, fromIndex = 0) => {
    stopTimer()
    setState(s => ({ ...s, currentStepIndex: fromIndex, isPlaying: true }))

    timerRef.current = setInterval(() => {
      setState(s => {
        if (!s.result) return s
        const next = s.currentStepIndex + 1
        if (next >= s.result.steps.length) {
          stopTimer()
          return { ...s, isPlaying: false }
        }
        return { ...s, currentStepIndex: next }
      })
    }, SPEED_MS[speed])
  }, [speed])

  const load = useCallback(async (
    fetcher: () => Promise<SimResult>,
  ) => {
    stopTimer()
    setState({ result: null, currentStepIndex: -1, isPlaying: false, isLoading: true, error: null })
    try {
      const result = await fetcher()
      setState({ result, currentStepIndex: 0, isPlaying: false, isLoading: false, error: null })
      startPlayback(result, 0)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setState(s => ({ ...s, isLoading: false, error: message }))
    }
  }, [startPlayback])

  const pause = useCallback(() => {
    stopTimer()
    setState(s => ({ ...s, isPlaying: false }))
  }, [])

  const play = useCallback(() => {
    setState(s => {
      if (!s.result) return s
      startPlayback(s.result, s.currentStepIndex)
      return s
    })
  }, [startPlayback])

  const reset = useCallback(() => {
    stopTimer()
    setState(s => ({ ...s, currentStepIndex: 0, isPlaying: false }))
  }, [])

  const seekTo = useCallback((idx: number) => {
    stopTimer()
    setState(s => ({ ...s, currentStepIndex: idx, isPlaying: false }))
  }, [])

  const currentStep: SimStep | null =
    state.result && state.currentStepIndex >= 0
      ? state.result.steps[state.currentStepIndex] ?? null
      : null

  return {
    result: state.result,
    currentStep,
    currentStepIndex: state.currentStepIndex,
    isPlaying: state.isPlaying,
    isLoading: state.isLoading,
    error: state.error,
    speed,
    setSpeed,
    load,
    play,
    pause,
    reset,
    seekTo,
  }
}
