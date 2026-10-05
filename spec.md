# Saksham Engine: Prototype Specification (v2)

> **Instruction to the coding agent:** Read this whole document first. Then produce a written implementation plan (phases, files, order of work, risks) and wait for my confirmation before writing code. Keep the code simple, typed and tested. This is a hackathon prototype that must demo reliably, so prefer boring and robust choices over clever ones. **Never log, print or commit secrets** (see section 9).

---

## 1. Context and goal

**Event:** TVS Credit e.p.i.c Season 8 (IT hackathon).
**Problem statement:** Build an alternative credit engine for customers who have no CIBIL score (credit-invisible / thin-file customers).

TVS Credit lends for two-wheelers, tractors, used cars and mobile loans, largely in Tier 3/4 towns and rural India. Bureau-based underwriting is built around formal income proof and past credit history. Gig workers, small-town merchants, farmers and other informal earners often have real cash flow but return **NO_HIT** at the bureau and get auto-rejected, pushing them toward moneylenders.

**Solution, "Saksham Engine":** a consent-based safety net that sits *beside* the existing bureau check. It fires only when the bureau has no usable score. It reads alternative data (account aggregator bank-statement data (which includes UPI transactions), telecom behaviour, and business records such as GST returns or mandi receipts), produces an explainable 300–900 score, and either approves into the existing loan flow or sends the applicant a plain-language improvement plan in their own language **on WhatsApp**.

The engine is **segment-agnostic**: it serves any no-CIBIL applicant. Different applicants will have different data available, so the design must handle partial data gracefully (section 3, decisions 7 and 8). That is a general robustness property, not a special case around one customer type.

**What the prototype must prove in a ~4–5 minute live demo:**
1. A dealer starts an application and the bureau returns no-hit.
2. The applicant receives a **real WhatsApp message** with a consent link, and gives granular, revocable consent on their phone.
3. Alternative signals are pulled in parallel and scored in well under a second.
4. Approve path: score, reasons, and a handoff to the (mock) LOS.
5. Decline path: SHAP reasons become a vernacular (Hindi/Marathi) action plan delivered on WhatsApp.
6. Graduation ladder: simulated on-time repayments raise the score and unlock a larger limit.

---

## 2. Scope: real vs mocked

| Component | Prototype status |
|---|---|
| Dealer POS UI, API gateway, orchestration, state machine | **Real** |
| Consent artifact (signed, granular, revocable, TTL) and consent web page | **Real** |
| Feature engineering, LightGBM model, calibration, scorecard, SHAP | **Real** (trained on **synthetic** data; say so in the README and UI footer) |
| Reason codes and vernacular advisory (LLM + deterministic fallback) | **Real** |
| **WhatsApp messaging (Meta Cloud API, test number)** | **Real**, with a simulated mirror and fallback (section 10) |
| Graduation ladder logic | **Real** (driven by simulated repayment events) |
| Credit bureau, AA bank statements (UPI appears as transactions inside them), telecom, business-record feeds (GST or mandi) | **Mocked** HTTP services behind adapter interfaces |
| TVS LOS, LMS, e-NACH/NPCI | **Mocked** adapters (in-process) |

---

## 3. Architectural decisions (already made)

