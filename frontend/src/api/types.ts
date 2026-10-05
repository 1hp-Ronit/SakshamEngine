export type Lang = 'en' | 'hi' | 'mr'
export type Group = 'aa' | 'telecom' | 'business'

export interface Persona {
  id: number
  key: string
  name: string
  description: string
  mobile_number: string
  pan_token: string
  aadhaar_token: string
  product_sku: string
  product_label: string
  language: Lang
  emi: number
  ticket: number
  expected_outcome: string
  consent_behaviour?: 'deny'
  simulate_outage?: Group[]
}

export interface ProductInfo { label: string; ticket: number; emi: number; tenure_months: number }

export interface PublicConfig {
  dealer: string
  public_base_url: string
  messaging: { mode: string; whatsapp_configured: boolean; real_sends_enabled: boolean; demo_recipient_set: boolean }
  llm: { provider: string; available: boolean; model: string; fallback_only: boolean }
  model: { loaded: boolean; version: string | null; metrics: { auc: number; ks: number } | null }
  policy: { version: string; comfortable_emi_ratio: number; approve_cutoff: number; borderline_floor: number | null; bureau_bypass_threshold: number; session_ttl_minutes: number }
  products: Record<string, ProductInfo>
  languages: Lang[]
  withdrawal_reasons: string[]
}

export interface TimelineStage {
  stage: string
  status: string
  latency_ms: number | null
  timestamp: string
  details: Record<string, unknown> | null
}

export interface LadderTier { name: string; min_behaviour_score: number; limits: Record<string, number> }
export interface Ladder {
  loan_id: string
  customer_id: string
  product_sku: string
  behaviour_score: number
  current_tier: string
  current_limit: number
  tier_limits: Record<string, number>
  next_tier: string | null
  next_tier_requirement: string | null
  next_tier_min_score: number | null
  next_tier_limits: Record<string, number> | null
  next_tier_unlocks: string[]
  tiers: LadderTier[]
  max_score: number
  tier_changed?: boolean
  previous_tier?: string
  steps?: { behaviour_score: number; tier: string }[]
}

export interface ConsentArtifact {
  consent_id: string
  grants: Record<Group, boolean>
  granted_at: string
  expires_at: string
  revoked: boolean
  signature: string
}

export interface ApplicationView {
  application_id: string
  status: string
  outcome: string | null
  terminal: boolean
  applicant_name: string
  mobile_masked: string
  language: Lang
  product_sku: string
  product_label: string
  requested_emi: number
  tenure_months: number
  ticket_size: number
  suggested_ticket: number | null
  bureau: { status: string | null; score: number | null }
  session_id: string | null
  consent_url: string | null
  consent: ConsentArtifact | null
  score: number | null
  pd: number | null
  has_plan: boolean
  simulated_outage: Group[]
  withdrawal: { reason: string; withdrawn_at: string } | null
  loan: Ladder | null
  created_at: string
  updated_at: string
  timeline: TimelineStage[]
  transitions: { status: string; timestamp: string; from: string | null }[]
}

export interface Trace {
  application_id: string
  status: string
  stages: TimelineStage[]
  total_latency_ms: number | null
  sources: Record<string, { status: string; latency_ms: number | null; detail: string | null }>
  message_delivery: { consent_request?: string; result_delivery?: string }
}

export interface Driver {
  feature: string
  label: string
  value: number | null
  points: number
  shap_value: number
  reason_code: string | null
  reason_text: string
  reason_texts: Record<Lang, string>
  positive: boolean
}
export interface WaterfallItem { feature: string; label: string; points: number; value: number | null; positive: boolean }

export interface Decision {
  application_id: string
  affordability: { est_monthly_income?: number; emi_to_income_ratio?: number; buffer_ratio?: number; bounce_velocity?: number } | null
  score: number | null
  pd: number | null
  outcome: string
  suggested_ticket: number | null
  approve_cutoff: number
  shap_drivers: { positive: Driver[]; negative: Driver[] }
  waterfall: WaterfallItem[]
  base_score: number | null
  audit_record_id: string
  model_version: string
  policy_version: string
  consent_id: string | null
  feature_vector_hash: string | null
  decided_at: string
}

export interface Message {
  id: string
  application_id: string | null
  direction: 'OUTBOUND' | 'INBOUND'
  purpose: string
  provider: 'whatsapp' | 'simulated'
  message_type: string
  template_name: string | null
  recipient: string
  body: string
  link_url: string | null
  delivery_status: string
  stored_status: string
  error: string | null
  created_at: string
}

export interface ConsentSessionInfo {
  session_id: string
  application_id: string
  status: 'OPEN' | 'GRANTED' | 'DENIED' | 'EXPIRED'
  applicant_name: string
  language: Lang
  product_sku: string
  product_label: string
  product_labels: Record<Lang, string>
  purpose: string
  seconds_remaining: number
  expires_at: string
  groups: Group[]
  consent_valid_days: number
  whatsapp_link: string | null
}

export interface PlanView {
  application_id: string
  language: Lang
  available_languages: Lang[]
  product_label: string
  applicant_first_name: string
  greeting: string
  summary: string
  steps: string[]
  closing: string
  source: 'llm' | 'fallback'
}

export interface CreateResponse {
  application_id: string
  status: string
  session_id?: string
  consent_url?: string
  bureau_result: string
  bureau_score?: number
  message: string
}

// ── Consent & data-rights ledger (GET /api/v1/applications/{id}/ledger) ──
export interface LedgerConsent {
  consent_id: string
  grants: Record<Group, boolean>
  purpose: string
  granted_at: string
  expires_at: string
  revoked: boolean
  revoked_at: string | null
  active: boolean
}
export interface LedgerEvent {
  event: 'GRANTED' | 'DENIED' | 'REVOKED'
  timestamp: string
  consent_id: string | null
  details: Record<string, unknown> | null
}
export interface LedgerRead {
  source: Group
  status: 'ok' | 'timeout' | 'error' | 'not_consented' | 'no_data'
  accessed_at: string
  latency_ms: number | null
  consent_id: string | null
  detail: string | null
}
export interface Ledger {
  application_id: string
  applicant_name: string
  mobile_masked: string
  consents: LedgerConsent[]
  events: LedgerEvent[]
  data_access: LedgerRead[]
  holdings: {
    mobile_number: string
    identifiers: string
    raw_vendor_payloads: string
    feature_vector: string
    feature_vector_hash: string | null
    audit_record: string | null
  }
}

// ── Approved loans (GET /api/v1/applications?outcome=APPROVED) ──
export interface ApprovedLoan {
  application_id: string
  applicant_name: string
  mobile_masked: string
  product_label: string
  ticket_size: number
  requested_emi: number
  tenure_months: number
  score: number | null
  pd: number | null
  outcome: string
  decided_at: string | null
  los_reference: string | null
  consent_active: boolean
  loan: Ladder | null
}
export interface ApprovedLoansResponse {
  outcome: string
  count: number
  loans: ApprovedLoan[]
}
