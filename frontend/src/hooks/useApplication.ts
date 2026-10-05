import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { ApplicationView, Decision, Message, Trace } from '../api/types'
import { usePolling } from './usePolling'

const DECISION_STATES = ['APPROVED', 'CONDITIONAL_APPROVAL', 'DECLINED_WITH_PLAN', 'INSUFFICIENT_DATA']

/** Polls application, trace and outbox every 2 s while the flow is live; keeps polling messages a bit after the end for delivery ticks. */
export function useApplication(id: string | null) {
  const [settledAt, setSettledAt] = useState<number | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)

  const app = usePolling<ApplicationView | null>(() => (id ? api.application(id) : Promise.resolve(null)), 2000, !!id && !settledAt)
  // Polling keeps its last data when `id` changes; only ever reason about data that belongs to the CURRENT id
  // (otherwise the previous application's "terminal" state would stop polling for the new one).
  const cur = id && app.data?.application_id === id ? app.data : null
  const live = !!id && (!cur?.terminal || (settledAt !== null && Date.now() - settledAt < 20000))
  const trace = usePolling<Trace | null>(() => (id ? api.trace(id) : Promise.resolve(null)), 2000, live)
  const messages = usePolling<Message[]>(() => (id ? api.messages(id) : Promise.resolve([])), 2000, live)

  const status = cur?.status
  const terminal = cur?.terminal
  const prevId = useRef<string | null>(null)

  useEffect(() => {
    if (prevId.current !== id) { prevId.current = id; setSettledAt(null); setDecision(null) }
  }, [id])

  useEffect(() => {
    if (terminal && settledAt === null) setSettledAt(Date.now())
  }, [terminal, settledAt])

  // After the terminal state, keep polling messages/trace for ~20 s (delivery ticks), then stop.
  const [, force] = useState(0)
  useEffect(() => {
    if (settledAt === null) return
    const t = setTimeout(() => force((n) => n + 1), 20500)
    return () => clearTimeout(t)
  }, [settledAt])

  useEffect(() => {
    if (id && status && DECISION_STATES.includes(status) && status !== 'INSUFFICIENT_DATA') {
      api.decision(id).then(setDecision).catch(() => undefined)
    }
  }, [id, status])

  const refreshAll = async () => { await Promise.all([app.refresh(), trace.refresh(), messages.refresh()]) }
  // Polling stops when `id` is null but keeps its last data — only expose data that belongs to the CURRENT id,
  // otherwise "New application" / "Reset demo" would keep showing the previous application.
  return {
    app: cur,
    trace: id && trace.data?.application_id === id ? trace.data : null,
    messages: id ? (messages.data ?? []).filter((m) => m.application_id === id) : [],
    decision: id && decision?.application_id === id ? decision : null,
    error: app.error, refreshAll, setSettledAt,
  }
}