1. **Ports-and-adapters (hexagonal).** The core domain never calls vendors directly. Define abstract interfaces: `BureauAdapter`, `DataSourceAdapter` (one per source), `LOSAdapter`, `LMSAdapter`, `MessagingProvider`, `LLMClient`. Ship mock implementations (and the real WhatsApp one). This is how we show "integrates with TVS's existing systems": swap a mock for a real client and nothing else changes.
2. **No Redis.** Session state lives in the database (`expires_at` column, 15-minute TTL, lazily enforced on read). Do not mention Redis anywhere.
3. **No Celery.** Parallel ingestion uses `asyncio.gather` with `httpx.AsyncClient`, a per-source timeout (default 3 s) and graceful degradation.
4. **Mock services are routers in the same FastAPI app** under `/mock/*`, called over HTTP via a configurable base URL.
5. **SQLite** via SQLAlchemy for all persistence. One file, easy to reset.
6. **Bureau-first, non-intrusive.** Bureau score ≥ 700 → straight to the existing LOS, Saksham not invoked. `NO_HIT` / score `-1` → Saksham. Bureau hit with score < 700 → also routed to LOS unchanged (out of scope; "Saksham as second opinion" is future work).
7. **Missing data is a first-class case.** LightGBM handles NaN natively. Every source group has an availability flag feature. A source that times out, is not consented to, or simply has no data for that applicant produces NaN features plus `src_<name>_available = 0`, never a crash.
8. **Insufficient data outcome.** If fewer than 2 of the 3 source groups return usable data, the outcome is `INSUFFICIENT_DATA` (refer for manual review). Do not score near-empty vectors.
9. **Auditability is real.** Every decision writes an immutable audit record: model version, policy version, consent_id, feature-vector hash, score, PD, top SHAP contributions, outcome, timestamps.
10. **Privacy by design.** Store only tokenized identifiers (HMAC of PAN/Aadhaar tokens). Discard raw payloads after feature extraction (keep only the feature vector). On consent revocation, purge the stored feature vector and mark the consent revoked.
11. **Config-driven policy.** Cutoffs, bureau bypass threshold, score parameters, product catalog and consent TTL live in `policy.yaml`.
12. **Single origin for the demo.** In demo mode, the backend serves the built frontend as static files, so one origin (and one tunnel) serves the dealer UI, the consent page and the API.
13. **Demo resilience.** Deterministic seeds, `/demo/reset`, pre-loaded model artifacts, offline LLM fallback, one-click persona loading, and a messaging fallback to the simulated phone if WhatsApp fails.
14. **UPI is not a separate source.** UPI activity is only visible as transactions (with a `mode` and `narration`) inside the AA bank statement. There is one AA feed. UPI features are derived from it.
15. **Train/serve parity via a shared raw-payload generator.** One generator module produces raw source payloads (AA, telecom, GST, mandi). It powers both the `/mock/*` services (for live demo personas) and training-data creation. Training rows are built by running those raw payloads through the **same feature pipeline function** used at inference. Never generate feature values directly for training, and never keep a second feature code path.

---

## 4. Tech stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, httpx, pandas, numpy, scikit-learn, LightGBM, SHAP, joblib, PyYAML, pytest.
- **Frontend:** React + Vite + TypeScript + Tailwind, Recharts (or similar) for the SHAP waterfall and score gauge. Polling or SSE for live updates. The consent page and plan page must be **mobile-first**, since they open on a real phone.
- **Messaging:** WhatsApp Business **Cloud API** (Meta Graph API) behind `MessagingProvider`, plus a simulated provider.
- **LLM:** provider-agnostic `LLMClient`. Default implementation uses the Anthropic API (`ANTHROPIC_API_KEY`, model name from `LLM_MODEL`; prefer a fast model). If the key is missing, or the call errors or times out (3–4 s), use deterministic templates.
- **Run:** `make dev`, `make train`, `make seed`, `make build-demo`, `make check-whatsapp`.

---

## 5. End-to-end flow and state machine

```
CREATED
  → BUREAU_CHECKED
      → BYPASSED_TO_LOS            (bureau score >= 700, or hit but < 700)
      → AWAITING_CONSENT           (NO_HIT; WhatsApp consent request sent)
          → CONSENT_DENIED         (terminal; no data pulled)
          → EXPIRED                (15 min TTL passed)
          → CONSENT_GRANTED
              → INGESTING → SCORED
                  → APPROVED            (score >= cutoff) → handed to LOS, e-NACH mocked, LMS account created
                  → DECLINED_WITH_PLAN  (score < cutoff)  → SHAP reasons → LLM/template → WhatsApp message
                  → INSUFFICIENT_DATA   (fewer than 2 usable source groups)
```

Every transition is timestamped and stored so the UI can render a live "pipeline trace". Message delivery status (sent / delivered / read) from WhatsApp webhooks is attached to the trace when available.

---

## 6. API contracts (v1)

All JSON. Consistent error shape `{ "error": { "code": "...", "message": "..." } }`.

**Core**
- `POST /api/v1/applications/create`: body `{ mobile_number, pan_token, aadhaar_token, requested_product_sku }`. Runs the bureau check; on no-hit creates the session and sends the consent request. Returns `{ application_id, status, session_id?, consent_url? }`.
- `GET /api/v1/applications/{id}`: full state, outcome, timeline.
- `GET /api/v1/applications/{id}/trace`: ordered stages with latency per stage and message delivery status.
- `GET /api/v1/applications/{id}/decision`: score, PD, outcome, top SHAP drivers (positive and negative, with reason codes), audit record id.

