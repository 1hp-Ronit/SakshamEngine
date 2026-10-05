# Saksham Engine — the complete explainer

> **Who this is for:** someone who has never seen this project before and wants to understand
> every part of it — the business idea, every technology choice, how the model was trained and
> why that model, what happens to the data at each step, every API endpoint, every file.
>
> Nothing here is assumed knowledge. Jargon is defined the first time it appears.
> Every number quoted was produced by actually running the code, not estimated.

---

## Table of contents

**Part A — Orientation**
1. [The problem this solves](#1-the-problem-this-solves)
2. [What the product actually does](#2-what-the-product-actually-does)
3. [The five-minute mental model](#3-the-five-minute-mental-model)
4. [Repository map](#4-repository-map)

**Part B — Choices**
5. [Every technology, and why it was chosen](#5-every-technology-and-why-it-was-chosen)
6. [The configuration system: the "nothing hardcoded" rule](#6-the-configuration-system-the-nothing-hardcoded-rule)

**Part C — The data journey (the heart of it)**
7. [Stage 0: personas — what you pick in the UI](#7-stage-0-personas--what-you-pick-in-the-ui)
8. [Stage 1: the Profile — one number that drives everything](#8-stage-1-the-profile--one-number-that-drives-everything)
9. [Stage 2: raw payloads — what the "vendors" return](#9-stage-2-raw-payloads--what-the-vendors-return)
10. [Stage 3: what the backend receives after consent](#10-stage-3-what-the-backend-receives-after-consent)
11. [Stage 4: feature engineering — all 42 features](#11-stage-4-feature-engineering--all-42-features)
12. [Stage 5: the model's three outputs](#12-stage-5-the-models-three-outputs)
13. [Stage 6: the scorecard — PD to a 300–900 score](#13-stage-6-the-scorecard--pd-to-a-300900-score)
14. [Stage 7: the decision](#14-stage-7-the-decision)
15. [Stage 8: SHAP → reason codes → the waterfall](#15-stage-8-shap--reason-codes--the-waterfall)
16. [Stage 9: the vernacular action plan](#16-stage-9-the-vernacular-action-plan)
17. [The whole journey on one page](#17-the-whole-journey-on-one-page)

**Part D — The machine learning, in depth**
18. [Why LightGBM and not something else](#18-why-lightgbm-and-not-something-else)
19. [Monotone constraints: the most important ML decision here](#19-monotone-constraints-the-most-important-ml-decision-here)
20. [How the synthetic training data was made](#20-how-the-synthetic-training-data-was-made)
21. [Train/serve parity — and why it is enforced by a test](#21-trainserve-parity--and-why-it-is-enforced-by-a-test)
22. [The training run, step by step](#22-the-training-run-step-by-step)
23. [Calibration: why a second model sits on top](#23-calibration-why-a-second-model-sits-on-top)
24. [Every metric in the report, explained](#24-every-metric-in-the-report-explained)
25. [What this model is *not*](#25-what-this-model-is-not)
26. [SHAP, explained from scratch](#26-shap-explained-from-scratch)

**Part E — The system**
27. [Consent: the legal and technical core](#27-consent-the-legal-and-technical-core)
28. [Security and privacy mechanics](#28-security-and-privacy-mechanics)
29. [The state machine](#29-the-state-machine)
30. [The orchestrator: the one place the flow lives](#30-the-orchestrator-the-one-place-the-flow-lives)
31. [Hexagonal architecture (ports and adapters)](#31-hexagonal-architecture-ports-and-adapters)
32. [The mock vendors](#32-the-mock-vendors)
33. [The graduation ladder](#33-the-graduation-ladder)

**Part F — External integrations**
34. [WhatsApp / Meta Cloud API, in full](#34-whatsapp--meta-cloud-api-in-full)
35. [Google Gemini and the guardrails](#35-google-gemini-and-the-guardrails)
36. [ngrok: what it is and exactly why it is needed](#36-ngrok-what-it-is-and-exactly-why-it-is-needed)

**Part G — Reference**
37. [Every API endpoint](#37-every-api-endpoint)
38. [Database schema — all 9 tables](#38-database-schema--all-9-tables)
39. [Backend code walkthrough, file by file](#39-backend-code-walkthrough-file-by-file)
40. [Frontend code walkthrough, file by file](#40-frontend-code-walkthrough-file-by-file)
41. [The Makefile and every command](#41-the-makefile-and-every-command)
42. [The test suite — all 99 tests](#42-the-test-suite--all-99-tests)

**Part H — Honesty**
43. [Known warts and bugs](#43-known-warts-and-bugs)
44. [Limitations you should admit before being asked](#44-limitations-you-should-admit-before-being-asked)
45. [Glossary](#45-glossary)

---
---

# Part A — Orientation

## 1. The problem this solves

In India, lenders decide whether to give you a loan mostly by asking a **credit bureau**
(CIBIL, Experian, Equifax, CRIF) for your credit history. The bureau replies with a score,
typically 300–900.

But a bureau can only report on credit you have *already had*. If you have never taken a
formal loan or held a credit card, the bureau has nothing to say about you. Its answer is
literally **"NO_HIT"** — no record found. In the industry these people are called
**credit-invisible**, **thin-file**, or **new-to-credit (NTC)**.

Who are they? Roughly:

- A gig worker (delivery rider, cab driver) earning ₹20,000/month through UPI.
- A farmer whose income arrives three times a year as mandi (agricultural market) settlements.
- A small shopkeeper who files GST returns, takes cash and UPI, and has never borrowed from a bank.

They may have perfectly good cash flow. They simply have no *credit* history. The standard
lending system treats "no information" the same as "bad information": the application is
auto-rejected, or pushed into slow, document-heavy manual underwriting that most dealers
won't bother with for a ₹80,000 two-wheeler loan.

**The commercial point for TVS Credit:** these are exactly the people buying two-wheelers,
used cars and tractors. Every auto-rejected NO_HIT applicant is a lost sale at the dealership.

**The problem statement this project answers** (TVS Credit e.p.i.c. Season 8): build an
alternative, consent-based way to assess creditworthiness for applicants the bureau cannot see.

## 2. What the product actually does

Saksham ("सक्षम" — *capable*, *able*) sits **beside** the existing bureau check, not instead of it.

```
Customer walks into a dealership, wants a two-wheeler loan
        │
        ▼
   Bureau check  (this already exists today)
        │
        ├── HIT, score ≥ 700 ──────────► existing TVS loan flow. Saksham never runs.
        ├── HIT, score < 700 ──────────► existing flow, unchanged. Out of scope.
        └── NO_HIT ────────────────────► Saksham takes over
                                              │
                                              ▼
                              Ask the customer, on WhatsApp, for permission
                              to look at specific records
                                              │
                                 ┌────────────┴────────────┐
                              refuses                   agrees
                                 │                         │
                        nothing is read            read 3 sources in parallel:
                        application ends           • bank statement (incl. UPI)
                                                   • telecom recharge history
                                                   • GST returns or mandi receipts
                                                             │
                                                             ▼
                                                 42 features → model → PD → score 300–900
                                                             │
                              ┌──────────────────────────────┼──────────────────────────┐
                              ▼                              ▼                          ▼
                       score ≥ 650                   600 ≤ score < 650           score < 600
                        APPROVED                  CONDITIONAL_APPROVAL        DECLINED_WITH_PLAN
                   into the normal loan flow      smaller ticket offered    a plain-language plan in
                                                                           Hindi/Marathi/English,
                                                                           sent on WhatsApp
```

Three product ideas make this more than "another scoring model":

1. **Consent is granular, visible and revocable.** The customer sees exactly which three
   record types are being requested, can switch each one off individually, and can withdraw
   permission later — at which point the stored data is deleted.
2. **A rejection is never a dead end.** Instead of "no", the customer gets three specific,
   achievable steps in their own language ("keep two EMIs' worth of balance in your account",
   "recharge on a monthly plan instead of small top-ups"). This is the *graduation* idea:
   today's reject is next year's customer.
3. **The graduation ladder.** Once approved, on-time repayments raise a *behaviour score*,
   which unlocks higher pre-approved limits and more products (two-wheeler → used car → tractor).

## 3. The five-minute mental model

If you remember only one thing, remember this: **the system is one Python process and one
SQLite file.** There is no message queue, no Redis, no microservices, no Docker cluster.

```
┌───────────────────────────────────────────────────────────────────────┐
│  ONE FastAPI process on port 8000                                     │
│                                                                       │
│   /                    → the built React app (dealer console)         │
│   /consent/{id}        → the same React app (customer's phone)        │
│   /plan/{id}           → the same React app (customer's phone)        │
│   /api/v1/*            → the real API                                 │
│   /mock/*              → fake vendors (bureau, bank, telecom, GST)    │
│   /webhooks/whatsapp   → Meta calls this                              │
│   /demo/*              → demo helpers (reset, personas, config)       │
│                                                                       │
│   state: ONE SQLite file at backend/data/saksham.db                   │
└───────────────────────────────────────────────────────────────────────┘
          │                                   │
          ▼                                   ▼
   WhatsApp Cloud API                   Google Gemini
   (real, over the internet)            (real, over the internet)
```

Why one process? Because for a hackathon demo, **"it starts with one command and never
breaks"** is worth more than architectural purity. The *boundaries* that would matter in
production are still there — they are Python interfaces (`BureauAdapter`, `DataSourceAdapter`,
`MessagingProvider`, `LLMClient`) with mock implementations behind them. You swap one class
in one file (`adapters/registry.py`) to point at a real vendor. The seams are real; the
deployment is simple.

Why does the fake bank/telecom/GST data get fetched **over HTTP** rather than by calling a
function? Because that makes the network failure modes real. Timeouts, HTTP error codes,
connection failures and consent rejections (`403`) all actually happen and are actually
handled, instead of being imagined. The "simulate outage" checkbox in the UI makes a mock
endpoint `sleep(5)` while the caller's timeout is `3` seconds — and you watch the system
degrade gracefully instead of crashing.

## 4. Repository map

```
SakshamEngine/
├── policy.yaml            ← ALL business rules. Cutoffs, products, tiers, timeouts.
├── reason_codes.yaml      ← 42 feature→reason mappings + all customer-facing text (EN/HI/MR)
├── personas.yaml          ← the 7 demo customers
├── .env                   ← secrets (git-ignored). API keys, tokens, URLs.
├── .env.example           ← the same file with placeholders (committed)
├── Makefile               ← every command you'll ever run
├── README.md              ← the short version of this document
│
├── backend/
│   ├── app/
│   │   ├── main.py            ← FastAPI app factory, startup warm-up, SPA serving
│   │   ├── seed.py            ← `make seed`: wipe the database
│   │   ├── core/              ← infrastructure: config, db, security, http, logging, errors
│   │   ├── domain/            ← pure business logic, no I/O: scorecard, policy, state machine
│   │   ├── models/            ← SQLAlchemy tables (9 of them)
│   │   ├── adapters/          ← the ports-and-adapters layer (all external contact)
│   │   │   ├── interfaces.py     ← the abstract "ports"
│   │   │   ├── registry.py       ← wiring: which implementation backs each port
│   │   │   ├── bureau.py, data_sources.py, los.py
│   │   │   ├── messaging/        ← whatsapp.py, simulated.py, manager.py
│   │   │   └── llm/              ← gemini.py, fallback.py
│   │   ├── services/          ← the orchestration layer (the actual flow)
│   │   │   ├── orchestrator.py   ← THE main flow. Read this file first.
│   │   │   ├── feature_pipeline.py ← THE ONE place raw data becomes model input
│   │   │   ├── scoring.py, explainability.py, advisory.py
│   │   │   ├── consent.py, ingestion.py, ladder.py, notifications.py, queries.py
│   │   ├── api/               ← thin HTTP routers (they just call services)
│   │   └── mock_services/     ← the fake vendors
│   │       ├── generators.py     ← procedurally generates all fake data. Important file.
│   │       ├── personas.py       ← mobile hash → Profile
│   │       └── routers.py        ← the /mock/* endpoints
│   ├── ml/
│   │   ├── generate_data.py   ← builds the 20,000-row synthetic training set
│   │   ├── train.py           ← trains, calibrates, evaluates, writes the report
│   │   ├── artifacts/         ← COMMITTED: model.joblib (344K), calibrator, schema, report.md
│   │   └── data/              ← git-ignored: training_data.parquet (3.1M)
│   └── tests/                 ← 99 tests
│
├── frontend/
│   ├── public/brand/          ← logo, TVS logo, hero video + poster
│   └── src/
│       ├── App.tsx            ← 3 routes
│       ├── api/               ← client.ts (fetch wrapper), types.ts
│       ├── hooks/             ← useApplication.ts (polling), usePolling.ts
│       ├── i18n.ts            ← phone-page strings in EN/HI/MR
│       ├── styles/index.css   ← design tokens (the dark theme)
│       └── components/
│           ├── Dashboard.tsx         ← the dealer console (the main screen)
│           ├── ConsentPage/          ← the customer's consent screen
│           ├── PlanPage/             ← the customer's action plan
│           ├── DealerPOS/            ← form, timeline, decision details
│           ├── UnderTheHood/         ← gauge, SHAP waterfall, trace, ladder
│           ├── Messages/             ← message log, QR code
│           └── Brand.tsx, VideoBg.tsx, ui.tsx
│
├── scripts/check_whatsapp.py  ← pre-demo validation of all credentials
└── docs/
    ├── architecture.md        ← terse technical notes
    ├── demo_script.md         ← the 5-minute presentation script
    └── EXPLAINER.md           ← this file
```

**Reading order if you want to understand the code:**
1. `policy.yaml` — learn the business rules.
2. `backend/app/services/orchestrator.py` — the whole flow in one file.
3. `backend/app/services/feature_pipeline.py` — the data transformation.
4. `backend/ml/train.py` — the model.
5. `frontend/src/components/Dashboard.tsx` — the UI.

---
---

# Part B — Choices

## 5. Every technology, and why it was chosen

### Backend

| Technology | Version | What it is | Why this one |
|---|---|---|---|
| **Python** | 3.11 | the language | LightGBM and SHAP publish pre-built wheels for 3.11. On 3.12/3.13 you risk compiling from source, which breaks on a demo machine. This is pinned deliberately. |
| **FastAPI** | 0.142.2 | web framework | Async-native (needed for parallel data fetching), automatic request validation from type hints, and free interactive API docs at `/docs`. The alternative, Flask, is synchronous and would need extra work for both. |
| **Uvicorn** | 0.54.0 | the ASGI server | The standard way to actually run FastAPI. `--reload` for development. |
| **Pydantic** | 2.13.5 | data validation | Every API request body and every line of `policy.yaml` is validated into a typed Python object at startup. A typo in the YAML fails loudly on boot rather than silently at 2 a.m. |
| **pydantic-settings** | 2.15.0 | config from env | Reads `.env` into a typed `EnvSettings` object. |
| **SQLAlchemy** | 2.1.2 (async) | database toolkit | Industry standard ORM. The 2.x async API matches FastAPI's async handlers. |
| **aiosqlite** | 0.22.1 | async SQLite driver | Lets SQLAlchemy talk to SQLite without blocking the event loop. |
| **greenlet** | 3.5.6 | coroutine plumbing | A hidden requirement of SQLAlchemy's async mode. It is listed explicitly in `requirements.txt` because the install silently breaks without it. |
| **httpx** | 0.28.1 | HTTP client | Async (so three vendor calls really do run in parallel), and — crucially — its `ASGITransport` lets the test suite route "HTTP" calls straight into the app in-process, so tests exercise the real HTTP code paths without a network. |
| **pandas** | 3.0.6 | data frames | The feature vector is a `pd.Series`; training data is a `DataFrame`. |
| **numpy** | 2.4.6 | numerics | All the generator maths and seeded random number generation. |
| **scikit-learn** | 1.9.1 | ML utilities | Used for three specific things: `train_test_split`, the `LogisticRegression` that does Platt calibration, and the metrics (`roc_auc_score`, `brier_score_loss`, `roc_curve`). |
| **LightGBM** | 4.7.0 | the model | See [section 18](#18-why-lightgbm-and-not-something-else) — this gets a full discussion. |
| **SHAP** | 0.51.0 | explainability | See [section 26](#26-shap-explained-from-scratch). |
| **joblib** | 1.6.0 | serialisation + parallelism | Saves the model to disk, and parallelises synthetic-data generation across CPU cores. |
| **PyYAML** | 6.0.3 | YAML parsing | Reads the three config files. |
| **pytest** + **pytest-asyncio** | 9.1.1 / 1.4.0 | testing | `asyncio_mode = auto` means async test functions just work with no decorator. |

**Deliberately *not* used, and why:**

- **No Redis.** Consent sessions need a 15-minute expiry — the classic reason to reach for
  Redis. Instead, a session is a database row with an `expires_at` column, and expiry is
  enforced **lazily**: whenever the row is read, if `expires_at` has passed, the status flips
  to `EXPIRED`. No background job, no second service to install. (`services/consent.py:38`)
- **No Celery / RQ / task queue.** The post-consent pipeline (fetch → score → decide → notify)
  takes a couple of seconds and must not block the HTTP response. Instead:
  `asyncio.create_task()` (`orchestrator.py:42`), with the task kept in a module-level set so
  it is not garbage-collected mid-flight, and a `drain()` helper so tests can wait for it.
- **No PostgreSQL.** SQLite in WAL mode. One file means `make reset` is a file delete, and the
  demo has zero setup. WAL (write-ahead logging) is enabled so a read never blocks a write.
- **No Docker.** `make install && make demo`. One fewer thing to fail on stage.
- **No authentication.** There is no login. This is a prototype; a real deployment would put
  this behind the dealer's existing auth. Worth stating out loud rather than pretending.

### Frontend

| Technology | Version | Why |
|---|---|---|
| **React** | 19.3 | The UI is a live view of a backend state machine; a declarative component model fits that. |
| **TypeScript** | 7.0 | Every API response is typed in `src/api/types.ts`. If a backend field is renamed, the build fails instead of the UI silently rendering `undefined`. |
| **Vite** | 8.3 | Dev server starts in ~300 ms, hot reload is instant, and the production build is a handful of static files the Python server can serve directly. |
| **Tailwind CSS** | 4.3 | Utility classes keep styling next to markup. v4's `@theme` block means the entire colour scheme is ~20 CSS variables in one file (`styles/index.css`). |
| **Recharts** | 3.10 | Only used for the SHAP waterfall chart. Lazy-loaded with the dashboard so the customer's phone pages never download it. |
| **react-router-dom** | 7.18 | Three routes: dashboard, consent page, plan page. |
| **qrcode** | 1.5 | Renders the consent URL as a QR code, so you can open it on a phone without WhatsApp working. A deliberate fallback for a live demo. |

**A notable frontend decision:** `Dashboard.tsx` is **lazy-loaded** (`App.tsx:8`). The two
pages a *customer* opens on their phone (`/consent/:id`, `/plan/:id`) are in the main bundle
and stay small (~90 KB gzipped); the heavier dealer console with its charting library
(~124 KB gzipped) only loads for the dealer. That is a real consideration for users on rural
mobile data.

### Data flow / state management

There is no Redux, no React Query, no state library. Instead `src/hooks/usePolling.ts` is a
32-line hook that calls a function every 2 seconds, and `useApplication.ts` composes three of
them (application, trace, messages). Polling stops when the application reaches a terminal
state — but keeps going for 20 more seconds, so WhatsApp delivery ticks (sent → delivered →
read) still arrive. For a demo where the backend is the source of truth and the flow lasts
seconds, polling is simpler and more robust than WebSockets.

## 6. The configuration system: the "nothing hardcoded" rule

A hard requirement for this build was that no business value is hardcoded in Python. The
result is three YAML files plus `.env`, all read at startup.

```
         .env                policy.yaml          reason_codes.yaml      personas.yaml
           │                      │                      │                     │
           ▼                      ▼                      ▼                     ▼
      EnvSettings             Policy model          ReasonCatalog          list of dicts
    (pydantic-settings)      (pydantic models)
           └──────────────────────┴──────────────────────┴─────────────────────┘
                                         │
                                         ▼
                              get_settings()  ← @lru_cache(maxsize=1)
```

**`get_settings()` is cached** (`core/config.py:231`). It reads the files exactly once per
process. This is why **editing `.env` or any YAML requires a server restart** — there is no
file watcher. (This is also the direct answer to "I replaced the expired WhatsApp token, do I
need to restart?" — yes.)

### What lives in `policy.yaml`

Every one of these is a number you can change without touching code:

| Section | Keys | Effect |
|---|---|---|
| `bureau` | `bypass_threshold: 700` | bureau score at or above this → straight to the normal flow |
| `decision` | `approve_cutoff: 650`, `borderline_floor: 600`, `borderline_enabled: true`, `borderline_ticket_factor: 0.7`, `min_sources_for_scoring: 2`, `max_pd_for_approval: null`, `comfortable_emi_ratio: 0.33` | the entire decision policy |
| `scorecard` | `pdo: 60`, `target_score: 650`, `target_pd: 0.07`, `offset: null`, `min_score: 300`, `max_score: 900` | the PD→score maths |
| `ingestion` | `per_source_timeout_seconds: 3.0`, `outage_sleep_seconds: 5.0` | timeouts |
| `session` | `ttl_minutes: 15` | consent link lifetime |
| `consent` | `ttl_days: 182`, `purpose_template`, `groups: [aa, telecom, business]` | consent validity |
| `products` | 3 SKUs with `ticket`, `tenure_months`, `emi`, `flat_rate` | the product catalogue |
| `languages` | `supported: [en, hi, mr]`, `default: en` | adding a 4th language is a config change |
| `ladder` | `initial_score: 50`, `max_score: 100`, `deltas`, 3 tiers with `min_behaviour_score` and per-product `limits` | the graduation ladder |
| `messaging` | `whatsapp_window_hours: 24`, `consent_prefill_text` | WhatsApp behaviour |
| `advisory` | `max_steps: 3`, `forbidden_phrases: [...]`, `cache_size: 256` | LLM guardrails |
| `ml` | `n_applicants: 20000`, `seed: 42`, `target_default_rate: 0.10`, `split`, `drop_source_prob: 0.06`, `product_mix`, `label: {cw_slope, burden_slope, interaction, noise_sd}` | how training data is generated |
| `mock` | `as_of_date: "2026-10-01"` | the anchor date for all fake data — fixed so the demo is reproducible |
| `features` | `low_balance_threshold: 500`, `bounce_window_days: 90`, `gst_margin: 0.18`, `mandi_margin: 0.45`, `income_blend_weights` | constants *inside* the feature pipeline |

That last one matters: the `features:` section changes **model inputs**. If you edit it, the
committed model was trained on different arithmetic. The code notices — `scoring.py:57-60`
stores the feature policy inside `feature_schema.json` at training time and compares it on
load, logging a warning telling you to re-run `make train`. That kind of self-checking is the
difference between "configurable" and "configurable without silently breaking".

### The product EMI formula

Products can either pin an EMI or have one derived (`core/config.py:117-122`):

```python
monthly_emi = ticket * (1 + flat_rate * tenure_years) / tenure_months
```

This is **flat-rate interest** (the Indian vehicle-finance convention), not reducing-balance.
For a two-wheeler: `80000 * (1 + 0.14 * 2) / 24 = ₹4,266.67`. The config pins `emi: 4200`
instead, so a round number shows in the demo. Remove the `emi:` line and the formula takes over.

### `.env` — secrets and deployment

Secrets never appear in YAML (which is committed) — only in `.env` (which is git-ignored).
`.env.example` is the committed template. The full list is in [section 34](#34-whatsapp--meta-cloud-api-in-full)
and [35](#35-google-gemini-and-the-guardrails); the key ones:

```bash
SECRET_KEY=...                  # HMAC key for consent signatures + identifier tokenisation
DATABASE_URL=...                # SQLAlchemy URL
PUBLIC_BASE_URL=https://...     # must be phone-reachable → this is what ngrok provides
MOCK_SERVICES_BASE_URL=...      # where the backend calls its own /mock/* endpoints
MESSAGING_MODE=both             # simulated | whatsapp | both
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
DEMO_RECIPIENT_NUMBER=+91...
GEMINI_API_KEY=...
LLM_MODEL=gemini-3.5-flash-lite
```

Three layers protect the secrets:
1. `masked_dump()` (`config.py:216`) masks them in any config dump.
2. `mask_secrets()` (`security.py:76`) scrubs them from arbitrary text — it replaces the
   literal secret values *and* matches patterns like `EAA...` (Meta tokens), `AIza...`
   (Google keys), `Bearer ...`, `access_token=...`.
3. A logging filter (`logging.py:10`) runs `mask_secrets()` over **every log record** in the
   process, so you cannot accidentally log a token even from third-party library code.

---
---

# Part C — The data journey (the heart of it)

This part follows one real applicant through every single transformation. All numbers below
were produced by actually running the pipeline for **persona 1 (Ramesh Gupta, merchant)**, so
you can trust them and reproduce them.

## 7. Stage 0: personas — what you pick in the UI

When you choose "1. Ramesh Gupta" in the dealer form, you are **not** loading a saved dataset.
`personas.yaml` contains no transactions at all. Here is the entire persona:

```yaml
- id: 1
  key: merchant
  name: "Ramesh Gupta"
  description: "Small-town merchant — steady UPI/bank inflows, GST filings, regular recharges"
  mobile_number: "9000000001"
  pan_token: "PANMERCH01"
  aadhaar_token: "AADH-MASK-0001"
  product_sku: TWO_WHEELER
  language: en
  bureau: { status: NO_HIT, score: -1 }
  profile: { segment: merchant, creditworthiness: 0.50 }
  expected_outcome: APPROVED
```

That is it. Eleven lines. The persona supplies **inputs to a simulator**, not data:

- `segment` — one of `merchant | gig | farmer | salaried`. Controls *shape*: a farmer gets
  lumpy seasonal income and mandi receipts; a gig rider gets many small UPI credits.
- `creditworthiness: 0.50` — a single hidden number from 0 to 1. **This one number drives
  almost everything.** Higher means denser bank activity, more distinct payers, more digital
  (less cash), fewer bounces, more regular recharges, longer SIM tenure, on-time GST filing.
- `bureau` — the fake bureau's scripted answer.
- `product_sku`, `language` — what gets requested and in which language messages are sent.
- `expected_outcome` — not used by the app; it is **asserted by the test suite**
  (`test_e2e_personas.py:44`), so a change that alters a persona's outcome fails CI.

The seven personas:

| # | Name | Segment | Creditworthiness | Bureau | Expected outcome | Actual score |
|---|---|---|---|---|---|---|
| 1 | Ramesh Gupta | merchant | 0.50 | NO_HIT | `APPROVED` | ~766 |
| 2 | Sunil Yadav | gig | 0.30 | NO_HIT | `DECLINED_WITH_PLAN` (Hindi) | ~551 |
| 3 | Mohan Patil | farmer | 0.60 | NO_HIT | `APPROVED` | ~783 |
| 4 | Sanjay Jadhav | farmer | 0.10 | NO_HIT | `DECLINED_WITH_PLAN` (Marathi) | ~325 |
| 5 | Anita Sharma | salaried | 0.95 | **HIT 760** | `BYPASSED_TO_LOS` | — (never scored) |
| 6 | Vikram Singh | merchant | 0.70 | NO_HIT | `CONSENT_DENIED` | — (no data read) |
| 7 | Ramesh (AA outage) | merchant | 0.50 | NO_HIT | `APPROVED` | ~746 |

Persona 7 deliberately reuses persona 1's mobile number (`9000000001`) so it gets **identical
underlying data**, with `simulate_outage: [aa]` set. The comparison 766 → 746 is therefore a
clean demonstration: lose the entire bank statement and the score drops 20 points but the
customer is still approved. That is the graceful-degradation story, with a number attached.

## 8. Stage 1: the Profile — one number that drives everything

The lookup path from a phone number to a data profile:

```
mobile "9000000001"
    │  normalize_mobile()  → strip +91, spaces, dashes; keep last 10 digits
    ▼
vendor_ref()  = sha256("saksham-vendor-ref-v1:9000000001")
    │                = "…" (64 hex chars)
    │
    ├──► persona_map() lookup: does personas.yaml contain a persona with this vendor_ref?
    │        YES → use its segment + creditworthiness
    │        NO  → derive a random-but-deterministic profile from the hash
    ▼
seed_from_hash()  = int(sha256(vendor_ref)[:8], 16)  = 1190768894
    ▼
build_profile(seed=1190768894, segment="merchant", cw=0.50)
    ▼
Profile(seed=1190768894, segment='merchant', cw=0.5,
        monthly_income=42730.88,      ← drawn from a lognormal, seeded
        has_aa=True, has_telecom=True, has_gst=True, has_mandi=False,
        aa_sparsity=1.0)
```

**Two subtle and important decisions here.**

**(a) There are two different hashes of the phone number, on purpose.**

| Function | Formula | Used for | Depends on `SECRET_KEY`? |
|---|---|---|---|
| `mobile_hash()` | `HMAC-SHA256(SECRET_KEY, "mobile:" + number)` | what we store in **our own** database | **Yes** |
| `vendor_ref()` | `SHA256("saksham-vendor-ref-v1:" + number)` | the pseudonymous id sent to **vendors** | **No** |

Why the split? Our stored hash should be keyed, so that a leaked database cannot be brute-forced
back to phone numbers without also leaking the key. But the *vendor-side* identity must be
stable: if it were keyed, rotating `SECRET_KEY` would change every persona's seed and therefore
every persona's data and score. That actually happened during development — persona 2 scored
differently under pytest (which sets `SECRET_KEY=test-secret-key`) than when run normally. The
fix was to split the two functions, and there is now a regression test for it:
`test_generators.py:67 — test_persona_data_does_not_depend_on_secret_key`.

**(b) `monthly_income` is latent — the model never sees it.**

```python
monthly_income = median_for_segment * lognormal(0, sigma) * (0.75 + 0.5 * cw)
```

For a merchant: median ₹45,000, sigma 0.35. Ramesh lands at **₹42,730.88/month** of *true*
income. The model never receives this number. It only sees what *leaks into the records* —
and for a merchant only 80% of income flows through the bank account (`AA_CAPTURE`), so the
pipeline's estimate comes out at ₹35,126, about 18% below truth. Inferring real capacity from
partial evidence is precisely the problem being modelled.

Also derived per profile: `aa_sparsity` (farmers get 0.25–0.6 — they barely use their bank
account), and which sources exist at all (farmers have a 12% chance of having no bank account;
GST only for merchants; mandi receipts only for farmers).

## 9. Stage 2: raw payloads — what the "vendors" return

`backend/app/mock_services/generators.py` (317 lines) is the simulator. It is **pure**: no I/O,
no settings, no database — just `(Profile, as_of_date) → dict`. That purity is what lets the
same functions serve both the live demo and the training-data build.

`as_of` comes from `policy.yaml → mock.as_of_date: "2026-10-01"`. Fixing it means the demo is
bit-for-bit reproducible regardless of the day you present.

### 9.1 The bank statement (Account Aggregator)

**What an Account Aggregator is:** an RBI-regulated framework where a licensed intermediary
fetches your bank data *with your consent* and passes it to a lender. Real players: Finvu,
OneMoney, Setu. You never hand over bank credentials; you approve a consent request in an app.
This is the single most important data source for the whole project, and it is the reason the
consent architecture is built the way it is.

The generator produces **180 days** of daily balances plus a transaction list.

```python
# What varies with creditworthiness (cw):
capture       = AA_CAPTURE[segment] * min(1.0, 0.35 + aa_sparsity)   # how much income is visible
n_payers      = (4 + 70*cw) * pool_scale * aa_sparsity   # distinct UPI counterparties
cash_weight  *= (1.5 - cw)                               # safer applicants lean digital
monthly_factor= clip(1 + (1.15-cw)*0.5*normal(), 0.2, 2.2)  # income volatility
spend_ratio   = clip(0.68 + 0.42*(1-cw) + normal(0,0.06), 0.5, 1.4)  # outflow/inflow
bounce_p      = 0.62 * (1-cw)**1.6                       # per-mandate chance of an ECS bounce
opening_bal   = income * (0.12 + 1.5*cw) * lognormal(0,0.3)
```

Real behaviours the generator models:

- **No overdraft.** A debit is clipped to the available balance (`generators.py:185`), so
  balances never go negative — as in a real savings account.
- **Mandates.** 90% of applicants have a recurring debit (an existing EMI or insurance
  premium) of 8–20% of income; 35% have a second smaller one. Each due date either succeeds
  or **bounces** — producing a `mode: "ECS_RETURN"` transaction with a ₹400 penalty and the
  narration `"ECS RETURN - INSUFFICIENT FUNDS CHARGES"`. This is where the bounce signal comes
  from; it is not injected directly as a feature.
- **UPI is a transaction mode, not a data source.** A conceptual point the project is careful
  about: there is no "UPI API". UPI activity is visible *inside* the bank statement as
  transactions with `mode: "UPI"`. `test_generators.py:23` asserts exactly this.
- **Recurring salary-like credits.** Always for `salaried`; otherwise with probability
  `0.22 * cw`. Safer applicants rarely miss the monthly credit, and its date wobbles less.

Real output for Ramesh:

```
180 balance rows, 279 transactions, 43,976 bytes of JSON

{"date": "2026-04-06", "amount": 311.64, "type": "DEBIT", "mode": "UPI",
 "narration": "UPI/SHOP036@pay", "balance": 30953.87}

{"date": "2026-04-05", "balance": 31265.51}
```

### 9.2 Telecom recharge history

**Why telecom data predicts credit:** how long you have kept the same number (stability), and
whether you recharge on a proper monthly plan versus scrambling for ₹19 top-ups when you run
out (cash-flow stress). This is genuinely used by lenders in emerging markets.

```python
tenure_months = clip(4 + 100*cw*uniform(0.3,1.2) + normal(0,6), 2, 150)
erratic       = 1 - cw
# with probability 0.25 * erratic^1.3 → a ₹19/₹49 TOPUP instead of the usual plan
gap_to_next   = plan_validity + abs(normal(0, 1 + 6*erratic))
                + (exponential(18 * erratic^1.5) if random() < 0.5*erratic else 0)
```

So a low-creditworthiness applicant shows: shorter tenure, cheap top-ups mixed in, and long
gaps where the phone was out of balance. Ramesh: **14 recharges**, 943 bytes, e.g.
`{"date": "2025-10-05", "amount": 299, "plan_type": "MONTHLY"}`.

### 9.3 GST returns (merchants only)

**What GST returns are:** every registered Indian business files monthly/quarterly returns
declaring turnover, due by the 20th of the following month. Filing consistency and turnover
trend are strong small-business credit signals.

```python
base       = monthly_income / 0.18 * uniform(0.8, 1.2)   # 18% assumed net margin
growth     = (cw - 0.4) * 0.05                            # monthly growth rate
volatility = 0.06 + 0.45*(1-cw)
# unfiled month with probability 0.28 * (1-cw)^1.5
filing_delay = poisson(10 * (1-cw)^1.5) - randint(0,6)    # negative = filed early
```

Ramesh: **10 returns filed** out of 12 months, e.g.
`{"period": "2025-10", "turnover": 165933.86, "filed_on": "2025-11-18"}` — due the 20th, filed
the 18th, so on time.

### 9.4 Mandi receipts (farmers only)

**What a mandi is:** a regulated agricultural market where farmers sell crops. A receipt
records crop, quantity, rate per quintal and the settlement amount — and critically, the
**settlement date**, which is often days or weeks after the sale.

```python
cycles_per_year = 1 + 3*cw + uniform(-0.3, 0.6)   # more cropping cycles = better farmer
n_crops         = 1 + round(2.5*cw*uniform(0.5,1.3))  # diversification = resilience
settlement_delay= round(2 + (1-cw)*22*exponential(1.0)*0.6 + randint(0,3))
```

Seven real crops with realistic rates per quintal (wheat ₹2,275, cotton ₹7,000, sugarcane ₹340…).
Ramesh is a merchant, so this returns `None`.

### 9.5 The bureau

Trivial by design: personas get a scripted answer from `personas.yaml`; anyone else gets
`generate_bureau_result(seed, hit_probability=0.0)` — i.e. **always NO_HIT by default**, since
NO_HIT is the case the whole system exists for.

## 10. Stage 3: what the backend receives after consent

This is where consent enforcement becomes concrete. When the customer taps "I Authorize":

```
POST /api/v1/consent/authorize  { session_id, grants: {aa: true, telecom: true, business: true} }
    │
    ├─ create a ConsentArtifact, HMAC-signed, valid 182 days
    ├─ transition the application to CONSENT_GRANTED
    ├─ asyncio.create_task(process_after_consent(...))   ← returns to the phone immediately
    └─ the phone shows "Thank you, we're reviewing"
```

Then, in the background (`services/ingestion.py`):

```python
async def one(name):                                   # name = aa | telecom | business
    if not getattr(consent, f"grant_{name}", False):
        return SourceResult(name, "not_consented", None, 0, "Customer did not grant this source")
    return await adapters[name].fetch(vendor_ref, consent.id, simulate_outage=...)

return list(await asyncio.gather(*(one(n) for n in adapters)))     # all three in parallel
```

**A source that was not consented to is never called.** Not called and filtered — *never
called*. `test_e2e_personas.py:119` asserts the unconsented source has no timeline entry
showing a vendor request.

Each granted source becomes a real HTTP request to the app's own mock vendor:

```
GET /mock/aa/bank-statement?mobile_hash=<vendor_ref>
    Header: X-Consent-Token: <consent_id>
    timeout: 3.0s  (policy.ingestion.per_source_timeout_seconds)
```

Note what is and is not sent. The vendor receives the **pseudonymous `vendor_ref`** and a
**consent token**. It does not receive a name, a phone number, a PAN or an Aadhaar number.

On the receiving side, every data endpoint is wrapped in a consent guard
(`mock_services/routers.py:36`) which calls `verify_for_source()` — six checks, described in
[section 27](#27-consent-the-legal-and-technical-core).

The `business` group is special: it maps to **two** endpoints (GST and mandi) fetched in
parallel, and succeeds if *either* returns data (`data_sources.py:72-91`). A gig rider has
neither, so the group legitimately returns `no_data` — a data gap, not an error.

Failures never raise. Every outcome becomes a typed `SourceResult`:

| `status` | Meaning | `usable`? |
|---|---|---|
| `ok` | data returned | ✅ |
| `timeout` | no response within 3 s | ❌ |
| `no_data` | vendor has no records for this customer (HTTP 404) | ❌ |
| `not_consented` | consent missing/revoked/expired/out of scope (HTTP 403) | ❌ |
| `error` | anything else — network failure, 500, bad shape | ❌ |

Then the **sufficient-data gate** (`orchestrator.py:256`):

```python
if usable_groups(results) < policy.decision.min_sources_for_scoring:   # default 2
    → INSUFFICIENT_DATA  → manual review.  Nothing is scored.
```

This is a real risk control, not decoration. Scoring someone off a single thin source would
produce a confident-looking number with nothing behind it. The system refuses.

## 11. Stage 4: feature engineering — all 42 features

`backend/app/services/feature_pipeline.py` — one function, `build_features()`, is **the only
code path** from raw payloads to model input. Its docstring says "Never add a second path",
and a test enforces it.

Input and output:

```python
build_features(
    raw_payloads = {"aa": {...} | None,
                    "telecom": {...} | None,
                    "business": {"gst": {...} | None, "mandi": {...} | None} | None},
    requested_emi = 4200.0,
    product_sku   = "TWO_WHEELER",
    ticket_size   = 80000.0,
) -> pd.Series   # exactly 42 float64 values, in a fixed order, NaN where unknown
```

**The single most important design decision in the pipeline: missing data stays `NaN`.** There
is no imputation — no filling with zeros, no median substitution. If the bank source timed out,
all 14 bank features are `NaN` and the model is handed `NaN`. This is deliberate and it is the
main reason LightGBM was chosen; see [section 18](#18-why-lightgbm-and-not-something-else).

Two conventions make the maths stable:

- **"Months" are 30-day blocks counted back from `as_of`**, not calendar months
  (`BLOCK_DAYS = 30`). So results don't wobble because February is short.
- `_norm_slope()` expresses a trend as a slope divided by the mean, making it scale-free
  (comparable between a ₹5,000/month and a ₹500,000/month applicant).

### The 42 features, every one explained

Each row gives the feature, what it measures, how it's computed, the monotone direction
(`↓risk` = more is safer, `↑risk` = more is riskier, `—` = unconstrained), and **Ramesh's
actual value**.

#### Bank statement / AA — 14 features

| Feature | What it measures | Computation | Mono | Ramesh |
|---|---|---|---|---|
| `buffer_ratio` | savings cushion in EMIs | mean(daily balance) / EMI | ↓risk | **10.34** |
| `bounce_velocity` | recent payment failures | count of `ECS_RETURN` in last 90 days | ↑risk | **0.0** |
| `income_regularity` | evenness of monthly inflow | `clip(1 − CV(monthly inflow), 0, 1)` | ↓risk | **0.62** |
| `monthly_inflow_count` | transaction activity | credits / n_blocks | ↓risk | **25.0** |
| `distinct_upi_counterparties` | customer base breadth | unique narrations on UPI credits | ↓risk | **36.0** |
| `cash_vs_digital_ratio` | cash dependence | cash credits / total credits | — | **0.252** |
| `digital_inflow_share` | digital footprint | (UPI+NEFT+IMPS) / total credits | ↓risk | **0.748** |
| `min_balance_days` | days near zero | days with balance < ₹500 | ↑risk | **0.0** |
| `balance_trend` | is the balance growing? | normalised slope of block-mean balances | ↓risk | **+0.090** |
| `avg_monthly_inflow` | scale of income | total credits / n_blocks | ↓risk | **₹30,222.92** |
| `max_monthly_outflow` | biggest spending month | max of block outflows | — | **₹41,000.51** |
| `salary_regularity` | reliable recurring credit | (share of blocks with a large credit) × (timing consistency) | ↓risk | **0.0** |
| `upi_txn_frequency` | UPI usage intensity | all UPI txns / n_blocks | — | **27.17** |
| `balance_volatility` | balance instability | std(balance) / mean(balance) | ↑risk | **0.185** |

A note on `salary_regularity = 0.0`: a "large credit" is one ≥ 25% of average monthly inflow.
Ramesh is a merchant with 25 small inflows a month and no single dominant credit, so this
scores zero — correctly. It is informative, not broken: it says "this person has no salary".

`cash_vs_digital_ratio` is intentionally **unconstrained** (`—`). Cash-heavy might mean a
street vendor with real turnover, or it might mean undocumented income. Forcing a direction
would encode a guess, so the model is allowed to learn whatever the data says.

#### Telecom — 6 features

| Feature | What it measures | Computation | Mono | Ramesh |
|---|---|---|---|---|
| `recharge_frequency_regularity` | recharge discipline | `clip(1 − std(gaps)/mean(gaps), 0, 1)` | ↓risk | **0.683** |
| `recharge_count_12m` | activity | recharges in the last 365 days | ↓risk | **14.0** |
| `avg_recharge_value` | spending power | mean recharge amount | ↓risk | **₹239.71** |
| `recharge_value_trend` | improving or shrinking? | (2nd-half mean − 1st-half mean) / overall mean | ↓risk | **−0.137** |
| `sim_tenure_months` | stability | (as_of − sim_start) / 30.4 | ↓risk | **45.39** |
| `max_recharge_gap_days` | worst dry spell | max(all gaps, *open gap to today*) | ↑risk | **37.0** |

That "open gap" detail matters: if the last recharge was 60 days ago and the phone is dead
right now, the gap list wouldn't capture it. The code includes `as_of − last_recharge_date`
explicitly (`feature_pipeline.py:157`), with a dedicated test.

#### GST — 5 features (merchants)

| Feature | What it measures | Computation | Mono | Ramesh |
|---|---|---|---|---|
| `gst_avg_turnover` | business size | mean declared turnover | ↓risk | **₹240,544.07** |
| `gst_turnover_volatility` | revenue instability | std of month-over-month % change | ↑risk | **0.289** |
| `gst_filing_consistency` | compliance | share filed by the 20th of the next month | ↓risk | **0.60** |
| `gst_growth_trend` | growing or shrinking? | (2nd-half mean − 1st-half mean) / overall mean | ↓risk | **+0.195** |
| `gst_months_filed` | record depth | count of returns | ↓risk | **10.0** |

The due-date calculation handles the December→January year rollover
(`feature_pipeline.py:183`), and there is a test for exactly that off-by-one-year bug.

#### Mandi — 6 features (farmers)

| Feature | What it measures | Mono | Ramesh |
|---|---|---|---|
| `mandi_settlement_frequency` | receipts per month over a 24-month window | ↓risk | `NaN` |
| `mandi_distinct_cycles` | cropping cycles (gaps > 45 days split a cycle) | ↓risk | `NaN` |
| `mandi_avg_monthly_settlement` | income scale | ↓risk | `NaN` |
| `mandi_avg_settlement_delay` | days from sale to payment | ↑risk | `NaN` |
| `mandi_crop_diversity` | distinct crops — diversification | ↓risk | `NaN` |
| `mandi_tenure_months` | history length | ↓risk | `NaN` |

All `NaN` for Ramesh: he is a merchant and has no mandi records. Those six `NaN`s are the
entire reason the model must handle missing values natively.

#### Affordability / application context — 5 features

| Feature | Computation | Mono | Ramesh |
|---|---|---|---|
| `requested_emi` | from the product catalogue | ↑risk | **₹4,200.00** |
| `est_monthly_income` | weighted blend — see below | ↓risk | **₹35,126.05** |
| `emi_to_income_ratio` | `requested_emi / est_monthly_income` | ↑risk | **0.1196** |
| `product_type_encoded` | index of the SKU in the product dict | — | **0.0** |
| `ticket_size` | loan amount | — | **₹80,000.00** |

`est_monthly_income` is the one genuinely clever feature. Different applicants reveal income
through different channels, so the pipeline blends whatever is available, using weights from
`policy.yaml`:

```python
candidates = {}
if avg_monthly_inflow is not NaN:         candidates["aa"]    = avg_monthly_inflow
if gst_avg_turnover  is not NaN:          candidates["gst"]   = gst_avg_turnover * 0.18   # margin
if mandi_avg_monthly_settlement not NaN:  candidates["mandi"] = mandi_avg * 0.45          # margin
weights = {aa: 0.5, gst: 0.3, mandi: 0.3}      # from policy.yaml
est_monthly_income = Σ(candidates[k] * w[k]) / Σ(w[k] for k present)
```

Worked, for Ramesh:

```
aa  contribution: 30,222.92 × 0.5                = 15,111.46
gst contribution: 240,544.07 × 0.18 × 0.3        = 12,989.38
                                           sum   = 28,100.84
            divided by present weights (0.5+0.3) = 35,126.05   ✓
```

Note the re-normalisation by the weights actually present — that is what makes the estimate
behave sensibly when a source is missing instead of collapsing toward zero. Ground truth was
₹42,730, so the estimate is conservative by 18%, which for a lender is the safe direction to err.

`product_type_encoded` is an honest wart: it assigns `TWO_WHEELER=0, USED_CAR=1, TRACTOR=2`,
an *ordinal* encoding of a *nominal* variable. With tree models and three categories this is
harmless (a tree can isolate any single value with two splits), and it is left unconstrained,
so the model is not forced to treat "tractor > used car". With many categories, one-hot or
LightGBM's native categorical support would be correct.

#### Data availability flags — 6 features

| Feature | Computation | Mono | Ramesh |
|---|---|---|---|
| `src_aa_available` | bank data present and non-empty | ↓risk | **1.0** |
| `src_telecom_available` | telecom present | ↓risk | **1.0** |
| `src_business_available` | business group returned something | — | **1.0** |
| `has_business_records` | GST or mandi actually has rows | — | **1.0** |
| `n_sources_available` | sum of the three | ↓risk | **3.0** |
| `data_completeness_score` | `0.45·aa + 0.25·telecom + 0.30·business` | ↓risk | **1.0** |

These exist so the model knows *why* a value is missing in aggregate, and can price the
uncertainty. An applicant scored on two sources carries more unknown risk than one scored on
three, all else equal — and because `n_sources_available` and `data_completeness_score` are
constrained `↓risk`, the model is **forced** to treat less data as (weakly) riskier. It cannot
learn the perverse "missing data is good news" pattern that unconstrained models often pick up
from noise.

**Final result for Ramesh: 42 features, 36 with values, 6 `NaN` (all mandi).**

## 12. Stage 5: the model's three outputs

```python
# backend/app/services/scoring.py:63
def predict(self, features: pd.Series) -> ScoreResult:
    x      = features[self.schema["features"]].to_numpy(dtype=float).reshape(1, -1)
    margin = float(self.model.booster_.predict(x, raw_score=True)[0])      # ① raw margin
    pd_cal = float(self.calibrator.predict_proba([[margin]])[0, 1])        # ② calibrated PD
    return ScoreResult(margin, pd_cal, self.scorecard.pd_to_score(pd_cal), latency)  # ③ score
```

Note `features[self.schema["features"]]` — the vector is re-ordered to match the **exact column
order stored at training time**. Silently shuffled feature order is a classic production ML
bug; this line prevents it.

For Ramesh:

| Output | Value | What it is |
|---|---|---|
| ① `raw_margin` | **−3.8642** | log-odds of **default**, straight from LightGBM. Negative = safe. Not a probability. |
| ② `pd` | **0.019211** | calibrated probability of default: **1.92%** |
| ③ `score` | **766.5** | the 300–900 number a human reads |

## 13. Stage 6: the scorecard — PD to a 300–900 score

A probability of 1.92% is correct but unusable: nobody in lending talks that way, and the
decision tables, dealer UI and customer messaging all assume a CIBIL-like 300–900 number. The
conversion uses the **standard industry scorecard scaling**, not an invented mapping:

```
odds_good = (1 − PD) / PD
Score     = Offset + Factor · ln(odds_good)
Factor    = PDO / ln(2)
```

**PDO = "points to double the odds" = 60.** Every 60 points of score means the odds of being
good double. This is the convention FICO and CIBIL-style scorecards use, so the number carries
the meaning a credit officer already expects.

`Factor = 60 / ln(2) = 86.562`.

The **Offset** is *derived*, not hardcoded (`core/config.py:88`):

```
Offset = target_score − Factor · ln((1 − target_pd) / target_pd)
       = 650 − 86.562 · ln(0.93 / 0.07)
       = 650 − 86.562 · 2.5867
       = 426.092
```

So the whole scale is pinned by one business statement in `policy.yaml`: **"a score of 650
means a 7% chance of default."** Change `target_pd` to 0.05 and the entire scale shifts
coherently. (The original implementation plan specified an offset of 487.123, which is
inconsistent with its own 650↔7% anchor; the derived value is used instead, and
`test_scorecard.py:13` asserts the anchor round-trips.)

Ramesh:

```
odds_good = (1 − 0.019211) / 0.019211 = 51.05
Score     = 426.092 + 86.562 × ln(51.05)
          = 426.092 + 86.562 × 3.9329
          = 766.5                              ✓
```

The full lookup table (from `ml/artifacts/report.md`, and it is a good thing to be able to
quote):

| Score | PD | | Score | PD |
|---|---|---|---|---|
| 300 | 81.10% | | 650 | **7.00%** |
| 400 | 57.48% | | 700 | 4.05% |
| 500 | 29.86% | | 800 | 1.31% |
| 600 | 11.83% | | 900 | 0.42% |

Properties worth knowing: the mapping is **strictly monotone** (higher score always = lower
PD), **clamped** to [300, 900], and **invertible** (`score_to_pd()`), which the report uses to
print the table. Tests cover the anchor, the PDO-doubling property, monotonicity, clamping,
and the explicit-offset override.

## 14. Stage 7: the decision

A pure function, no I/O, 12 lines (`backend/app/domain/policy.py:17`):

```python
def evaluate_decision(score, pd, product_sku, policy) -> Decision:
    d = policy.decision
    pd_ok = d.max_pd_for_approval is None or pd <= d.max_pd_for_approval
    if score >= d.approve_cutoff and pd_ok:                    # ≥ 650
        return Decision(APPROVED, reason=f"score {score:.0f} ≥ cutoff {d.approve_cutoff:.0f}")
    if d.borderline_enabled and d.borderline_floor <= score < d.approve_cutoff:   # 600–650
        return Decision(CONDITIONAL_APPROVAL,
                        suggested_ticket=round(ticket * d.borderline_ticket_factor, -3),
                        reason=f"borderline band {d.borderline_floor:.0f}–{d.approve_cutoff:.0f}")
    return Decision(DECLINED_WITH_PLAN, reason=f"score {score:.0f} < cutoff {d.approve_cutoff:.0f}")
```

| Band | Outcome | What happens next |
|---|---|---|
| score ≥ 650 | `APPROVED` | LOS handoff + LMS loan account created + WhatsApp confirmation |
| 600 ≤ score < 650 | `CONDITIONAL_APPROVAL` | a **reduced ticket** is suggested: `80,000 × 0.7 → ₹56,000` (rounded to the nearest 1,000 by `round(..., -3)`) |
| score < 600 | `DECLINED_WITH_PLAN` | Gemini (or templates) generates a 3-step plan; sent on WhatsApp in the customer's language |

`max_pd_for_approval` is an optional second gate — a hard PD ceiling independent of the score,
currently `null`. It exists because real credit policy often wants a belt-and-braces override.

Ramesh: `766.5 ≥ 650` → **APPROVED**, reason `"score 767 ≥ cutoff 650"`.

## 15. Stage 8: SHAP → reason codes → the waterfall

Explaining a decision is not optional here, for two reasons: regulators increasingly require
adverse-action reasons, and the entire "decline with a plan" product depends on knowing *which*
specific behaviours held the applicant back.

The mechanism (`services/explainability.py`) converts SHAP values into **score points**, so the
explanation adds up to the score the customer was shown:

```python
points_i = −shap_i × platt_slope × Factor
```

Why each term:
- SHAP values are in the model's output space, i.e. **log-odds of default**.
- The **minus sign** flips to the applicant's perspective: positive points now mean "this
  helped your score".
- `platt_slope` (1.0543) converts the raw margin into calibrated log-odds.
- `Factor` (86.562) converts log-odds into score points.

The waterfall's base is the score implied by the model's expected margin — "the average
applicant". For Ramesh:

```
Average applicant                            676.7
  + Savings buffer vs EMI                    +32.49   (buffer_ratio = 10.34)
  + Distinct UPI counterparties              +20.72   (36 payers)
  + SIM tenure                               +19.43   (45.4 months)
  + GST filing consistency                   +15.71   (60% on time)
  − Recharge regularity                      −11.56   (0.683)
  − Income regularity                         −6.75   (0.62)
  + All other factors                        +19.85
  ────────────────────────────────────────────────────
  This applicant                             766.5    ✓ (exactly the score he was given)
```

Then SHAP contributions are mapped to **reason codes** from `reason_codes.yaml` — 42 entries,
one per feature, each with a label, a positive phrasing, a negative phrasing and a concrete
**action**, in English, Hindi and Marathi. For example:

```yaml
RC001:
  feature: buffer_ratio
  label:    { en: "Savings buffer vs EMI", hi: "EMI के मुकाबले बचत", mr: "EMI च्या तुलनेत शिल्लक" }
  positive: { en: "Strong savings buffer relative to the EMI", ... }
  negative: { en: "Low account balance relative to the EMI", ... }
  action:
    en: "Try to keep a balance of at least 2 EMIs in your bank account at all times."
    hi: "अपने बैंक खाते में हमेशा कम से कम 2 EMI के बराबर रकम रखने की कोशिश करें।"
    mr: "तुमच्या बँक खात्यात नेहमी किमान 2 EMI इतकी रक्कम ठेवण्याचा प्रयत्न करा."
```

For Ramesh the top drivers come out as:

```
Helping:        RC001 buffer_ratio                  +32.5
                RC005 distinct_upi_counterparties    +20.7
                RC019 sim_tenure_months              +19.4
Holding back:   RC015 recharge_frequency_regularity  −11.6
                RC003 income_regularity               −6.8
                RC012 salary_regularity               −3.8
```

Two filters make the reason lists honest (`explainability.py:69`):

1. **Features with a missing value are excluded.** "You have no GST records" is not an action
   a gig worker can take, so it never appears as advice — even if its absence mathematically
   moved the score. It still appears in the full waterfall.
2. **`reportable: false` features are excluded.** Some entries in `reason_codes.yaml` are
   marked unreportable because they are not actionable (e.g. `ticket_size`).

## 16. Stage 9: the vernacular action plan

Only for `DECLINED_WITH_PLAN`. The top-3 *negative* reason codes become the input to the
advisory service, which produces a four-part plan: `greeting`, `summary`, up to 3 `steps`,
`closing`. See [section 35](#35-google-gemini-and-the-guardrails) for the LLM and its
guardrails. The deterministic fallback composes the same structure from the `action:` strings
in `reason_codes.yaml`, so the feature works with no API key and no internet.

The plan is rendered into a WhatsApp message and also published at `/plan/{application_id}`,
a mobile page with EN/हिं/मरा toggles.

## 17. The whole journey on one page

```
personas.yaml:  segment=merchant, creditworthiness=0.50          ← 11 lines of config
        │
        ▼  vendor_ref() → sha256 → seed 1190768894
Profile(cw=0.5, monthly_income=₹42,730.88 [LATENT — never seen by the model])
        │
        ▼  generators.py (pure functions, deterministic, as_of = 2026-10-01)
RAW PAYLOADS      bank: 180 balances + 279 transactions (44 KB JSON)
                  telecom: 14 recharges (943 B)
                  gst: 10 returns
                  mandi: None
        │
        ▼  3 parallel consent-gated HTTP calls, 3 s timeout each
SourceResults     aa: ok (payload) · telecom: ok · business: ok
        │
        ▼  gate: usable sources (3) ≥ min_sources_for_scoring (2) → proceed
        ▼  build_features()  ← THE one code path, shared with training
FEATURE VECTOR    42 float64 values, 36 real + 6 NaN
                  buffer_ratio=10.34 · bounce_velocity=0.0 · est_income=₹35,126 …
        │
        ▼  LightGBM (192 trees, 15 leaves, monotone constraints)
RAW MARGIN        −3.8642                            (log-odds of default)
        │
        ▼  Platt calibration (slope 1.0543, intercept 0.1412)
CALIBRATED PD     0.019211                           (1.92% chance of default)
        │
        ▼  Score = 426.092 + 86.562 · ln((1−PD)/PD)
SCORE             766.5
        │
        ├──► evaluate_decision() → APPROVED (766.5 ≥ 650)
        ├──► SHAP → 6 drivers + waterfall summing exactly to 766.5
        ├──► AuditRecord written (insert-only, immutable)
        ├──► LOS handoff (mock) → LMS loan account → ladder at STARTER/50
        └──► WhatsApp message to the customer
```

What gets **stored**, and what gets **thrown away**:

| Data | Stored? |
|---|---|
| Raw vendor payloads (the 44 KB bank statement) | ❌ **discarded** after feature extraction |
| The 42-value feature vector | ✅ as JSON — and **purged on consent revocation** |
| SHA-256 hash of the feature vector | ✅ permanently, in the audit record |
| Score, PD, raw margin, outcome | ✅ in the audit record |
| SHAP drivers + waterfall | ✅ in the audit record |
| Model version, policy version, consent id | ✅ in the audit record |
| PAN, Aadhaar | ❌ only **HMAC tokens** are stored, never the values |
| Mobile number | ✅ in clear — the messaging channel needs it (stated honestly in the code comment) |

---
---

# Part D — The machine learning, in depth

## 18. Why LightGBM and not something else

**What LightGBM is:** a gradient-boosting library from Microsoft. Gradient boosting builds
many small decision trees in sequence; each new tree is fitted to the errors the previous ones
are still making. The final prediction is the sum of all trees' outputs. LightGBM's specific
contributions are speed (histogram-based splitting) and leaf-wise tree growth.

Here is the honest reasoning for each candidate:

### Logistic regression — the industry default, rejected

Classic credit scorecards *are* logistic regressions, usually over WOE-binned variables. It is
interpretable, regulator-friendly and stable. It was rejected for three concrete reasons:

1. **It cannot accept `NaN`.** This is decisive. Six of Ramesh's 42 features are missing, and
   missingness is the *normal* case here (no farmer has GST, no merchant has mandi receipts, a
   source can time out). Logistic regression would require imputation — and imputing "mandi
   settlement delay" for a shopkeeper invents a fact that does not exist. Any choice of fill
   value is a lie the model then learns from.
2. **No interactions without manual construction.** The risk of a high EMI burden is much worse
   for someone with irregular income — a multiplicative interaction. Trees find these splits
   automatically; a linear model needs every interaction hand-specified.
3. **Manual binning is a lot of work.** Credible WOE binning for 42 features, with monotonicity
   enforced per bin, is days of iteration — not available in a hackathon.

### Neural network — rejected

Needs far more data than 18k rows, has no native missing-value handling, is slower to train
and infer on CPU, produces a much larger artifact, and (most importantly) cannot have
monotone constraints imposed as cleanly. For tabular data of this size, gradient-boosted trees
are also simply the stronger baseline — this is one of the better-established empirical results
in applied ML.

### XGBoost / CatBoost — reasonable, not chosen

Both would work. XGBoost supports monotone constraints and missing values too. LightGBM was
preferred for: `monotone_constraints_method="advanced"` (the most rigorous of its three
enforcement modes), fast CPU training (the whole run takes ~2 minutes), a small artifact
(**344 KB**, small enough to commit to git so a fresh checkout needs no training), and exact,
fast SHAP via `TreeExplainer`.

### So: the four properties that actually decided it

1. **Native `NaN` handling.** LightGBM learns a *default direction* at each split for missing
   values — i.e. missingness is treated as information rather than as a value to fabricate.
   This is what makes "the bank feed timed out but we still scored you sensibly" work. It is
   also why the training data deliberately drops sources 6% of the time: the model gets
   practice at exactly this.
2. **Monotone constraints.** See the next section. This is the big one.
3. **Exact SHAP in milliseconds.** `TreeExplainer` computes exact Shapley values for tree
   ensembles in polynomial time. Model-agnostic SHAP (`KernelExplainer`) is approximate and
   orders of magnitude slower — unusable for a live request.
4. **Small and fast.** 344 KB artifact; single-row inference in roughly a millisecond.

### Hyperparameters, and the reasoning

```python
PARAMS = dict(
    n_estimators=800,            # upper bound; early stopping picked 192
    learning_rate=0.03,          # small → more trees, better generalisation
    num_leaves=15,               # ~4 levels deep. Small = less overfitting on 12.7k rows
    min_child_samples=60,        # a leaf needs ≥60 samples → no memorising individuals
    subsample=0.8, subsample_freq=1,   # each tree sees 80% of rows
    colsample_bytree=0.8,        # each tree sees 80% of features
    reg_lambda=5.0,              # L2 penalty on leaf weights
    monotone_constraints=MONOTONE_CONSTRAINTS,
    monotone_constraints_method="advanced",
    objective="binary",
)
```

The theme is **deliberate restraint**: shallow trees, large minimum leaf size, row and column
subsampling, L2 regularisation and a low learning rate. With 12,710 training rows and 42
features, the real danger is memorising noise, not underfitting. Early stopping (50 rounds'
patience, monitored on a separate validation set) chose 192 of the allowed 800 trees —
evidence the regularisation is doing its job rather than being decorative.

## 19. Monotone constraints: the most important ML decision here

**The problem.** Fit a flexible model to finite, noisy data and it will find patterns that are
not real. In credit scoring this produces specific absurdities:

- "Applicants with 4 bounced payments are *safer* than those with 3" (because of 11 unlucky
  rows in the training set).
- "A larger savings buffer slightly *increases* risk in the ₹40–50k band."

These are fatal in lending, for three separate reasons: they are unfair to the individual
caught by the quirk, they are indefensible to a regulator or an auditor, and they break the
product — the advisory plan tells people to improve a behaviour, so the model must guarantee
that improving it cannot hurt.

**The fix.** Every feature declares a monotone direction in its spec (`feature_pipeline.py:30`):

```python
_SPECS = [
    ("buffer_ratio",     "aa", -1),   # −1 : more of this → LOWER risk, always
    ("bounce_velocity",  "aa", +1),   # +1 : more of this → HIGHER risk, always
    ("cash_vs_digital_ratio", "aa", 0),  # 0 : unconstrained, let the data speak
    ...
]
MONOTONE_CONSTRAINTS = [s.monotone for s in FEATURE_SPECS]
```

That list is passed straight to LightGBM, which then **refuses to build any tree that would
violate it**. It is a hard structural guarantee, not a regularisation nudge or a post-hoc check.

The distribution across the 42 features: **27 constrained `↓risk`** (more is safer),
**8 constrained `↑risk`** (more is riskier), **7 left unconstrained**.

```
↑risk (8):  bounce_velocity · min_balance_days · balance_volatility · max_recharge_gap_days
            gst_turnover_volatility · mandi_avg_settlement_delay · requested_emi · emi_to_income_ratio

free (7):   cash_vs_digital_ratio · max_monthly_outflow · upi_txn_frequency
            product_type_encoded · ticket_size · src_business_available · has_business_records
```

The seven unconstrained ones are the honest ones: cases where the direction is genuinely
ambiguous, so forcing one would encode an assumption rather than knowledge. Cash-heavy inflows
might mean a street vendor with real turnover or undocumented income; a big outflow month might
be restocking inventory or a crisis. The model is allowed to learn whichever the data supports.

`monotone_constraints_method="advanced"` is LightGBM's strictest enforcement mode. It is slower
than the alternatives but gives the tightest guarantee, which is the right trade for a model
that runs once per application.

**Three things this buys you, that are worth saying out loud in a presentation:**

1. **Defensibility.** You can state, as a mathematical property of the artifact and not a hope:
   "reducing bounced payments can never reduce your score."
2. **Product integrity.** The advisory plan's promise is structurally true. Without constraints
   the plan could tell someone to do something that lowers their score.
3. **Built-in protection against small-sample artefacts** — which matters a great deal when the
   training data is synthetic and the real-world sample will initially be small.

## 20. How the synthetic training data was made

There is no real repayment data. That is the honest, central limitation of this project, and
the approach taken is to be rigorous about the *process* so that swapping in real data later
changes one function and nothing else.

### The generative story

`ml/generate_data.py` builds 20,000 applicants. The crucial design choice is the direction of
causation:

```
latent creditworthiness (cw) + latent true income
        │
        ├────► raw payloads ────► build_features() ────► 42 FEATURES  (what the model sees)
        │       (the same generators the live mocks use)
        │
        └────► default probability ────► Bernoulli draw ────► LABEL  (what the model predicts)
```

**Features and labels are generated from a common hidden cause, never from each other.** The
model's job is to infer `cw` from the evidence that leaked into the records. This is what makes
the task non-trivial and the resulting AUC meaningful rather than circular. Had features been
generated directly from the label, AUC would approach 1.0 and tell you nothing.

### The default process

```python
# ml/generate_data.py:60
burden = EMI / true_monthly_income            # real affordability, not the estimate
core = ( cw_slope    * (0.5 - cw)                                  # 7.0 — creditworthiness
       + burden_slope* (burden - 0.25)                             # 3.0 — EMI burden
       + interaction * (1 - cw) * max(0, burden - 0.30)            # 2.0 — the interaction
       + normal(0, noise_sd) )                                     # 0.35 — irreducible noise
```

Read as risk factors:
- `cw_slope · (0.5 − cw)`: creditworthiness relative to the midpoint. The dominant term.
- `burden_slope · (burden − 0.25)`: EMI as a share of *true* income, relative to 25%.
- `interaction`: extra risk when someone is *both* weak and over-burdened — a real compounding
  effect, and exactly the kind of thing a linear model would miss.
- `noise_sd = 0.35`: unobservable idiosyncratic risk (illness, accident, a bad harvest). This
  term is why perfect prediction is impossible and the achievable AUC is capped — which is
  realistic.

All four coefficients live in `policy.yaml → ml.label`, so the difficulty of the synthetic
problem is itself configurable.

Then the intercept is **solved for** so the average default rate hits the 10% target, instead
of being guessed (`generate_data.py:91`):

```python
lo, hi = -10.0, 10.0
for _ in range(60):                     # 60 rounds of bisection
    mid = (lo + hi) / 2
    if sigmoid(mid + core).mean() > target: hi = mid
    else:                                   lo = mid
df["_p_default"] = sigmoid(lo + core)
df["default"]    = (default_rng(seed).random(len(df)) < df["_p_default"]).astype(int)
```

10% is a plausible portfolio default rate for subprime/new-to-credit vehicle finance in India.
The final Bernoulli draw uses its own seeded generator, so labels are reproducible.

### Deliberate realism in the training set

- **`drop_source_prob: 0.06`** — each of the three sources is independently removed from 6% of
  training rows, *independently of the label*. This teaches the model to handle `NaN` honestly
  without learning "missing data implies default".
- **`product_mix`** — segments apply for plausible products: farmers mostly tractors (60%) and
  two-wheelers (40%); gig riders 90% two-wheelers. So `emi_to_income_ratio` has a realistic
  joint distribution with segment rather than a uniform one.
- **Parallel generation** via joblib across all cores, with BLAS threads pinned to 1 per worker
  to avoid thread oversubscription (`generate_data.py:77`).
- **The sufficient-data gate is applied to training too** (`train.py:43`): rows with fewer than
  2 usable sources are dropped, because they would never be scored in production. **20,000 rows
  → 18,158** after filtering. Training on data you would refuse to score at serving time is a
  subtle and common mistake; it is avoided here.

## 21. Train/serve parity — and why it is enforced by a test

**Training/serving skew** is one of the most common and most expensive production ML failures:
the training pipeline computes a feature one way, the serving code computes it slightly
differently, and the model silently degrades. It is hard to detect because nothing errors.

This project structurally prevents it:

```
                  ┌────────────────────────────────┐
                  │ mock_services/generators.py    │  pure functions
                  └───────────┬────────────────────┘
                   ┌──────────┴───────────┐
                   ▼                      ▼
        /mock/* HTTP endpoints      ml/generate_data.py
        (live serving)              (training)
                   │                      │
                   └──────────┬───────────┘
                              ▼
               services/feature_pipeline.build_features()
                   THE ONE AND ONLY code path
```

And `tests/test_feature_parity.py` proves it with two tests:

1. `test_same_payloads_same_features_in_training_and_serving` — builds a profile, generates
   payloads, computes features directly (the training path), then fetches the *same* customer's
   data through the **real HTTP endpoints with real consent enforcement** and computes features
   again (the serving path). Asserts the two 42-value vectors are identical.
2. `test_training_rows_come_from_build_features` — asserts that a generated training row's
   feature columns match a fresh `build_features()` call on the same payloads, so nobody can
   quietly add a shortcut in the training script.

This is, in my view, the strongest engineering decision in the project. It is a property
production ML teams spend serious effort to achieve, and it is enforced here by construction
plus two tests.

## 22. The training run, step by step

`make train` → `python -m ml.train --force-data`:

```
1. load_or_generate(force=True)
      → generate 20,000 applicants in parallel
      → save backend/ml/data/training_data.parquet  (3.1 MB, git-ignored)

2. filter: n_sources_available ≥ 2            → 18,158 rows survive

3. stratified split, seed 42, from policy.yaml
      train 12,710 (70%) · val 2,724 (15%) · test 2,724 (15%)
      Stratified on the label, so each split has ~10% defaults.
      The segment column is carried along for per-segment evaluation.

4. fit LGBMClassifier with monotone constraints
      eval_set = validation, metric = AUC, early_stopping(50)
      → stopped at 192 trees of a permitted 800

5. Platt calibration
      m_val      = model.predict(X_val, raw_score=True)        # raw margins
      calibrator = LogisticRegression(C=1e6).fit(m_val, y_val) # fitted on VALIDATION, not train

6. evaluate on the test set — untouched until this point
      AUC, KS, Brier (calibrated and uncalibrated), per-segment AUC,
      partial-data-slice AUC, a 10-bin calibration table, approval rate at the cutoff,
      and feature importance by gain

7. write artifacts
      model.joblib (344 KB) · calibrator.joblib (4 KB)
      feature_schema.json  — feature order, monotone constraints, the feature policy
                             used, calibration coefficients, scorecard params, metrics
      report.md            — the human-readable model card
```

Three disciplines worth noting: **three-way split** (the calibrator is fitted on validation
data, never on training data — fitting it on training margins would make it badly
overconfident); **the test set is used exactly once**, at the end; and
`feature_schema.json` records the `features:` policy section so the server can detect config
drift at load time.

## 23. Calibration: why a second model sits on top

LightGBM's `predict_proba` outputs numbers between 0 and 1, so why add a logistic regression?

Because those numbers are **ranking scores, not probabilities**. Gradient boosting optimises a
loss that produces good *ordering*, but the absolute values are typically distorted — pushed
toward the extremes. If the model says 0.30, you cannot assume 30% of such applicants default.

That assumption matters enormously here, because the score is *defined* in terms of PD:
`Score = Offset + Factor·ln((1−PD)/PD)` anchored at 650 ↔ 7%. If PD is miscalibrated, every
score is wrong, every cutoff means something different from what it claims, and the published
score↔PD table becomes fiction.

**Platt scaling** is the standard fix: fit a one-dimensional logistic regression mapping the raw
margin to the observed outcome.

```python
calibrator = LogisticRegression(C=1e6).fit(margins_val, y_val)
# learned: slope 1.0543, intercept 0.1412
PD = sigmoid(1.0543 × margin + 0.1412)
```

`C=1e6` means almost no regularisation — with one feature and 2,724 points, regularisation
would only bias the fit. Fitting on held-out validation margins is what makes the result
trustworthy.

Does it work? The calibration table from the report compares predicted PD against observed
default rate, in deciles:

| Predicted PD | Observed | n | | Predicted PD | Observed | n |
|---|---|---|---|---|---|---|
| 0.008 | 0.011 | 273 | | 0.055 | 0.048 | 272 |
| 0.012 | 0.007 | 272 | | 0.085 | 0.106 | 273 |
| 0.017 | 0.018 | 272 | | 0.133 | 0.143 | 272 |
| 0.025 | 0.040 | 273 | | 0.221 | 0.191 | 272 |
| 0.036 | 0.048 | 272 | | 0.448 | 0.388 | 273 |

Predicted and observed track each other closely across two orders of magnitude. The 4th bin
(0.025 predicted vs 0.040 observed) is the worst, and with 273 samples that gap is within
sampling noise.

**An honest observation:** Brier score is 0.0768 calibrated vs 0.0764 uncalibrated — i.e.
calibration very slightly *worsened* the aggregate squared error. That is because LightGBM's
binary objective already produces fairly well-calibrated output on this synthetic data; the
Platt layer is insurance that costs ~0.0004 Brier. It is worth keeping: it guarantees the
score↔PD mapping is anchored to observed frequencies, and on real data, where boosted
probabilities are usually much more distorted, it will earn its place.

## 24. Every metric in the report, explained

From `backend/ml/artifacts/report.md`, model version `v1-lgbm-20261002`:

| Metric | Value | What it means | How to read this number |
|---|---|---|---|
| **AUC** | **0.813** | Probability that a randomly chosen defaulter is ranked riskier than a randomly chosen non-defaulter. 0.5 = coin flip, 1.0 = perfect. | Solid. Real credit models on real data typically land 0.70–0.85, so this is a believable range rather than a suspicious one. |
| **KS** | **0.492** | Kolmogorov–Smirnov: the largest gap between the cumulative distributions of good and bad applicants. The traditional credit-industry discrimination measure. | Above 0.40 is considered strong in credit scoring. |
| **Brier (calibrated)** | **0.0768** | Mean squared error of the predicted probabilities. Lower is better. | Good for a 10% base rate (always predicting 0.10 would give ≈0.09). |
| **Brier (uncalibrated)** | 0.0764 | Same, before Platt scaling. | See the honesty note in [section 23](#23-calibration-why-a-second-model-sits-on-top). |
| **Test default rate** | 10.0% | Share of defaults in the test set. | Matches the 10% target — the bisection worked. |
| **Rows** | 12,710 / 2,724 / 2,724 | train / validation / test | |
| **Boosting rounds** | 192 | Trees kept by early stopping out of 800 allowed. | Stopped well short of the cap → the regularisation is real. |
| **Approval rate at 650** | **60.6%** | Share of test applicants who would be approved. | A business number, not just an ML one: roughly 6 in 10 bureau-invisible applicants become lendable. That is the commercial headline. |

### Per-segment AUC — the fairness-adjacent check

| Segment | n | Default rate | AUC |
|---|---|---|---|
| farmer | 871 | 12.6% | 0.834 |
| gig | 739 | 9.2% | 0.804 |
| merchant | 906 | 8.5% | 0.798 |
| salaried | 208 | 8.7% | 0.777 |

The spread is 0.777–0.834 — the model works comparably well across all four customer types,
with no segment left badly behind. (Salaried is the weakest, on the smallest sample; it is also
the segment that least needs this product, since salaried applicants are most likely to have a
bureau record.) This is *discrimination parity*, which is a useful check but not a full fairness
audit — see [section 44](#44-limitations-you-should-admit-before-being-asked).

### Partial-data slices — does graceful degradation actually work?

| Slice | n | AUC |
|---|---|---|
| AA (bank) missing | 195 | 0.893 |
| Telecom missing | 133 | 0.835 |
| No business records | 1,167 | 0.802 |
| All 3 sources present | 1,229 | 0.812 |

The headline claim — "the model still works when a source is missing" — holds. But read these
honestly: the first two slices have only 195 and 133 rows, so their AUCs carry wide confidence
intervals. **Do not** claim "the model is better without bank data"; that is noise plus the fact
that the surviving applicants in those slices are not a random sample. The defensible statement
is "performance does not collapse when a source is unavailable", and the two large slices
(1,167 and 1,229 rows, AUC 0.802 and 0.812) support exactly that.

### Feature importance by gain (top 10)

| # | Feature | Gain |
|---|---|---|
| 1 | `buffer_ratio` | 10,544 |
| 2 | `sim_tenure_months` | 4,488 |
| 3 | `min_balance_days` | 2,050 |
| 4 | `avg_recharge_value` | 1,893 |
| 5 | `emi_to_income_ratio` | 1,588 |
| 6 | `max_recharge_gap_days` | 1,298 |
| 7 | `recharge_frequency_regularity` | 1,138 |
| 8 | `max_monthly_outflow` | 1,138 |
| 9 | `distinct_upi_counterparties` | 970 |
| 10 | `upi_txn_frequency` | 907 |

"Gain" is the total improvement in the loss function from all splits on that feature. The
ordering is reassuring: savings buffer dominates (as any credit analyst would expect),
affordability (`emi_to_income_ratio`) is top-5, and **four of the top seven are telecom
features** — strong support for the project's premise that alternative data carries real
signal, since telecom data is available for nearly everyone.

## 25. What this model is *not*

Stated plainly, because this is the question a sharp judge will ask:

1. **It is not trained on real repayment outcomes.** No actual person's default has informed
   any coefficient. The AUC of 0.813 measures how well the model recovers a *simulated* risk
   process. It demonstrates that the pipeline, architecture, calibration and constraints are
   sound — not that this specific model would perform at 0.813 on TVS Credit's book.
2. **It cannot be validated for fairness in any real sense.** The synthetic data has no gender,
   caste, religion or region, so there is nothing to test disparate impact against.
3. **The synthetic default process is simple** — four terms and Gaussian noise. Real defaults
   involve shocks, fraud, local economic conditions and seasonality. A visible consequence is
   that scores saturate near the extremes for very clean profiles (persona 3 at ~783).
4. **No temporal validation.** Real credit models must be validated out-of-time (train on
   last year, test on this year) to catch population drift. There is no time dimension here.
5. **No reject inference.** Real scorecards suffer from only observing outcomes for applicants
   who were approved; techniques exist to correct it. Not applicable to synthetic data, but it
   would be needed in production.

**What a responsible rollout looks like**, and the right answer to "would you deploy this?":
run in **shadow mode** — score live applicants, store the scores, make no decisions with them.
Wait 12–18 months for real repayment outcomes. Retrain on those outcomes. Compare the shadow
scores with reality. Only then, with a validated model and a fairness audit, let the score
influence a decision. The architecture supports this directly: `AuditRecord` already stores
model version, policy version and feature hash for every scored application, which is exactly
the data a shadow-mode evaluation needs.

## 26. SHAP, explained from scratch

**The question SHAP answers:** the model said 766.5 for this applicant. The average applicant
gets 676.7. Which features account for the +89.8 difference, and by how much each?

**The idea.** SHAP (SHapley Additive exPlanations) borrows Shapley values from cooperative game
theory. Imagine the 42 features are players cooperating to produce a prediction. A feature's
Shapley value is its average marginal contribution across **every possible ordering** in which
features could be added to the model. With 42 features that is 42! orderings — astronomically
many.

**Why it is tractable here.** For tree ensembles specifically, `TreeExplainer` computes exact
Shapley values in polynomial time by exploiting tree structure. This is the only reason SHAP is
usable in a live request path. The model-agnostic alternative (`KernelExplainer`) approximates
by sampling and is orders of magnitude slower.

**The guarantee that matters** is *local accuracy*: the contributions sum exactly to the
difference between the prediction and the baseline. You saw this hold for Ramesh — the
waterfall adds to 766.5, not approximately but exactly. That is what makes it legitimate to
show a customer.

**Two engineering details in this codebase:**

```python
# explainability.py:46 — SHAP warns that LightGBM's binary output shape changed; handled below
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    sv = self.tree.shap_values(x)
sv = np.asarray(sv[-1] if isinstance(sv, list) else sv).reshape(-1, len(names))[0]
```

Depending on version, SHAP returns either an array or a list of two arrays (one per class) for
binary classifiers. The code handles both, taking the positive class.

```python
# main.py:31 — the first SHAP call JIT-compiles; do it at startup, not in someone's request
def warm():
    svc = get_scoring_service()
    get_explainer().explain(pd.Series(0.0, index=FEATURE_NAMES))
    return svc.model_version
log.info("Model loaded and warmed: %s", await asyncio.to_thread(warm))
```

SHAP's first invocation pays a significant one-time compilation cost. The server does a dummy
explanation at startup, in a worker thread so the event loop is not blocked, so the first real
applicant doesn't absorb that latency. Small detail; the kind of thing that separates a demo
that feels fast from one that stutters on the first click.

---
---

# Part E — The system

## 27. Consent: the legal and technical core

Consent is not a checkbox here. It is a **signed, scoped, time-limited, revocable artifact**
that is verified on every single data access.

### The two-object model

| Object | Lifetime | Purpose |
|---|---|---|
| **`ConsentSession`** | 15 minutes (`policy.session.ttl_minutes`) | the one-time link sent to the phone. Status: `OPEN → GRANTED \| DENIED \| EXPIRED` |
| **`ConsentArtifact`** | 182 days (`policy.consent.ttl_days`) | the actual permission, created when the customer authorises |

The split exists because they answer different questions: the session is "is this link still
usable?" (short), the artifact is "may we read this data?" (long, and revocable).

### The signature

When consent is granted, the artifact's fields are canonicalised and HMAC-signed
(`services/consent.py:53`):

```python
art.id = new_id()                           # the id is part of the signed payload → assign first
art.signature = sign_payload({
    "consent_id": art.id, "session_id": ..., "application_id": ...,
    "grants": {"aa": True, "telecom": True, "business": True},
    "purpose": "Alternative credit assessment for Two-Wheeler loan",
    "granted_at": ..., "expires_at": ...,
})
# sign_payload = HMAC-SHA256(SECRET_KEY, json.dumps(payload, sort_keys=True, separators=(",", ":")))
```

Canonical JSON (sorted keys, no whitespace) means the signature is reproducible. The purpose of
signing is **tamper evidence**: if someone edits the stored `grant_business` flag directly in
the database to widen the scope, the signature no longer matches and access is refused. There
is a test for precisely that attack (`test_consent.py:72`).

### The six checks on every data access

`verify_for_source()` (`services/consent.py:70`) runs before any mock vendor returns data:

| # | Check | Error code on failure |
|---|---|---|
| 1 | a consent token was supplied | `CONSENT_REQUIRED` |
| 2 | the artifact exists | `CONSENT_REQUIRED` |
| 3 | it has not been revoked | `CONSENT_REVOKED` |
| 4 | it has not expired | `CONSENT_EXPIRED` |
| 5 | **the HMAC signature verifies** | `CONSENT_INVALID` |
| 6 | it covers *this* source group | `CONSENT_SCOPE` |
| 7 | it was issued for *this* customer (`vendor_ref` match) | `CONSENT_MISMATCH` |

Check 7 prevents using a valid token to pull a *different* person's data — tested at
`test_consent.py:80`.

### Revocation actually does something

```python
# services/consent.py:92
art.revoked    = True
art.revoked_at = utcnow()
if app.feature_vector_json is not None:
    app.feature_vector_json = None     # the extracted features are DELETED
    purged = True
await log_event(db, art.application_id, "REVOKED", art.id, {"features_purged": purged})
```

Revoking has three visible effects: future vendor calls return HTTP 403; the stored feature
vector is **deleted**; and the affordability panel in the dealer UI goes blank (because
`decision_view` reads those numbers from the feature vector). What survives is the audit
record — the score, outcome and the feature vector's **SHA-256 hash**. That is the right
balance: the lender can still prove *what it decided and on what basis* without retaining the
data itself. Tested at `test_e2e_personas.py:132` and `test_consent.py:54`.

### A race condition that was actually handled

```python
# orchestrator.py:286 — consent may have been revoked WHILE we were scoring
await db.refresh(art)
fv = _clean_features(features)
app.feature_vector_hash = sha256_hex(json.dumps(fv, sort_keys=True))
app.feature_vector_json = None if art.revoked else json.dumps(fv)
```

Scoring takes a couple of seconds. If the customer revokes during that window, the features
must not be persisted. The code re-reads the artifact immediately before writing and stores
the hash but not the data. That is a genuinely easy bug to ship, and it was anticipated.

### What the customer sees

The consent page (`/consent/{session_id}`) shows, in their chosen language:

- **three independent toggles**, one per source group, each with a plain-language description
  ("Money in and out of your bank account and your balance (via Account Aggregator). UPI
  payments show up here too.");
- the **purpose** string;
- **"Valid for 182 days. You can withdraw your consent at any time."**;
- a **live countdown** of the 15-minute session;
- separate **"I Authorize"** and **"No, thanks"** buttons.

Turning all three toggles off and pressing Authorize is treated as a **denial**, not an empty
grant (`orchestrator.py:212`) — the honest interpretation.

## 28. Security and privacy mechanics

| Concern | Mechanism | Where |
|---|---|---|
| PAN / Aadhaar storage | only `HMAC-SHA256(SECRET_KEY, "pan:" + value)` is stored; the value never is | `security.py:22` |
| Mobile number | stored in clear, with an explicit code comment explaining why (the messaging channel needs it) | `models/application.py:21` |
| Vendor-side identity | pseudonymous `vendor_ref`, unkeyed so it is stable across key rotation | `security.py:36` |
| Raw bank/GST payloads | discarded after feature extraction; never written to the database | `orchestrator.py` |
| Feature vector | stored as JSON; purged on revocation | `consent.py:101` |
| Audit trail | insert-only `AuditRecord`, one per decision, `unique=True` on `application_id` | `models/audit.py` |
| Secret masking in logs | a `logging.Filter` runs `mask_secrets()` over **every** record in the process | `logging.py:10` |
| Secret masking in errors | the WhatsApp provider additionally scrubs its *own* token, because Meta sometimes echoes it back in error text | `whatsapp.py:79` |
| Secrets reaching the browser | `/demo/config` is hand-built to be secret-free; there is no generic config dump endpoint | `api/demo.py:65` |
| Webhook authenticity | optional `X-Hub-Signature-256` HMAC verification of Meta's payloads | `webhooks.py:32` |
| Timing attacks | `hmac.compare_digest()` everywhere a secret is compared, including the webhook verify token | `webhooks.py:27` |
| Error messages | one shape everywhere, `{"error": {"code", "message"}}`; unhandled exceptions return a generic message and log the detail | `errors.py` |
| SQL injection | SQLAlchemy parameterised queries throughout; no string-built SQL | — |
| Path traversal | the SPA handler resolves the candidate path and verifies `dist` is a parent before serving | `main.py:91` |

The masking deserves a closer look, because it is defence in depth rather than a single check:

```python
_SECRET_PATTERNS = [
    re.compile(r"(access_token=)[^&\s]+", re.I),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.I),
    re.compile(r"(key=)[^&\s]+", re.I),
    re.compile(r"(EAA[A-Za-z0-9]{10,})"),        # Meta access tokens
    re.compile(r"(AIza[0-9A-Za-z_\-]{20,})"),    # Google API keys
]
```

So even a token that was never in `.env` — say, one pasted into a URL by a third-party library's
error message — is caught by shape. During development a test did catch the WhatsApp provider
leaking its token through a mock-transport error message; the provider-level `_scrub()` was
added in response, and the test now guards it
(`test_messaging.py:64 — test_graph_errors_are_typed_hinted_and_never_leak_the_token`).

## 29. The state machine

An application is always in exactly one of 13 states, and only declared transitions are legal
(`domain/state_machine.py`).

```
                              CREATED
                                 │
                                 ▼
                           BUREAU_CHECKED
                           ┌─────┴─────────────────────┐
                           ▼                           ▼
                  BYPASSED_TO_LOS ◄terminal     AWAITING_CONSENT
                                            ┌────────┼────────────────┐
                                            ▼        ▼                ▼
                               CONSENT_DENIED◄t   EXPIRED◄t    CONSENT_GRANTED
                                                                      │
                                                                      ▼
                                                                  INGESTING
                                                            ┌─────────┴──────────┐
                                                            ▼                    ▼
                                                         SCORED        INSUFFICIENT_DATA◄t
                                               ┌────────────┼────────────┐
                                               ▼            ▼            ▼
                                        APPROVED◄t  CONDITIONAL◄t  DECLINED_WITH_PLAN◄t
                                                    _APPROVAL
```

Expressed as data, so it is checkable rather than implied by `if` statements:

```python
TRANSITIONS = {
    S.CREATED:          {S.BUREAU_CHECKED},
    S.BUREAU_CHECKED:   {S.BYPASSED_TO_LOS, S.AWAITING_CONSENT},
    S.AWAITING_CONSENT: {S.CONSENT_DENIED, S.EXPIRED, S.CONSENT_GRANTED},
    S.CONSENT_GRANTED:  {S.INGESTING},
    S.INGESTING:        {S.SCORED, S.INSUFFICIENT_DATA},
    S.SCORED:           {S.APPROVED, S.CONDITIONAL_APPROVAL, S.DECLINED_WITH_PLAN, S.INSUFFICIENT_DATA},
}
TERMINAL = {BYPASSED_TO_LOS, CONSENT_DENIED, EXPIRED, APPROVED, CONDITIONAL_APPROVAL,
            DECLINED_WITH_PLAN, INSUFFICIENT_DATA}
```

Any undeclared move raises `INVALID_TRANSITION` (HTTP 409). Why bother? It makes whole classes
of bug impossible rather than unlikely: an application cannot be scored twice, cannot be
approved without consent, cannot move backwards. The test
`test_scorecard.py:52` walks every state pair and asserts only declared moves are permitted.

Every transition also writes a `TimelineEvent` row (`STATE_<NAME>`, with the previous state in
its details), which is what the UI's "Application timeline" renders. The UI is a view over an
event log, not a separate representation that could drift.

## 30. The orchestrator: the one place the flow lives

`backend/app/services/orchestrator.py` (350 lines) is the file to read if you read only one.

### Phase 1 — `create_application()`

```
validate: product exists? mobile is 10 digits? language supported?   → 422 with a clear message
    ↓
tokenise PAN and Aadhaar (HMAC), store the Application row
    ↓
add_timeline("CREATED")
    ↓
bureau check via the port
    ├─ raises? → log a warning, treat as NO_HIT with degraded: true, carry on
    │             ("a bureau outage must not block the customer")
    ↓
transition → BUREAU_CHECKED
    ↓
HIT?  → transition BYPASSED_TO_LOS, hand off to the LOS, return. Saksham never runs.
    ↓
NO_HIT → create a ConsentSession (TTL 15 min)
       → build consent_url from PUBLIC_BASE_URL  (never localhost — there's a test)
       → send the consent request message
       → transition AWAITING_CONSENT
```

The bureau-failure branch is a small but telling decision: a vendor outage degrades to "treat
as thin file" rather than erroring the application. The timeline records `degraded: true` so
the behaviour is visible rather than hidden.

### Phase 2 — `grant_consent()`

```
load the session, lazily expire it if the TTL passed
    ↓
already expired → 410 GONE · already used → 409 CONFLICT   (both tested)
    ↓
nothing granted → treat as a denial
    ↓
create the signed ConsentArtifact → transition CONSENT_GRANTED → commit
    ↓
schedule(process_after_consent(app.id, art.id))     ← background, returns immediately
    ↓
respond to the phone  ("Thank you, we're reviewing")
```

### Phase 3 — `_process()`, the background pipeline

```python
transition INGESTING
results = await ingest_all_sources(vendor_ref(app.mobile_number), art, demo_outages(app))
for r in results: add_timeline(f"{r.source.upper()}_INGESTION", r.status, r.latency_ms, ...)

if usable_groups(results) < min_sources_for_scoring:      # the gate
    transition INSUFFICIENT_DATA; write an audit record; notify; return

features = await asyncio.to_thread(build_features, ...)   # CPU work OFF the event loop
res      = await asyncio.to_thread(scoring.predict, features)
expl     = await asyncio.to_thread(lambda: get_explainer().explain(features))

await db.refresh(art)                                     # revoked while we worked?
app.feature_vector_hash = sha256_hex(...)
app.feature_vector_json = None if art.revoked else json.dumps(fv)
app.score, app.pd = round(res.score, 1), res.pd
transition SCORED

decision = evaluate_decision(res.score, res.pd, sku, policy)
transition decision.outcome
db.add(AuditRecord(...))                                  # immutable
await _post_decision_actions(...)                         # LOS/LMS/advisory/WhatsApp
```

Two concurrency details that matter:

**`asyncio.to_thread` for CPU work.** Feature building, model inference and SHAP are
synchronous and CPU-bound. Run directly in an async handler they would block the event loop —
and because ingestion calls the app's *own* HTTP endpoints, a blocked loop would deadlock the
very requests it is waiting on. Moving them to a worker thread is not a micro-optimisation; it
is required for correctness in this architecture.

**Nothing is ever left stuck.** `process_after_consent` wraps `_process` in a try/except that,
on any failure, logs, writes a `PIPELINE_ERROR` timeline event, and transitions the application
to `INSUFFICIENT_DATA` with reason "pipeline error — referred to manual review". An application
can never sit in `INGESTING` forever with a spinner on the dealer's screen.

### Phase 4 — `_post_decision_actions()`

| Outcome | Actions |
|---|---|
| `APPROVED` | LOS handoff (returns a reference like `LOS-A1B2C3D4`, plus "e-NACH mandate registered (mock)") → LMS creates a loan account → ladder starts at STARTER/50 → WhatsApp confirmation |
| `CONDITIONAL_APPROVAL` | WhatsApp message naming the reduced ticket |
| `DECLINED_WITH_PLAN` | generate the advisory plan (timeline records `source: llm \| fallback`) → store it → send it on WhatsApp with a link to `/plan/{id}` |
| `INSUFFICIENT_DATA` | a "we need more information" message |

## 31. Hexagonal architecture (ports and adapters)

**The idea** (also called Clean Architecture): business logic talks to **abstract interfaces**,
never to concrete vendors. Vendors live at the edges, behind those interfaces. Swapping a
vendor touches one file.

The five ports (`adapters/interfaces.py`):

```python
class BureauAdapter(ABC):
    async def check(self, mobile_hash: str, pan_hash: str) -> BureauResult: ...

class DataSourceAdapter(ABC):
    name: str                       # "aa" | "telecom" | "business" — also the consent group
    async def fetch(self, mobile_hash, consent_id, simulate_outage=False) -> SourceResult: ...

class LOSAdapter(ABC):              # Loan Origination System
    async def handoff(self, application_id, summary) -> LOSHandoff: ...

class LMSAdapter(ABC):              # Loan Management System
    async def create_loan_account(...) -> dict: ...
    async def record_repayment(self, loan_id, status) -> dict: ...

class MessagingProvider(ABC):
    async def send_template(self, to, template_name, language, params) -> SendResult: ...
    async def send_text(self, to, body) -> SendResult: ...
    def parse_webhook(self, payload) -> list[WebhookEvent]: ...

class LLMClient(ABC):
    @property
    def available(self) -> bool: ...
    async def complete_json(self, system_prompt, user_prompt) -> str: ...
```

Wiring is one 48-line file (`adapters/registry.py`):

```python
def get_data_sources() -> dict[str, DataSourceAdapter]:
    global _sources
    if _sources is None:
        _sources = {"aa": MockAAAdapter(), "telecom": MockTelecomAdapter(), "business": MockBusinessAdapter()}
    return _sources

def override(*, bureau=None, sources=None) -> None:     # used by tests
    ...
```

To go live with a real Account Aggregator you write a `FinvuAAAdapter(DataSourceAdapter)` and
change one line in this file. The orchestrator, feature pipeline, model, UI and tests are all
untouched. That is the whole payoff, and it is the honest answer to "how far is this from
production?" for the *integration* dimension (the model is a separate question).

A detail that makes the abstraction real rather than decorative: **`SourceResult` has no
exception path**. Adapters are contractually forbidden from raising — every failure becomes a
typed status. The orchestrator therefore has no try/except around ingestion, and graceful
degradation is structural instead of being a thing someone remembered to code.

## 32. The mock vendors

The `/mock/*` endpoints are stand-ins for five real vendors:

| Endpoint | Method | Stands in for | Consent group |
|---|---|---|---|
| `/mock/bureau/check` | POST | CIBIL / Experian / Equifax | **none** — a bureau check is the lender's own legitimate-interest enquiry |
| `/mock/aa/bank-statement` | GET | an Account Aggregator (Finvu, OneMoney, Setu) | `aa` |
| `/mock/telecom/recharge` | GET | a telco or a data partner | `telecom` |
| `/mock/business/gst-returns` | GET | GSTN / a GSP | `business` |
| `/mock/business/mandi-receipts` | GET | an eNAM / mandi board feed | `business` |

Three design points:

**They are routers in the same app, called over HTTP.** A single process, a single port, a
single ngrok tunnel — but the calls traverse the real HTTP stack, so timeouts, status codes and
connection errors are genuinely exercised.

**They enforce consent.** Not simulated enforcement — the guard dependency calls the same
`verify_for_source()` the rest of the system uses, hits the same database, and returns HTTP
403 with a specific code. `test_consent.py` has 10 tests attacking these endpoints.

**They can fail on demand.** `?simulate_outage=true` makes the endpoint
`await asyncio.sleep(policy.ingestion.outage_sleep_seconds)` = 5 s, against a caller timeout of
3 s. That is what the dealer-form checkboxes do, and it is how persona 7 demonstrates
degradation.

A note of self-criticism that is better said than hidden: the mocks verify consent by reading
the application's own database. A real vendor would validate a consent *handle* with the
Account Aggregator, not query the lender's database. It is noted in the README's limitations.

## 33. The graduation ladder

The retention and growth mechanic: a customer approved at the bottom tier earns their way up
through repayment behaviour.

```
behaviour score starts at 50 (of 100)

  ON_TIME  → +5
  LATE     → −8          ← asymmetric on purpose: trust is slow to build, fast to lose
  MISSED   → −15

tiers (from policy.yaml):
  STARTER      ≥ 0    two-wheeler ₹80,000   · used car    —      · tractor    —
  GROWTH       ≥ 70   two-wheeler ₹1,20,000 · used car ₹2,00,000 · tractor    —
  ESTABLISHED  ≥ 85   two-wheeler ₹1,80,000 · used car ₹3,50,000 · tractor ₹5,00,000
```

Six on-time EMIs: 50 → 80, crossing into GROWTH, raising the two-wheeler limit to ₹1,20,000 and
**unlocking used cars entirely**. That is a tangible, visible reward.

Implementation notes: the score is clamped to [0, 100]; `limit_for()` never returns less than
what was actually sanctioned (`max(sanctioned, tier_limit)`), so a tier change can never
retroactively shrink an existing loan; every event is recorded in `repayment_events` with the
delta and the resulting score and tier, so the history is auditable.

The UI steps through each simulated EMI with a 280 ms pause (`LadderVisual.tsx:20`) so the bar
visibly climbs rather than jumping — a deliberate demo affordance.

---
---

# Part F — External integrations

## 34. WhatsApp / Meta Cloud API, in full

### Why WhatsApp at all

The target customer is a farmer, gig worker or small shopkeeper in a small town. They will not
install a lender's app, may not read email, and may be uncomfortable with a dense web form. They
use WhatsApp daily. Delivering the consent request and the decision there is a genuine product
decision, not a gimmick.

### The vocabulary you need

| Term | What it means |
|---|---|
| **WhatsApp Cloud API** | Meta-hosted WhatsApp Business API. You call `graph.facebook.com`; Meta runs the infrastructure. |
| **Phone Number ID** | The numeric id of your sending number (here `1299240743270975`). Not the phone number — the API object id. |
| **WABA ID** | WhatsApp Business Account id; groups numbers and templates. |
| **Access token** | The bearer credential. **Temporary** tokens from the developer dashboard last ~24 h; **System User** tokens can be long-lived. |
| **Test number** | The free number Meta gives a new app (here `+1 555-669-7571`). It can only message numbers you have explicitly added to an allow-list. |
| **Template** | A pre-approved message with optional variables. Required for business-initiated contact. `hello_world` is the sample template every app has. |
| **24-hour customer service window** | After a user messages your business, you may send **free-form** text for 24 hours. Outside it, only templates. This is Meta's anti-spam rule and it shapes the entire messaging design. |
| **Webhook** | An HTTPS endpoint Meta calls with inbound messages and delivery statuses. |

### The window problem, and how the code solves it

The consent request needs to contain a **URL unique to this application**
(`https://.../consent/<session-id>`). But outside the 24-hour window only templates may be
sent, and `hello_world` takes no variables — so the link cannot ride on it.

The resolution (`adapters/messaging/manager.py:100`):

| Situation | What is actually sent |
|---|---|
| Consent request, window **open** | free-form text containing the real consent link ✅ |
| Consent request, window **closed** | the `hello_world` template (no link) — and the dealer UI shows the link plus a QR code as the fallback |
| Decision / plan, window **open** | free-form text, full plan, Devanagari fine ✅ |
| Decision, window closed, status template configured | that template |
| Decision, window closed, no status template | **not sent**; held in the outbox and flushed later |
| Any real send fails | marked `failed_real_send` with the reason; the flow continues |

Hence the standing demo instruction: **text "Hi" to the business number before presenting.**
That opens the window and the consent link arrives as a real message.

Two refinements worth noting:

**The window is keyed by recipient number, not just by application** (`manager.py:41`):

```python
real_number = to_wa_number(self.env.demo_recipient_number or app.mobile_number)
... where(Message.direction == "INBOUND",
          Message.created_at >= utcnow() - timedelta(hours=24),
          or_(Message.application_id == app.id, Message.recipient == real_number))
```

So one "Hi" opens the window for *every* subsequent demo application, not just the first.
There is also a test that another number's window does **not** count
(`test_messaging.py:151`).

**`flush_pending()`** (`manager.py:80`): when an inbound message arrives, the webhook looks for
result messages that were held back as simulated-only and sends them for real, right then. The
customer messages you, and the plan that was waiting arrives immediately.

### The outbox pattern

```python
msg = Message(application_id=..., direction="OUTBOUND", purpose=purpose,
              provider="simulated", body=body, delivery_status="queued")
db.add(msg)
await db.flush()          # the row exists BEFORE any network call
if self.real_enabled:
    ...attempt the real send, then update the row...
```

**The outbox row is always written first, in every mode.** Consequences: the dashboard message
log always shows what *would* be sent, including the full text and the link; a failed real send
leaves a record with the reason; the whole feature works offline with
`MESSAGING_MODE=simulated`; and there is no window in which a message was sent but not recorded.

### Error handling that respects the developer

Graph API error codes are translated into actionable hints (`whatsapp.py:17`):

| Code | Hint shown |
|---|---|
| 190 | access token expired/invalid — refresh it (or use a long-lived system-user token) |
| 131030 | recipient not in the allowed list — add the number under "Send and receive messages → To" |
| 131047 | 24-hour customer-service window closed — only approved templates can be sent |
| 132001 | template does not exist in this language / not approved |
| 100 | invalid parameter (check phone number ID / payload) |

This is the difference between "send failed" and knowing what to do. During development the
phone-number and WABA ids from the implementation plan turned out to be missing their last
digit — error code 100 plus this hint is what located that quickly.

### Webhooks

```
GET  /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
     → if the token matches (constant-time compare), echo the challenge back as plain text
POST /webhooks/whatsapp
     → optional X-Hub-Signature-256 HMAC verification (if WHATSAPP_APP_SECRET is set)
     → parse into WebhookEvents:
         "inbound" → store the message; attribute it to an application; flush_pending()
         "status"  → update that message's delivery_status (sent/delivered/read/failed)
```

Inbound attribution is neat: the consent page's `wa.me` link pre-fills
`"Hi Saksham, I have given my consent. Ref a1b2c3d4"`, and the webhook extracts that 8-character
reference with a regex to find the right session (`webhooks.py:41`), falling back to the most
recent application for single-recipient demos.

Delivery statuses are what put the ✓/✓✓/✓✓-read ticks in the dashboard — the same semantics as
the WhatsApp UI, which makes the demo legible without explanation.

### Pre-flight validation

`make check-whatsapp` (`scripts/check_whatsapp.py`) checks, in order: config (with secrets
masked), that `PUBLIC_BASE_URL/health` is reachable from the internet, that the WhatsApp
credentials authenticate (`GET` the phone-number object — no message sent), **how long the
token has left** (via `debug_token`), optionally sends a real test template, and that Gemini
responds. `ARGS=--no-send` validates without sending. Running this before presenting is the
single highest-value habit for this project, because the most likely failure is an expired
token.

## 35. Google Gemini and the guardrails

### What it is used for — and only for

Gemini writes the **three-step improvement plan** for declined applicants, in their language.
That is the entire scope. It does **not** touch the credit decision, the score, or any number.
This boundary is deliberate: an LLM in a lending decision path is a regulatory and
reproducibility problem; an LLM rewriting pre-computed advice into warm vernacular prose is a
good use of the technology.

### The call

```python
# adapters/llm/gemini.py
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
body = {
    "systemInstruction": {"parts": [{"text": system_prompt}]},
    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
    "generationConfig": {"responseMimeType": "application/json",
                         "temperature": 0.4, "maxOutputTokens": 2048},
}
resp = await client.post(url, json=body,
                         headers={"x-goog-api-key": api_key},   # header, NOT the URL
                         timeout=6.0)
```

Choices here: **raw REST via httpx** rather than the `google-generativeai` SDK (one fewer
dependency; full control over timeout and error text); the key travels in a **header**, never a
query string (query strings land in logs and proxies); `responseMimeType: "application/json"`
asks Gemini to emit JSON natively; `temperature 0.4` is warm enough to sound human, cool enough
to stay on task; and a **hard 6-second timeout** with a fallback, so a slow model can never
stall an application.

Model choice: `gemini-3.5-flash-lite`. `gemini-3.8-flash` was tried and took around 10 seconds,
which exceeded the timeout and meant *every* plan silently fell back to templates. The lite
model responds well within budget. (The earlier default `gemini-2.0-flash` now returns 404 —
"no longer available" — which is a good argument for the model being a config value.)

### The prompt

```
You are a financial advisor writing a simple, encouraging action plan for a loan applicant
in {language}. The applicant's name is {first_name}.

You will receive up to 3 areas where the applicant can improve, each with a suggested action.
For each, write one clear, actionable step in simple everyday language that a person in a
small town can understand.

Rules:
- Never reveal the score or any formula
- Never promise approval or guarantee any outcome
- Never invent numbers not provided to you
- Use a respectful, encouraging tone
- Maximum 3 steps
- Write ONLY in {language}
- Output strict JSON: {"greeting","summary","steps":[...],"closing"}
```

The user message is JSON containing only the applicant's first name, the product label, and the
3 areas with their deterministic problem/action text. **The score, the PD and the raw features
are never sent to Gemini** — the model sees reason codes, not a credit file.

### The guardrails — the part that matters

Prompt instructions are requests, not guarantees. Every response is **validated**, and any
failure silently falls back to the deterministic plan (`services/advisory.py:88`):

| # | Check | Rejects |
|---|---|---|
| 1 | strips markdown fences, parses as JSON, requires an object | prose, malformed JSON |
| 2 | `greeting`, `summary`, `closing` are non-empty strings | missing fields |
| 3 | `steps` is a list of 1–3 non-empty strings | too many/zero steps, wrong types |
| 4 | no phrase from `policy.yaml → advisory.forbidden_phrases` appears | "guaranteed", "will be approved", "your score is", "आपका स्कोर", "तुमचा स्कोर" |
| 5 | **every digit sequence in the output also appeared in the input** | invented numbers — hallucinated amounts, rates, timelines |
| 6 | script check: Devanagari ≥ 40% for hi/mr; ≤ 10% for en | wrong-language output |

Check 5 is the cleverest and is worth describing in a presentation. It normalises Devanagari
digits (`०१२३४५६७८९`) to ASCII first, then does a set difference:

```python
invented = _numbers(output) - allowed_numbers        # allowed = numbers present in the input
if invented: raise ValueError(f"invented numbers: {sorted(invented)}")
```

So the model cannot tell someone "save ₹5,000 a month" or "reapply after 90 days" unless that
figure came from the system. This closes off the single most dangerous failure mode for
financial advice generated by a language model.

### The fallback is a first-class path, not an afterthought

```python
plan = self.render_deterministic(negatives, lang, sku, first_name)   # built FIRST, always
if self.llm.available and negatives:
    try:
        raw  = await self.llm.complete_json(...)
        out  = self._validate(raw, lang, _numbers(user))
        plan = Plan(**out, source="llm", ...)                        # upgrade only if valid
    except Exception as exc:
        plan.fallback_reason = f"{type(exc).__name__}: {exc}"[:200]
        log.warning("LLM advisory fell back to templates: %s", plan.fallback_reason)
```

The deterministic plan is composed first, from the `action:` strings in `reason_codes.yaml`, in
all three languages. The LLM is an *upgrade* attempted on top. Any failure — no key, timeout,
bad JSON, guardrail violation — leaves a complete, correct, translated plan in place, and
records *why* it fell back (visible in the pipeline trace as `source: fallback` with the reason).
`LLM_FALLBACK_ONLY=true` forces this path for a fully offline demo.

Plans are cached in an LRU keyed by `(reason codes, language, product, first name)`, size 256,
so re-opening a plan page or switching language does not re-bill the API.

## 36. ngrok: what it is and exactly why it is needed

**What ngrok is.** A tunnelling service. You run `ngrok http 8000` and it gives you a public
HTTPS URL (e.g. `https://rocklike-handiwork-lived.ngrok-free.dev`) that forwards to
`localhost:8000` on your machine. It is the standard way to expose a local development server
to the internet.

**Why this project cannot work without it (or an equivalent).** Two independent reasons:

**1. The consent link must open on a real phone.**

```
Dealer starts an application
  → the backend builds   consent_url = PUBLIC_BASE_URL + "/consent/" + session_id
  → that URL is sent to the customer's phone over WhatsApp
  → the customer taps it
```

If `PUBLIC_BASE_URL` is `http://localhost:8000`, the phone tries to open *its own* localhost and
fails. The URL must be publicly resolvable. `check_whatsapp.py:40` warns about exactly this.

**2. Meta's webhooks must be able to reach you.**

Delivery statuses (✓✓ read) and inbound messages ("Hi") arrive because Meta makes an HTTPS
POST to a callback URL you register. Meta's servers cannot reach your laptop. The webhook URL
registered in the Meta dashboard is `https://<tunnel>/webhooks/whatsapp`.

**The operational catch.** On the free tier the subdomain **changes every time the tunnel
restarts**. When it does, two things must be updated:

1. `PUBLIC_BASE_URL` in `.env` — **and the server restarted**, because settings are cached.
2. The webhook callback URL in the Meta dashboard (App → WhatsApp → Configuration), with the
   same verify token.

Hence the standing advice: start the tunnel, then leave it alone for the whole demo.

**Alternatives**, all equivalent in principle: Cloudflare Tunnel (`cloudflared`, free, stable
subdomain with an account), ngrok paid (reserved domain), `localtunnel`, Tailscale Funnel, or
simply deploying to any cloud host with a real domain — which is what production would do.

`vite.config.ts` sets `allowedHosts: true` so the dev server also accepts tunnelled requests,
though the single-origin `make demo` mode is what the demo actually uses.

---
---

# Part G — Reference

## 37. Every API endpoint

### Meta

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{"status": "ok"}` — used by the tunnel check and monitoring |
| GET | `/docs` | FastAPI's interactive Swagger UI (free, from the type hints) |
| GET | `/openapi.json` | the generated OpenAPI schema |

### Applications — `/api/v1/applications`

| Method | Path | Body / params | Returns |
|---|---|---|---|
| POST | `/create` | `mobile_number`, `pan_token`, `aadhaar_token`, `requested_product_sku`, `applicant_name`, `preferred_language`, `persona_name?`, `demo_options?` | `application_id`, `status`, `session_id`, `consent_url`, `bureau_result`, `expires_at` |
| GET | `/{id}` | — | the full application view: status, outcome, terminal flag, applicant, masked mobile, product, EMI, ticket, tenure, bureau result, consent artifact, score, PD, loan + ladder, `timeline[]`, `transitions[]` |
| GET | `/{id}/trace` | — | `stages[]` with per-stage latency, `total_latency_ms` (consent→decision), `sources{}` with per-source status/latency/detail, `message_delivery{}` |
| GET | `/{id}/decision` | — | `score`, `pd`, `outcome`, `suggested_ticket`, `approve_cutoff`, `shap_drivers{positive,negative}`, `waterfall[]`, `base_score`, `affordability{}`, `audit_record_id`, `model_version`, `policy_version`, `feature_vector_hash` — **409** if no decision yet |
| GET | `/{id}/plan?lang=` | optional `lang` | `greeting`, `summary`, `steps[]`, `closing`, `language`, `source`, `reason_codes[]` — **404** unless the outcome is `DECLINED_WITH_PLAN` |

### Consent — `/api/v1/consent`

| Method | Path | Purpose |
|---|---|---|
| GET | `/session/{session_id}` | what the phone page renders: applicant, product (in all languages), purpose, `seconds_remaining`, groups, `consent_valid_days`, `whatsapp_link` |
| POST | `/authorize` | `{session_id, grants: {aa, telecom, business}, purpose?}` → the consent artifact. Starts the background pipeline. 410 if expired, 409 if already used |
| POST | `/deny` | `{session_id}` → `CONSENT_DENIED`, no data requested |
| POST | `/revoke` | `{consent_id}` → `{revoked: true, features_purged: bool}` |

### Messages / LMS

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/messages/{application_id}` | the whole outbox for this application: direction, purpose, provider, type, template, masked recipient, body, link, delivery status, error |
| POST | `/api/v1/lms/repayment-event` | `{loan_id, status: ON_TIME\|LATE\|MISSED}` → updated behaviour score, tier, limit |
| GET | `/api/v1/customers/{customer_id}/ladder` | ladder state plus full repayment history (accepts a `customer_id` or a `loan_id`) |

### Webhooks

| Method | Path | Purpose |
|---|---|---|
| GET | `/webhooks/whatsapp` | Meta's verification challenge (`hub.mode`, `hub.verify_token`, `hub.challenge`) |
| POST | `/webhooks/whatsapp` | inbound messages and delivery statuses; optional signature check |

### Demo helpers — `/demo`

| Method | Path | Purpose |
|---|---|---|
| POST | `/reset` | drain background tasks, drop and recreate all tables, clear caches — **but preserve recent inbound WhatsApp messages**, because those record a real-world fact (the 24 h window), not demo state |
| GET | `/personas` | the 7 personas with product label, EMI and ticket resolved |
| GET | `/config` | everything the UI needs: dealer, public base URL, messaging status, LLM status, model version + metrics, policy thresholds, products, languages. **Secret-free by construction** |
| POST | `/simulate-repayments` | `{loan_id, count, status}` → runs N repayment events and returns each intermediate step for the climbing animation |

### Mock vendors — `/mock`

| Method | Path | Consent group |
|---|---|---|
| POST | `/bureau/check` | none |
| GET | `/aa/bank-statement` | `aa` |
| GET | `/telecom/recharge` | `telecom` |
| GET | `/business/gst-returns` | `business` |
| GET | `/business/mandi-receipts` | `business` |

All data endpoints take `?mobile_hash=` and an `X-Consent-Token` header, and accept
`?simulate_outage=true`.

### SPA fallback

`GET /{path:path}` serves `frontend/dist`, with history-API fallback to `index.html`, so
`/consent/abc` and `/plan/xyz` work on a hard refresh. Paths beginning `api/`, `mock/`,
`webhooks/`, `demo/` or `health` are excluded so a typo returns a JSON 404 rather than HTML.

### The uniform error shape

```json
{"error": {"code": "SESSION_EXPIRED", "message": "This consent link has expired."}}
```

Every error, from validation to consent rejection to unhandled exception, has this shape
(`core/errors.py`). The frontend's `ApiError` class reads `code` and `message`, which is why the
UI can react specifically — e.g. a 404 clears a stale application id, and `SESSION_EXPIRED`
shows the expired screen rather than a generic failure.

## 38. Database schema — all 9 tables

```
applications ──┬── consent_sessions ──── consent_artifacts
               ├── consent_log
               ├── audit_records  (1:1, unique)
               ├── timeline_events
               ├── messages
               └── loans ──── repayment_events
```

**`applications`** — the central row. Identity (`mobile_number`, `mobile_number_hash`,
`pan_token_hash`, `aadhaar_token_hash`), request (`requested_product_sku`, `requested_emi`,
`ticket_size`, `preferred_language`), state (`status`, `outcome`), bureau result, session and
consent URL, results (`score`, `pd`, `suggested_ticket`), `feature_vector_json` (purged on
revoke) and `feature_vector_hash` (kept), `plan_json`, plus demo fields.

**`consent_sessions`** — `status` (`OPEN|GRANTED|DENIED|EXPIRED`), `expires_at`.

**`consent_artifacts`** — three boolean grants, `purpose`, `signature`, `revoked`, `granted_at`,
`expires_at`, `revoked_at`.

**`consent_log`** — append-only `GRANTED | DENIED | REVOKED` events with timestamps.

**`audit_records`** — one per decision, `unique=True` on `application_id`, never updated:
`model_version`, `policy_version`, `consent_id`, `feature_vector_hash`, `raw_score`,
`calibrated_pd`, `final_score`, `outcome`, `shap_top_positive`, `shap_top_negative`,
`reason_codes`, `waterfall_json`.

**`timeline_events`** — the event log driving the whole UI: `stage`, `status`, `latency_ms`,
`details` (JSON), `timestamp`.

**`messages`** — the outbox and inbox: `direction`, `purpose`, `provider`, `message_type`,
`template_name`, `recipient`, `body`, `link_url`, `whatsapp_message_id`, `delivery_status`,
`error`, `status_updated_at`.

**`loans`** / **`repayment_events`** — the mock LMS and the ladder history.

Conventions: UUID string primary keys (except the two autoincrement event tables); **all
timestamps are naive UTC** (SQLite drops tzinfo, so `timeutil.utcnow()` normalises and `iso()`
appends `Z` on the way out); SQLite PRAGMAs set at connect time — `journal_mode=WAL`,
`foreign_keys=ON`, `busy_timeout=5000`.

## 39. Backend code walkthrough, file by file

### `core/` — infrastructure

| File | Lines | What it does |
|---|---|---|
`config.py` | 241 | `EnvSettings` (from `.env`) + the whole `Policy` tree as pydantic models + personas + reason codes, behind a cached `get_settings()`. `ScorecardPolicy.resolved_offset` derives the offset from the anchor. |
`database.py` | 78 | async engine/sessionmaker, SQLite PRAGMAs, `create_all`, `drop_and_create_all`, `get_session` dependency. |
`security.py` | 85 | `hmac_hex`, `tokenize_identifier`, `normalize_mobile`, `mobile_hash` (keyed), `vendor_ref` (unkeyed), `sign_payload`/`verify_signature`, `sha256_hex`, `mask_secret`, `mask_secrets`. |
`errors.py` | 58 | `AppError`/`NotFound`/`ConsentError`, four exception handlers, one error shape. |
`http.py` | 31 | the shared httpx client, with `max_keepalive_connections=0` (a stale pooled connection must never stall a source fetch) and an override hook for tests. |
`logging.py` | 33 | the `SecretFilter` applied to every record; silences httpx's URL logging. |
`timeutil.py` | 12 | `utcnow()` (naive UTC), `iso()` (with `Z`). |

### `domain/` — pure logic, no I/O

| File | Lines | What it does |
|---|---|---|
`scorecard.py` | 27 | `pd_to_score`, `score_to_pd`. |
`policy.py` | 28 | `evaluate_decision` — the three bands. |
`state_machine.py` | 47 | the 13 states, the transition table, `validate_transition`. |
`reason_codes.py` | 60 | `ReasonCatalog` over `reason_codes.yaml`: `code_for`, `label`, `text`, `action`, `template`, `product_label`, `reportable`. |

### `adapters/` — all external contact

| File | Lines | What it does |
|---|---|---|
`interfaces.py` | 105 | the five ports and their result dataclasses. `SourceResult.usable` is the key property. |
`registry.py` | 48 | the wiring, plus `override()` for tests. |
`bureau.py` | 17 | HTTP call to the mock bureau. |
`data_sources.py` | 91 | the three source adapters. `_get()` maps every failure to a typed status; `MockBusinessAdapter` fans out to GST + mandi. |
`los.py` | 30 | mock LOS (returns a reference) and mock LMS (creates a loan via the ladder service). |
`messaging/whatsapp.py` | 147 | the Cloud API provider: templates, free text, `check_credentials`, `token_expiry_days`, `parse_webhook`, error hints, token scrubbing. |
`messaging/simulated.py` | 21 | succeeds instantly; the outbox row *is* the delivery. |
`messaging/manager.py` | 134 | routes by `MESSAGING_MODE`, always writes the outbox, implements `window_open`, template-vs-text selection, and `flush_pending`. |
`llm/gemini.py` | 52 | the REST call, header auth, hard timeout, scrubbed errors. |
`llm/fallback.py` | 15 | `available = False` → tells the advisory service to render templates. |

### `services/` — orchestration

| File | Lines | What it does |
|---|---|---|
`orchestrator.py` | 350 | the whole flow. Read first. |
`feature_pipeline.py` | 281 | the 42 feature specs with monotone directions, four per-group functions, `build_features`. |
`scoring.py` | 87 | loads the artifacts, re-orders features to the stored schema, predicts, warns on feature-policy drift. |
`explainability.py` | 98 | SHAP → score points → reason codes → waterfall. |
`advisory.py` | 168 | the prompt, the six guardrails, the deterministic renderer, the LRU cache. |
`consent.py` | 111 | artifacts, signing, the six-check verifier, revocation with purge. |
`ingestion.py` | 31 | parallel consent-gated fetch; `to_raw_payloads`; `usable_groups`. |
`ladder.py` | 100 | behaviour score, tiers, limits, repayment events. |
`notifications.py` | 49 | builds message bodies from `reason_codes.yaml` templates in the right language. |
`queries.py` | 138 | the read-side views. Also `display_status()`, which ages simulated messages through sent→delivered→read so simulated mode still shows delivery progress. |

### `api/` — thin routers

`applications.py` (37), `consent.py` (29), `messages.py` (14), `lms.py` (18), `webhooks.py` (84),
`demo.py` (94), `schemas.py` (51). They validate and delegate; no business logic lives here.

### `mock_services/`

`generators.py` (317) — the simulator. `personas.py` (42) — hash → Profile/bureau.
`routers.py` (84) — the endpoints with the consent guard and the outage switch.

## 40. Frontend code walkthrough, file by file

### Entry and plumbing

| File | What it does |
|---|---|
`main.tsx` | mounts React with `BrowserRouter`. |
`App.tsx` | three routes; `Dashboard` is `lazy()`-loaded so the phone pages stay small. |
`api/client.ts` | a typed `fetch` wrapper. Parses the uniform error shape into `ApiError{code, status, message}`; turns a network failure into a readable message. |
`api/types.ts` | TypeScript mirrors of every API response (198 lines). The build fails if the backend's shape changes. |
`hooks/usePolling.ts` | poll a function every N ms while enabled; keeps `fnRef.current` fresh to avoid stale closures. |
`hooks/useApplication.ts` | composes three polls. **Only ever exposes data whose `application_id` matches the current id** — this is the fix for the "New application" button appearing to do nothing. Keeps polling ~20 s past the terminal state for delivery ticks. |
`i18n.ts` | all phone-page strings in EN/HI/MR with `{placeholder}` interpolation. |
`styles/index.css` | the dark theme as ~20 `@theme` tokens, plus `.btn-dark`, `.btn-ghost`, `.field`, and the `.acc` accordion (a CSS-grid `grid-template-rows: 0fr → 1fr` transition that animates height without measuring it). |

### Components

| File | What it does |
|---|---|
`Dashboard.tsx` (241) | the dealer console. `Nav` (lockup, a System popover showing live model/WhatsApp/LLM status, Reset, New application); `Landing` (video hero + form card overlapping it); `Console` (video hero, headline, three tiles, then accordions). `LoanSummary` + `nextStep()` live here. |
`DealerPOS/ApplicationForm.tsx` | persona picker that auto-fills, collapsed "Applicant details", and the outage toggles. |
`DealerPOS/StatusTimeline.tsx` | `buildSteps()` derives a human narrative from timeline events, with `done/active/pending/warn` states — including the branches for bypass, denial, expiry and insufficient data. |
`DealerPOS/DecisionDetails.tsx` | `Drivers` (helping vs holding back, with reason codes and points) and `AuditPanel` (audit id, model, policy, feature hash, consent, and the Revoke button). |
`UnderTheHood/ScoreGauge.tsx` | a hand-built SVG semicircular gauge, 300–900, with the cutoff ticked, the borderline band shaded, a cubic-eased count-up and an `onDark` palette. |
`UnderTheHood/SHAPWaterfall.tsx` | the Recharts horizontal waterfall in score points, green up / amber down, labelled "Average applicant" → "This applicant". |
`UnderTheHood/SourceStatus.tsx` | per-source status with latency and a spinner while pending. |
`UnderTheHood/PipelineTrace.tsx` | every stage with a latency bar, status badges, detail lines, and the delivery ticks. |
`UnderTheHood/LadderVisual.tsx` | behaviour score, tier markers, next-tier requirement, and the stepped animation. |
`Messages/MessageLog.tsx` | what was sent, via what, whether it arrived, the full text in a `<details>`, plus the consent link with copy button. |
`Messages/QrCode.tsx` | renders the consent URL as a QR — the WhatsApp-independent fallback. |
`ConsentPage/ConsentPage.tsx` (158) | the customer's screen: `MobileShell` (shared with the plan page), language chips, three toggles, the countdown, and all seven terminal states (granted/denied/expired/used/not found/offline). |
`PlanPage/PlanPage.tsx` | the action plan with alternating step cards and a language switcher. |
`Brand.tsx` | `SakshamLogo` (drawn via CSS mask so it inherits `currentColor`), `TvsCredit` (on a white chip, because its blue is invisible on the dark theme), `Lockup`. |
`VideoBg.tsx` | the looping muted hero video with poster fallback, a legibility scrim, a `startAt` offset and respect for `prefers-reduced-motion`. |
`ui.tsx` | `Badge`, `Spinner`, `StatusBadge`, `OUTCOME_META`, `ErrorNote`, and the collapsible `Section`. |

One UI decision worth calling out: in `OUTCOME_META`, `DECLINED_WITH_PLAN` is styled **amber,
never red**, with the label "Guidance plan sent". The code comment says it plainly: *this is
guidance, not rejection*. The product philosophy is enforced in the design tokens.

## 41. The Makefile and every command

```makefile
PY := .venv/bin/python     # relative, because the repo path contains a space
PORT ?= 8000
```

That comment matters: this repo lives at `/run/media/ronit/New Volume/...`. An absolute
unquoted path breaks on the space, so every target does `cd backend` first and uses a relative
interpreter path.

| Command | What it does | When to use it |
|---|---|---|
| `make install` | create the 3.11 venv, install requirements, `npm install` | once, after cloning |
| `make dev` | backend on :8000 with `--reload` **and** Vite on :5173, killed together via `trap 'kill 0' EXIT` | while coding |
| `make backend` / `make frontend` | either half alone | debugging |
| `make build-demo` | install, train only if artifacts are missing, build the frontend | before a demo |
| `make demo` | one process on :8000 serving API + mocks + the built UI | **the demo command** |
| `make train` | regenerate data and retrain (~2 min), rewrite artifacts and `report.md` | after changing `features:` or `ml:` |
| `make seed` / `make reset` | wipe the database | between runs |
| `make test` | pytest; `make test ARGS='-k e2e'` to filter | always, before presenting |
| `make check-whatsapp` | validate credentials, tunnel and Gemini; `ARGS=--no-send` to skip sending | before every demo |

**Why `make demo` rather than `make dev` for a presentation:** `demo` is single-origin. The
Python server serves the built React app, so the dealer console, the consent page, the API and
the mocks are all on one port — which means **one ngrok tunnel**. With `make dev` the UI is on
:5173 and the API on :8000, which needs either two tunnels or proxy configuration.

## 42. The test suite — all 99 tests

```
tests/test_advisory.py          16
tests/test_consent.py           10
tests/test_e2e_personas.py      21
tests/test_feature_parity.py     5
tests/test_feature_pipeline.py  12
tests/test_generators.py         7
tests/test_messaging.py         20
tests/test_scorecard.py          8
                           ───────
                                99   ✅ all passing
```

### The harness (`conftest.py`)

```python
os.environ.update({                      # set BEFORE any app module reads settings
    "MESSAGING_MODE": "simulated", "LLM_FALLBACK_ONLY": "true",
    "GEMINI_API_KEY": "", "WHATSAPP_ACCESS_TOKEN": "",
    "SECRET_KEY": "test-secret-key", "PUBLIC_BASE_URL": "https://test.example.com",
    "DEMO_RECIPIENT_NUMBER": "",
})
```

Environment variables beat `.env`, so **a developer's real keys can never be used by the test
suite** — no accidental WhatsApp messages, no accidental Gemini billing. Each test gets a fresh
SQLite file in `tmp_path`. The `client` fixture wires httpx's `ASGITransport` into
`override_http_client()`, so when an adapter "calls `/mock/aa/bank-statement` over HTTP" it is
routed in-process — real HTTP semantics, no network. A session-scoped fixture trains the model
if artifacts are missing.

### What each file proves

**`test_scorecard.py` (8)** — the 650↔7% anchor round-trips; 60 points really doubles the odds;
monotonicity and clamping; an explicit offset override wins; the three decision bands;
borderline can be disabled by config; the state machine permits only declared transitions; the
flat-rate EMI formula.

**`test_generators.py` (7)** — payloads are deterministic for the same seed and differ across
seeds; the AA payload has the right shape and **UPI appears as a transaction mode, not a
source**; per-segment data availability; creditworthiness actually moves the statistics in the
expected direction; bureau defaults to NO_HIT; **persona data does not depend on `SECRET_KEY`**
(the regression test for the bug described in [section 8](#8-stage-1-the-profile--one-number-that-drives-everything)).

**`test_feature_pipeline.py` (12)** — all 42 features present and in order; empty payloads give
`NaN` and zero flags rather than a crash; hand-computed checks for buffer ratio, the 90-day
bounce window, income mix, telecom gaps (including the open gap to today), GST (including the
December due-date year rollover), mandi, affordability and the availability flags.

**`test_feature_parity.py` (5)** — the two tests described in
[section 21](#21-trainserve-parity--and-why-it-is-enforced-by-a-test).

**`test_consent.py` (10)** — attacking the mock endpoints: no token → rejected; valid consent →
data; scope is per group; revoked consent blocks access **and** purges features; expired consent
rejected; **tampered signature rejected**; a token cannot be used for another customer; the
bureau needs no consent; a gig worker's business feed returns `no_data`; the outage flag really
causes an adapter timeout.

**`test_messaging.py` (20)** — number normalisation; the exact template request shape and the
recipient override; template variables sanitised of newlines; Devanagari free-text round-trip;
**Graph errors are typed, hinted, and never leak the token**; a network failure is a result not
an exception; an unconfigured provider makes no call; `mask_secrets` scrubs tokens and URLs;
webhook payload parsing; simulated mode writes only the outbox; a real-send failure is marked
and the flow continues; the configured template is used; **a pre-opened window sends the real
consent link**; another number's window does not count; results are free text only inside the
window; the status template is used when configured; the verification challenge; signature
enforcement when `WHATSAPP_APP_SECRET` is set; an inbound message opens the window and status
updates apply; **`/demo/reset` keeps the open WhatsApp window**.

**`test_advisory.py` (16)** — deterministic plans in all three languages; steps come from the
reason-code actions; a plan exists even with no negative drivers; valid LLM output is used; each
guardrail rejects the output it should; a number present in the input is allowed; an LLM error
or timeout falls back; plans are cached per codes and language; WhatsApp message rendering.

**`test_e2e_personas.py` (21)** — all seven personas end to end through the public API, each
asserted against its `expected_outcome` from `personas.yaml`; the consent URL is built from
`PUBLIC_BASE_URL` and is never localhost; persona 1's full trace and audit record; persona 2's
Hindi plan; persona 4's Marathi plan with no LLM key; persona 5 never asks for consent; persona
6 requests no data; persona 7 degrades gracefully and is still approved; partial consent leaves
unconsented sources uncalled; a single source yields `INSUFFICIENT_DATA`; revocation purges and
blocks; session expiry is lazy; authorising twice is rejected; validation errors use the
standard shape; the decision exposes affordability until consent is revoked.

**What is not tested:** there are no frontend unit tests. UI behaviour was verified manually with
a headless Chromium script during development (and several real bugs were found that way — the
"New application" hang among them), but that is not automated. An honest gap.

---
---

# Part H — Honesty

## 43. Known warts and bugs

Things that are genuinely wrong or untidy in the current codebase, stated plainly.

### 1. ~~Three directories named `data`, one of them dead~~ — fixed

There used to be a stray `./data/` at the repo root alongside the live `./backend/data/` and
the (intentional, git-ignored) `./backend/ml/data/`. The cause: `.env` set
`DATABASE_URL=sqlite+aiosqlite:///./data/saksham.db` — a **relative** path — while the
in-code default in `core/config.py` was `REPO_ROOT / 'data' / 'saksham.db'`, an *absolute*
path pointing at the repo root. Those two disagreed. Every Makefile target does `cd backend`
first, so the `.env` override actually resolved to `backend/data/saksham.db` — and that,
not the in-code default, is what was really live. The root `./data/` was a leftover from an
earlier run with a different working directory, before that `cd backend` convention settled;
nothing read or wrote it afterwards.

That mismatch was a real latent bug, not just clutter: anyone running `uvicorn` directly from
the repo root (skipping the Makefile) would have silently opened a *second, empty* database
at the repo-root default instead of erroring.

**Fixed:** the in-code default now points at `BACKEND_ROOT / 'data' / 'saksham.db'` instead of
`REPO_ROOT`, so it's absolute *and* agrees with where the data actually lives regardless of
the process's working directory. The `DATABASE_URL` line was removed from `.env` and
`.env.example` (comments there explain why), and the stray root `./data/` was deleted.

### 2. The project is not under version control

`git status` reports this is not a git repository. There is a `.gitignore`, and commit
attribution conventions exist, but no history. For a hackathon submission this is the highest
risk item in the whole project: one bad edit is unrecoverable, and submission usually requires
a repository.

### 3. ~~Documentation drift~~ — fixed

Four small inconsistencies between the docs/comments and the current code were found and
corrected: `README.md` said "97 tests" (there are 99); its env table listed `LLM_MODEL`'s
default as `gemini-2.0-flash` (the code default is `gemini-3.5-flash-lite`, and
`gemini-2.0-flash` now 404s — see [section 35](#35-google-gemini-and-the-guardrails));
`.env.example` had a comment referring to "the simulated phone mirror", a UI component that
was removed earlier in the build; and `ConsentPage.tsx`'s `MobileShell` docstring still said
"lavender hero card with meadow art", left over from before the video background replaced both.

### 4. Smaller things

- **`product_type_encoded`** ordinally encodes a nominal variable. Harmless with trees and three
  categories, left unconstrained, but not textbook-correct. One-hot or LightGBM's native
  categorical handling would be right at larger cardinality.
- **The mock vendors read the lender's own database** to verify consent. A real Account
  Aggregator would validate a consent handle on its side. Already noted in the README.
- **No pagination anywhere.** `/demo/personas`, the message list and the timeline all return
  everything. Fine at demo scale; wrong at any real scale.
- **No rate limiting and no authentication** on any endpoint.
- **The Saksham logo is my redraw**, not the original artwork — the attachment never landed on
  disk. Drop the original over `frontend/public/brand/saksham-logo.svg` to replace it everywhere.
- **The TVS Credit logo asset is low-resolution** (source 246×138), so it is slightly soft at
  larger sizes.
- ~~`frontend/tsconfig.tsbuildinfo` is a build artifact sitting in the repo~~ — fixed: the
  stray file was deleted and `*.tsbuildinfo` added to `.gitignore`.

## 44. Limitations you should admit before being asked

Volunteering these is stronger than being caught by them.

**On the model**
1. **Synthetic data.** No real repayment outcome informed this model. AUC 0.813 measures
   recovery of a simulated process. The right framing: *the pipeline is production-shaped; the
   model is not production-validated.*
2. **No fairness audit is possible.** The synthetic data has no protected attributes, so
   disparate impact cannot be measured. This is the question I would expect a thoughtful judge
   to ask, and the answer is a plan — demographic parity and equal-opportunity checks across
   gender, region and rural/urban on real data in shadow mode — not a number.
3. **No out-of-time validation and no reject inference.** Both are mandatory for a real
   scorecard.
4. **Scores saturate at the extremes** because the synthetic default process is simple.

**On the data sources**
5. **Everything is mocked** except WhatsApp and Gemini. Real Account Aggregator integration
   involves RBI-regulated consent artifacts, a certified technical service provider, and
   latency and failure characteristics nobody can simulate honestly.
6. **The AA assumption is the load-bearing one.** The whole proposition depends on applicants
   having a bank account with meaningful activity and being willing to share it.
7. **Telecom data is not actually commercially available** to lenders in India in this form,
   today, at this granularity. Worth knowing before claiming it as a ready input.

**On the system**
8. **No authentication, no rate limiting, no multi-tenancy.** A prototype, not a deployment.
9. **SQLite single-writer.** Fine for a demo; a real deployment needs PostgreSQL.
10. **The LLM is a real external dependency** in the decline path. Mitigated by a 6 s timeout
    and a full deterministic fallback, but the dependency is real.

**Operationally, for the demo**
11. **The WhatsApp token is temporary** (~24 h). Generate a System User token for anything
    longer than a quick test.
12. **The ngrok URL changes on restart**, which requires a `.env` edit, a server restart and a
    Meta dashboard update.
13. **The 24-hour window must be opened** by texting the business number, or the consent link
    degrades to a `hello_world` template.

## 45. Glossary

| Term | Meaning |
|---|---|
| **AA (Account Aggregator)** | RBI-regulated intermediary that fetches your financial data with your consent and passes it to a lender. |
| **AUC** | Area Under the ROC Curve. Probability a random defaulter is ranked riskier than a random non-defaulter. 0.5 = random, 1.0 = perfect. |
| **Brier score** | Mean squared error of predicted probabilities. Measures calibration *and* discrimination. Lower is better. |
| **Bureau** | Credit bureau (CIBIL, Experian, Equifax, CRIF) — holds credit history and issues scores. |
| **Calibration** | Whether predicted probabilities match observed frequencies. "Of applicants given 10%, do ~10% default?" |
| **CIBIL** | India's most widely used credit bureau; colloquially, "your CIBIL score". |
| **e-NACH** | Electronic National Automated Clearing House — the mandate authorising automatic EMI debits. |
| **ECS return** | A failed auto-debit — the bank bounced the payment for insufficient funds. The `bounce_velocity` signal. |
| **EMI** | Equated Monthly Instalment — the fixed monthly loan payment. |
| **Flat rate** | Interest charged on the original principal for the full tenure (the Indian vehicle-finance convention), as opposed to reducing balance. |
| **GST / GSTN** | Goods and Services Tax; the network businesses file monthly returns to. |
| **HMAC** | Hash-based Message Authentication Code. A keyed hash — proves authenticity and detects tampering. |
| **KS statistic** | Kolmogorov–Smirnov: the largest separation between the cumulative distributions of good and bad applicants. The traditional credit discrimination metric. |
| **LightGBM** | Microsoft's gradient-boosting framework. The model used here. |
| **LMS** | Loan Management System — services the loan after disbursal (EMIs, balances). |
| **LOS** | Loan Origination System — handles the application through to disbursal. |
| **Mandi** | A regulated agricultural market in India where farmers sell crops. |
| **Monotone constraint** | A hard structural rule forcing a model's response to a feature to move in only one direction. |
| **NO_HIT** | A bureau's answer when it has no record of the person. The trigger condition for this whole system. |
| **NTC / thin file / credit-invisible** | Someone with no or minimal formal credit history. |
| **PD** | Probability of Default — the chance a borrower fails to repay within the horizon. |
| **PDO** | Points to Double the Odds. In this scorecard, 60. |
| **Platt scaling** | Fitting a logistic regression on a model's raw output to turn scores into calibrated probabilities. |
| **Quintal** | 100 kg. The unit mandi crop rates are quoted in. |
| **Shapley value / SHAP** | A game-theoretic attribution of a prediction to its input features, with the guarantee that contributions sum exactly to the prediction. |
| **Scorecard scaling** | The standard conversion from PD to a 300–900 score: `Offset + Factor·ln(odds)`. |
| **Shadow mode** | Running a model on live traffic, recording its outputs, but making no decisions with them — the way to validate before deploying. |
| **UPI** | Unified Payments Interface — India's instant payment system. Visible here as a transaction *mode* inside a bank statement, not as a separate data source. |
| **WABA** | WhatsApp Business Account. |
| **WAL** | Write-Ahead Logging — a SQLite mode where readers don't block writers. |
| **24-hour window** | WhatsApp's rule: free-form replies are allowed for 24 hours after a user messages you; outside it, only approved templates. |

---

*Written against the codebase as it stands. Every metric, feature value, score and trace in this
document was produced by running the code, not estimated. If you change `policy.yaml`'s
`features:` or `ml:` sections and re-run `make train`, the numbers in Parts C and D will move —
`backend/ml/artifacts/report.md` is regenerated on every training run and is always the current
source of truth.*
