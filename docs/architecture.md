# Architecture notes

## Request flow

```
POST /api/v1/applications/create
  → create Application (PAN/Aadhaar tokenised) → BureauAdapter.check()  [timeline: BUREAU_CHECK]
      HIT            → BYPASSED_TO_LOS (LOSAdapter.handoff)
      NO_HIT         → ConsentSession (TTL 15 min) → consent request message → AWAITING_CONSENT
POST /api/v1/consent/authorize
  → signed ConsentArtifact (HMAC-SHA256, 6 months) → CONSENT_GRANTED → background task:
      INGESTING  asyncio.gather(AA, telecom, business) — consent-gated, 3 s timeout each, never raises
      < 2 usable sources → INSUFFICIENT_DATA (manual review, nothing is scored)
      build_features() → LightGBM → Platt → scorecard → SHAP → reason codes
      SCORED → policy → APPROVED | CONDITIONAL_APPROVAL | DECLINED_WITH_PLAN
      audit record (insert-only) → LOS/LMS (approved) | advisory plan → WhatsApp (declined)
```

Every transition and stage is a `timeline_events` row (stage, status, latency) — the UI's pipeline trace and status timeline are rendered from it.

## State machine
`CREATED → BUREAU_CHECKED → {BYPASSED_TO_LOS | AWAITING_CONSENT → {CONSENT_DENIED | EXPIRED | CONSENT_GRANTED → INGESTING → {SCORED → {APPROVED | CONDITIONAL_APPROVAL | DECLINED_WITH_PLAN | INSUFFICIENT_DATA} | INSUFFICIENT_DATA}}}`
Illegal transitions raise `INVALID_TRANSITION` (`domain/state_machine.py`). Session expiry is **lazy**: it is applied whenever a session or application is read.

## Ports and adapters
| Port | Mock / real implementation | Swap point |
|---|---|---|
| `BureauAdapter` | `MockBureauAdapter` → HTTP `/mock/bureau/check` | `adapters/registry.py` |
| `DataSourceAdapter` ×3 | `MockAA/Telecom/BusinessAdapter` → HTTP `/mock/*` | `adapters/registry.py` |
| `LOSAdapter`, `LMSAdapter` | in-process mocks (LMS backed by the ladder service) | `adapters/registry.py` |
| `MessagingProvider` | `WhatsAppCloudProvider`, `SimulatedProvider`; routed by `MessagingManager` | `adapters/messaging/manager.py` |
| `LLMClient` | `GeminiLLMClient` (REST/httpx), `DeterministicFallbackClient` | `services/advisory.py` |

## Consent enforcement
Every `/mock/*` data endpoint calls `consent.verify_for_source()`: artifact exists → not revoked → not expired → **signature valid** → covers the requested group → issued for *this* customer.
Tampering with the stored grants (without re-signing) is rejected (`CONSENT_INVALID`). The business adapter maps the `business` group to GST and/or mandi, whichever has data.

## Scoring maths
`Score = Offset + Factor · ln((1−PD)/PD)`, `Factor = PDO/ln 2`, `Offset = target_score − Factor·ln((1−target_pd)/target_pd)` (or an explicit `scorecard.offset`). Clamped to [300, 900].
SHAP runs on the raw LightGBM margin; contributions are shown in **score points**: `points = −shap · platt_slope · Factor`, so the waterfall adds up to the score.
Reason lists skip features whose value is missing (a missing GST feed is not an action) and features marked `reportable: false` in `reason_codes.yaml`.

## Advisory guardrails
Input: top-3 negative reason codes with their deterministic action templates. LLM output must be strict JSON with ≤ 3 steps, contain no forbidden phrase (`policy.yaml`),
**no number that was not in the input**, and be in the right script; otherwise the deterministic plan is used. Results are cached by (reason codes, language, product, name).

## Data model
`applications` · `consent_sessions` · `consent_artifacts` · `consent_log` · `audit_records` · `timeline_events` · `messages` · `loans` · `repayment_events` (SQLite via SQLAlchemy 2 async, WAL).
