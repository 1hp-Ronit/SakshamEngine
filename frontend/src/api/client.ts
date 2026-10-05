import type {
  ApplicationView, ApprovedLoansResponse, ConsentSessionInfo, CreateResponse, Decision, Ladder, Lang, Ledger, Message, Persona, PlanView, PublicConfig, Trace,
} from './types'

export class ApiError extends Error {
  code: string
  status: number
  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  } catch {
    throw new ApiError('NETWORK', 'Cannot reach the server. Please check your connection.', 0)
  }
  const text = await res.text()
  let data: unknown = null
  try { data = text ? JSON.parse(text) : null } catch { /* non-JSON error page */ }
  if (!res.ok) {
    const err = (data as { error?: { code: string; message: string } } | null)?.error
    throw new ApiError(err?.code ?? 'HTTP_ERROR', err?.message ?? `Request failed (${res.status})`, res.status)
  }
  return data as T
}

const post = <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  config: () => request<PublicConfig>('/demo/config'),
  personas: () => request<{ personas: Persona[] }>('/demo/personas').then((r) => r.personas),
  reset: () => post<{ ok: boolean }>('/demo/reset'),
  create: (body: Record<string, unknown>) => post<CreateResponse>('/api/v1/applications/create', body),
  application: (id: string) => request<ApplicationView>(`/api/v1/applications/${id}`),
  trace: (id: string) => request<Trace>(`/api/v1/applications/${id}/trace`),
  decision: (id: string) => request<Decision>(`/api/v1/applications/${id}/decision`),
  plan: (id: string, lang?: Lang) => request<PlanView>(`/api/v1/applications/${id}/plan${lang ? `?lang=${lang}` : ''}`),
  messages: (id: string) => request<{ messages: Message[] }>(`/api/v1/messages/${id}`).then((r) => r.messages),
  consentSession: (sid: string) => request<ConsentSessionInfo>(`/api/v1/consent/session/${sid}`),
  authorize: (session_id: string, grants: Record<string, boolean>, purpose?: string) =>
    post<{ consent_id: string | null; denied?: boolean }>('/api/v1/consent/authorize', { session_id, grants, purpose }),
  deny: (session_id: string) => post('/api/v1/consent/deny', { session_id }),
  revoke: (consent_id: string) => post<{ revoked: boolean; features_purged: boolean }>('/api/v1/consent/revoke', { consent_id }),
  simulateRepayments: (loan_id: string, count = 6, status = 'ON_TIME') => post<Ladder>('/demo/simulate-repayments', { loan_id, count, status }),
  repayment: (loan_id: string, status: string) => post<Ladder>('/api/v1/lms/repayment-event', { loan_id, status }),
  approvedLoans: () => request<ApprovedLoansResponse>('/api/v1/applications?outcome=APPROVED'),
  ledger: (id: string) => request<Ledger>(`/api/v1/applications/${id}/ledger`),
  withdraw: (id: string, reason: string) => post<{ withdrawn: boolean; reason: string; withdrawn_at: string }>(`/api/v1/applications/${id}/withdraw`, { reason }),
}
