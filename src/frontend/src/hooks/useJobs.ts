import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Job } from '../lib/api'

/** Recent jobs; polls every 2 s only while something is queued or running. */
export function useJobs(onFinished?: () => void) {
  const [jobs, setJobs] = useState<Job[]>([])
  const active = jobs.some((j) => j.status === 'queued' || j.status === 'running')
  const wasActive = useRef(false)

  const refresh = useCallback(() => api.jobs().then(setJobs, () => {}), [])
  useEffect(() => void refresh(), [refresh])
  useEffect(() => {
    if (wasActive.current && !active) onFinished?.()
    wasActive.current = active
    if (!active) return
    const id = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(id)
  }, [active, refresh, onFinished])

  return { jobs, refresh }
}