**Consent**
- `POST /api/v1/consent/authorize`: body `{ session_id, grants: { aa: bool, telecom: bool, business: bool }, purpose }`. Returns a signed consent artifact `{ consent_id, session_id, grants, granted_at, expires_at (6 months), revocable: true, signature }` (HMAC-SHA256 with a server secret). Triggers ingestion in the background.
- `POST /api/v1/consent/revoke`: body `{ consent_id }`. Marks revoked and purges stored features.
- Mock data endpoints **reject requests without a valid, unrevoked consent token covering that source**. This proves consent is enforced.

**Mock data sources** (deterministic, seeded by `mobile_number` → persona)
- `POST /mock/bureau/check` → `{ status: "HIT"|"NO_HIT", score: int|-1 }`
- `GET /mock/aa/bank-statement` → 180 days of balances and transactions. UPI activity appears as transactions with `mode = UPI`, not as a separate feed.
- `GET /mock/telecom/recharge` → 12 months: recharge dates and values, plan type, SIM tenure
- `GET /mock/business/gst-returns` → monthly turnover and filing dates (for merchants)
- `GET /mock/business/mandi-receipts` → trade receipts: date, crop, quantity, rate, settlement amount, settlement delay (for farmers)
- The `business` consent group maps to whichever business-record feed applies to the applicant; an applicant may have neither (e.g. a gig worker), which is the data-gap case.
- Each source supports a flag to **simulate an outage** (for the graceful-degradation demo).

**Payload shapes** (the contract shared by the mock services, the generators and the feature pipeline; keep them compact):
- **AA bank statement:** `{ "account": {...}, "balances": [{date, balance}], "transactions": [{date, amount, type: "CREDIT"|"DEBIT", mode: "UPI"|"NEFT"|"IMPS"|"CASH"|"ATM"|"ECS_RETURN"|"OTHER", narration, balance}] }`. Mandate bounces are `ECS_RETURN` or return-charge transactions. Cash vs digital inflow and UPI counterparties are derived from `mode` and `narration`.
- **Telecom:** `{ "sim_start_date", "recharges": [{date, amount, plan_type}] }`
- **GST returns:** `{ "gstin_token", "returns": [{period, turnover, filed_on}] }`
- **Mandi receipts:** `{ "receipts": [{date, crop, quantity, rate, settlement_amount, settlement_date}] }`
- Note: in the real AA ecosystem GST is another AA data type, while telecom and mandi data would come from separate partners. They are kept as separate mock feeds on purpose to demonstrate multi-source ingestion.

**Ladder / LMS (simulated)**
- `POST /api/v1/lms/repayment-event`: body `{ loan_id, status: "ON_TIME"|"LATE"|"MISSED" }`.
- `GET /api/v1/customers/{id}/ladder`: current tier, internal behaviour score, current limit, next tier and the requirement to reach it.

**Messaging and webhooks**
- `GET /api/v1/messages/{application_id}`: the message outbox (everything sent, regardless of provider), consumed by the in-app phone mirror.
- `GET /webhooks/whatsapp`: Meta verification challenge (uses `WHATSAPP_VERIFY_TOKEN`).
- `POST /webhooks/whatsapp`: inbound messages and delivery statuses. Record inbound messages (to track the 24-hour service window) and statuses (sent/delivered/read).
- `GET /plan/{application_id}`: mobile-first web page rendering the full action plan (used as the fallback target of a template message).

**Demo helpers**
- `POST /demo/reset`: wipe the database and reseed personas.
- `GET /demo/personas`: preloaded personas and the mobile numbers that map to them.

---

## 7. Signals and feature engineering (~40 features, one row per applicant)

Modular pandas pipeline, one function per feature group, each unit-tested. Target: feature build plus inference under **200 ms** (measure and display it).

**Single pipeline contract:** `build_features(raw_payloads, requested_emi) -> feature_row` is the only function that turns raw source payloads into model input. Training, tests and live inference must all call it. Add a **parity test**: the same raw payloads must produce an identical feature vector in the training path and the serving path.

**Bank statement incl. UPI (AA)** (UPI features come from transactions where `mode = UPI`, not from a separate source)
- `buffer_ratio` = average daily balance ÷ target monthly EMI
- `bounce_velocity` = sum of e-mandate/ECS failures in the last 90 days
- Income regularity (coefficient of variation of monthly inflows), inflow count, distinct UPI counterparties, cash vs digital inflow share, minimum-balance days, balance trend

**Telecom**
- Recharge frequency regularity (std of gaps), recharge count over 12 months, average recharge value and trend, SIM tenure (months), longest gap without recharge

