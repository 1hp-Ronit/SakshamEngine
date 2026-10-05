import { useCallback, useEffect, useRef, useState } from 'react'

/** Poll `fn` every `intervalMs` while `enabled`. The latest `fn` is always used (no stale closures). */
export function usePolling<T>(fn: () => Promise<T>, intervalMs: number, enabled = true) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const refresh = useCallback(async () => {
    try {
      setData(await fnRef.current())
      setError(null)
    } catch (e) {
      setError(e as Error)
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    const tick = async () => {
      await refresh()
      if (!stopped) timer = setTimeout(tick, intervalMs)
    }
    tick()
    return () => { stopped = true; clearTimeout(timer) }
  }, [enabled, intervalMs, refresh])

  return { data, error, refresh, setData }
}