**Business records (segment-dependent, NaN when not applicable)**
- Merchants (GST): turnover level, month-to-month volatility, filing consistency, growth trend
- Farmers (mandi): settlement frequency, distinct harvest cycles, average monthly settlement, settlement delay, crop diversity, tenure

**Affordability and application**
- Requested EMI, `est_monthly_income` (blend of the best available sources), `emi_to_income_ratio`, product type, ticket size

**Availability flags**
- `src_aa_available`, `src_telecom_available`, `src_business_available`, plus a data-completeness score

Keep monotonic intuition: more regularity, buffer, tenure and turnover stability = lower risk; more bounces, longer gaps, longer settlement delays = higher risk.

---

## 8. Model, calibration and scorecard

**Training data: synthetic, generated at the raw-payload level.** Write the shared generator in `backend/app/mock_services/generators.py` and a thin `ml/generate_data.py` that calls it:
- Draw a latent creditworthiness variable per applicant. Generate **raw source payloads** (AA transactions, telecom recharges, GST or mandi records) whose statistics depend on it plus noise. Then run every applicant through `build_features`. About 10k–30k applicants with compact payloads is enough. Demo personas are just fixed seeds of the same generator.
- Generate **segment-specific data availability**: merchants have GST but possibly sparse AA; farmers have mandi but possibly sparse AA; gig workers have heavy UPI/AA but no business records; some applicants have thin data in a source group. This trains the model to score well across partial vectors.
- Generate the default label from a logistic function of the latent variable plus a few interaction effects. Base default rate about 8–12%. 20–30k rows, fixed seed.
- State clearly in the README that this is synthetic and that production would begin in shadow mode on real outcomes.

**Model:** LightGBM binary classifier.
- Use **monotone constraints** on features where direction is obvious (buffer ratio, bounce velocity, regularity, EMI-to-income ratio) so the model is explainable and sane.
- Train/validation/test split, early stopping. Report AUC, KS, Brier score and a calibration curve to `ml/artifacts/report.md`, plus AUC **per segment**.
- **Calibration** is a separate step: Platt scaling on held-out raw scores, producing a calibrated PD.
- Save the model, calibrator and feature schema with joblib, versioned (`model_version`).

**Scorecard mapping** (PD → score; do **not** use a linear PD × 600 mapping):

```
odds_good = (1 - PD) / PD
Score     = Offset + Factor * ln(odds_good)
Factor    = PDO / ln(2)
```

Defaults (config-driven): `PDO = 60`, and `Offset` chosen so **score 650 ↔ PD ≈ 7%**. Clamp to 300–900. Generate a "score → PD" lookup table into `report.md`.

**Decision policy:** approve if score ≥ cutoff (default 650), else decline with plan. Optional stretch: a borderline band 600–649 → "approve smaller ticket / add co-applicant".

**Explainability:** `shap.TreeExplainer` on the raw model per applicant. Map each feature to a reason code via `reason_codes.yaml`: code, English text, positive driver or negative drag, and a deterministic action template per language (en/hi/mr). Return the top 3 negative and top 3 positive drivers, plus data for a waterfall chart.

---

## 9. Consent, privacy and secrets

**Consent**
- Granular toggles per source group (AA, telecom, business records), each with a purpose string and a plain-language description.
- The consent page opens from the WhatsApp message via a one-time tokenized URL tied to `session_id`. It **must be reachable from a real phone**, so URLs are built from `PUBLIC_BASE_URL` (a tunnel such as ngrok or cloudflared, or a free host). Never build links from `localhost`.
- The artifact is HMAC-signed with the TTL (6 months). Verify signature and expiry on every data access.
- Revocation is available from the UI; revoking blocks future access and purges stored features.
- Log every consent event (granted, denied, revoked) in a `consent_log` table.

**Secrets**
- All secrets come from environment variables loaded from a git-ignored `.env`. Commit only `.env.example` with placeholders. Never print tokens in logs, traces, error messages or the UI. Mask them if a config dump is needed.

---

## 10. Messaging: real WhatsApp Cloud API

I have an existing Meta app with an access token and a test phone number. Design around its constraints (**verify each against Meta's current docs before relying on it**).

**Provider design**
- `MessagingProvider` interface: `send_template(to, template_name, language, params)`, `send_text(to, body)`, `parse_webhook(payload)`.
- Implementations: `WhatsAppCloudProvider` (POST to the Graph API `/{WHATSAPP_PHONE_NUMBER_ID}/messages` with a Bearer token) and `SimulatedProvider`.
- `MESSAGING_MODE = whatsapp | simulated | both`. **Every outgoing message is always written to the outbox table**, regardless of mode, so the in-app phone mirror works and acts as an automatic fallback. If a real send fails (network, token, window), log the error (without secrets), mark the message `failed_real_send`, and continue the flow using the simulated mirror.
- Config via env: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_VERSION` (do not hardcode the version), `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` (optional, for webhook signature checks), `DEMO_RECIPIENT_NUMBER`, `PUBLIC_BASE_URL`.

**Constraints to design around**
1. **Recipient restrictions.** A test number can usually message only a short list of pre-verified recipient numbers. Personas have fake mobile numbers, so when sending for real, **override the recipient with `DEMO_RECIPIENT_NUMBER`** (my own or a teammate's verified phone). The mock persona number is still used for data lookup.
2. **24-hour service window.** Business-initiated messages outside the window must use approved **templates**. Free-form text is allowed only within 24 hours of the user's last inbound message.
3. **Templates need approval.** Only a default sample template is pre-approved. I will create and submit templates early (see below). Until they are approved, the consent request is simulated-only.
4. **Token lifetime.** Temporary tokens expire (about 24 hours). I will refresh or use a long-lived system-user token before the demo. `make check-whatsapp` must validate credentials and send a test message, so expiry is caught early.
5. **Webhooks need public HTTPS**, hence the tunnel and `PUBLIC_BASE_URL`.

**Message plan**
1. **Consent request:** template `saksham_consent_request` (languages en/hi/mr) with variables for first name and the consent URL. Sent when the bureau returns no-hit.
2. **Result delivery** (in order of preference):
   - If the 24-hour window is open (the applicant tapped "Continue on WhatsApp" on the consent page, a `wa.me` deep link with prefilled text that opens the window, and the inbound webhook recorded it), send the full decision or action plan as free-form text.
   - Otherwise send template `saksham_status_update` (short summary plus a link to `/plan/{application_id}`, which renders the full plan on a mobile page).
3. **Delivery status:** consume webhook statuses and show sent → delivered → read in the trace panel.

**Message copy rules:** UTF-8 Devanagari must render correctly (Hindi and Marathi). Keep template variables free of newlines and tabs. Respect template body length limits.

---

## 11. LLM vernacular advisory

- Input: top 3 negative reason codes with their deterministic action templates, target language (`en`, `hi`, `mr`), product, first name.
- Output: strict JSON `{ greeting, summary, steps: [3 items], closing }`, rendered into a WhatsApp-style message.
- **Guardrails** (system prompt plus post-validation): never reveal the score formula, never promise approval, never invent numbers not provided, respectful and simple language, 3 steps maximum.
- **Fallback:** missing API key, error, timeout or invalid JSON → render the deterministic template for that language. It must read naturally and work fully offline.
- Cache outputs per (reason codes, language).

---

## 12. Graduation ladder

- On approval, create a mock LMS loan account.
- Simulated repayment events update an internal behaviour score: on-time payments add points (capped), late payments subtract, missed payments subtract more.
- Tiers map to limits via config (starter small-ticket → mid-ticket → larger product). Show current tier, next tier and what is needed to reach it.
- Demo control: a button "Simulate 6 on-time EMIs" that visibly raises the score and unlocks the next tier.

---

## 13. Frontend (single app, projector-friendly)

Coordinated views, with a persona selector and a language toggle (EN/HI/MR):

1. **Dealer POS:** application form (prefilled by persona), live status timeline, final decision card.
2. **Phone mirror:** a phone-frame view of the outbox messages and the consent/plan pages. The audience cannot see a real phone, so this mirror is what the projector shows while the real phone also receives the message. **These screens will be screenshotted for slides, so they must look polished.**
3. **"Under the hood" panel:** live pipeline trace with per-stage latency, source status (ok / timeout / not consented / no data), message delivery status, score gauge (300–900 with cutoff marked), SHAP waterfall, and the ladder visual after approval.
4. **Mobile pages:** `/consent/{session_id}` and `/plan/{application_id}`, mobile-first, same design language.

Footer: "Prototype trained on synthetic data." Use a clear visual language: green for approve, amber (not red) for "guidance".

---

## 14. Demo personas (seeded, deterministic; segment-diverse)

| # | Persona | Data profile | Expected outcome |
|---|---|---|---|
| 1 | Small-town merchant | Steady UPI and bank inflows, GST filings, regular recharges | `APPROVED` |
| 2 | Gig rider | UPI-heavy, irregular inflows, low buffer, several bounces, no business records | `DECLINED_WITH_PLAN` (Hindi) |
| 3 | Farmer | Regular mandi settlements, steady recharges, sparse bank data | `APPROVED` (shows partial-data handling) |
| 4 | Struggling farmer | Few receipts, long settlement delays, recharge gaps | `DECLINED_WITH_PLAN` (Marathi) |
| 5 | Prime salaried | Bureau hit, score 760 | `BYPASSED_TO_LOS` |
| 6 | Consent denier | NO_HIT, denies consent | `CONSENT_DENIED`, no data requested |
| 7 | Outage case | Persona 1 with the AA source forced to time out | Still `APPROVED` using remaining sources |

Write a pytest that runs all seven end to end and asserts the expected outcome (with messaging in `simulated` mode).

---

## 15. Suggested repository layout

```
saksham/
  README.md
  Makefile
  .env.example
  policy.yaml
  reason_codes.yaml
  backend/
    app/
      api/            # routers: applications, consent, lms, messages, webhooks, demo
      core/           # config, security (HMAC, tokenization, secret masking), db, logging
      domain/         # entities, state machine, policy engine, scorecard
      adapters/       # interfaces + implementations (bureau, sources, los, lms, messaging [whatsapp + simulated], llm)
      services/       # orchestrator, feature pipeline, scoring, explainability, advisory, ladder
      mock_services/  # /mock/* routers + shared raw-payload generators (used by mock APIs AND training)
    ml/
      generate_data.py  # calls shared generators, runs build_features, adds labels
      train.py
      artifacts/
    tests/
  frontend/
    src/              # views: DealerPOS, PhoneMirror, UnderTheHood, ConsentPage, PlanPage
  scripts/
    check_whatsapp.py
  docs/
```

---

## 16. Delivery phases (each with an acceptance check)

**Parallel tasks for me (the human), start immediately**
- Create and submit the WhatsApp templates (`saksham_consent_request`, `saksham_status_update`, in en/hi/mr if possible) because approval takes time.
- Refresh or create a long-lived access token, add my own phone to the test number's verified recipients, and set up a tunnel or free host for `PUBLIC_BASE_URL`.

**Phases**
0. **Scaffold:** repo, config, `.env.example`, DB models, Makefile, health endpoint. *Check: `make dev` runs both apps.*
1. **Mock world:** shared raw-payload generators (segment- and persona-seeded), mock bureau and source services, consent enforcement. *Check: curl each endpoint for persona 1 with and without a valid consent token.*
2. **ML:** feature pipeline (single code path for training and inference), synthetic raw-level training data, training, calibration, scorecard, reason codes, `report.md`. *Check: the parity test passes (same payloads give the identical feature vector in training and serving); AUC (overall and per segment) and calibration reported; score↔PD table generated; cutoff 650 ↔ about 7% PD.*
3. **Orchestration:** state machine, bureau triage, consent flow, async ingestion with timeouts and degradation, scoring, decision, audit record. *Check: personas 1–7 pass the end-to-end test in simulated mode.*
4. **Messaging:** outbox, simulated provider, **WhatsApp Cloud provider**, webhooks, template and free-form logic with fallbacks, `check-whatsapp` script. *Check: a real consent message arrives on my phone; a real Hindi plan arrives; failure of the real send degrades to the mirror without breaking the flow.*
5. **Advisory:** LLM client plus deterministic fallback, EN/HI/MR templates. *Check: persona 4 yields a valid Marathi plan with the API key unset.*
6. **Ladder:** LMS simulation, tiers, repayment events. *Check: six on-time events move the customer to the next tier.*
7. **Frontend:** all views, live trace, charts, mobile pages. *Check: full demo on personas 1 and 2 without touching the terminal.*
8. **Hardening:** `/demo/reset`, timing display, error states, single-origin demo build, README with screenshot instructions. *Check: cold start to demo-ready in under 2 minutes; the whole flow also works with `MESSAGING_MODE=simulated` and the internet off.*

---

## 17. Explicitly out of scope

Real AA, UPI, NPCI e-NACH or credit bureau integrations; authentication beyond a demo dealer login; production deployment; training on real customer data; multi-tenant concerns; WhatsApp production number registration.

## 18. Assumptions to confirm in your plan

State your assumptions and anything you need me to decide before coding, for example: exact ticket sizes and EMI formula per product SKU, which languages to template, charting library, tunnel choice, and whether to include the optional borderline band.