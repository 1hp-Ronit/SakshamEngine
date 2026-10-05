# Saksham Engine

> **Alternative credit for the credit-invisible — a consent-based safety net that sits *beside* the bureau check.**
> Built for TVS Credit e.p.i.c Season 8.

When the bureau returns **NO_HIT**, Saksham asks the applicant — on WhatsApp — for granular, revocable consent, reads
alternative data (bank statement incl. UPI, telecom recharges, GST / mandi records) **in parallel**, produces an explainable
**300–900 score**, and either approves into the existing loan flow or sends a plain-language improvement plan in **Hindi / Marathi / English**.

> ⚠️ **Prototype trained on synthetic data. Not for production use.** A real rollout would start in shadow mode on real repayment outcomes.
> The bureau, Account Aggregator, telecom, GST/mandi feeds, LOS, LMS and e-NACH are **mocked** behind adapter interfaces.
> WhatsApp (Meta Cloud API) and the LLM (Gemini) are **real integrations** with automatic fallbacks.

---

## Quick start

Requires Python 3.11, Node 20+, `make`. (LightGBM/SHAP wheels are not yet reliable on newer Pythons.)

```bash
cp .env.example .env          # set SECRET_KEY (any long random string); everything else works offline as-is
make install                  # backend venv + frontend deps
make build-demo               # builds the frontend (model artifacts are committed; trains only if missing)
make demo                     # single origin on http://localhost:8000  — dealer UI, consent page, API, mocks
```

Development with hot reload: `make dev` (backend `:8000`, Vite `:5173` proxying the API).

Open <http://localhost:8000>, pick **persona 1** and press **Start application**. Open the consent link on your phone (it arrives on WhatsApp; the dashboard also shows a QR code and a copy button), authorise, and watch the pipeline.

| Command | What it does |
|---|---|
| `make dev` | backend + frontend with hot reload |
| `make demo` | single-origin server (backend serves `frontend/dist`) |
| `make build-demo` | install, train if artifacts are missing, build the frontend |
| `make train` | regenerate synthetic data, train, calibrate, write `ml/artifacts/` + `report.md` (~2 min) |
| `make test` | 110 tests (`make test ARGS='-k e2e'`) |
| `make seed` / `make reset` | wipe the SQLite DB (or press **Reset demo** in the UI) |
| `make check-whatsapp` | validate WhatsApp + Gemini credentials, public URL, send a test message (`ARGS=--no-send` to skip sending) |

**Fully offline:** `MESSAGING_MODE=simulated LLM_FALLBACK_ONLY=true make demo` — every feature works; messages are listed in the dashboard's message log (with the consent link / QR so you can open it yourself) and
action plans come from the deterministic templates. (Fonts load from Google Fonts when online and fall back to system fonts otherwise.)

---

## Making it work on a real phone (WhatsApp + tunnel)

1. **Tunnel** — the consent link must open on a phone, so it can never be `localhost`:
   ```bash
   ngrok http 8000            # then set PUBLIC_BASE_URL=https://<your-subdomain>.ngrok-free.app in .env
   ```
   (Run `make demo` so the backend serves the built UI on that single origin.)
2. **WhatsApp credentials** in `.env`: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `DEMO_RECIPIENT_NUMBER` (a number verified in Meta's
   *API setup → To* list), `MESSAGING_MODE=both`. Personas have fake numbers, so real sends are **redirected to `DEMO_RECIPIENT_NUMBER`**.
3. **Webhook** (delivery ticks + the 24 h window): in the Meta app → WhatsApp → Configuration, set the callback URL to
   `https://<tunnel>/webhooks/whatsapp` and the verify token to `WHATSAPP_VERIFY_TOKEN`; subscribe to **messages**.
4. `make check-whatsapp` — validates the token, sends the pre-approved `hello_world` template, checks the tunnel and Gemini.

**How messages are delivered** (Meta only allows business-initiated *templates* outside a 24 h window):

| Situation | What goes out for real |
|---|---|
| Consent request, window closed | the pre-approved template (`WHATSAPP_CONSENT_TEMPLATE`, default `hello_world`) |
| Consent request, window **open** | free text **with the actual consent link** |
| Decision / action plan, window open | free-form text (full plan, Devanagari OK) |
| Decision, window closed | `WHATSAPP_STATUS_TEMPLATE` if configured, else logged only (not sent) |
| Real send fails (token, network, window) | marked `failed_real_send` with the reason; the flow continues and the consent link stays available in the message log |

> **Demo tip:** text "Hi" to the business number from your phone once before presenting. That opens the 24 h window for your number, so even the
> consent link arrives as a real WhatsApp message. (**Reset demo** keeps this window record.) The consent page also has a *Continue on WhatsApp* `wa.me` button that opens it, and any held-back
> result is delivered the moment your inbound message arrives. The dashboard also shows a **QR code** of the consent URL.

The **outbox is always written**, whatever the mode — it feeds the dashboard's message log (delivery status, message text, consent link + QR) and is the automatic fallback.
When your own templates (`saksham_consent_request`, `saksham_status_update`) are approved, set `WHATSAPP_CONSENT_TEMPLATE*` / `WHATSAPP_STATUS_TEMPLATE*`
in `.env` — no code change.

---

## Configuration — nothing business-relevant is hard-coded

| File | Controls |
|---|---|
| [`policy.yaml`](policy.yaml) | bureau bypass threshold, approval cutoff, borderline band (on/off, floor, ticket factor), min sources, scorecard (PDO, anchor score/PD or explicit offset), per-source timeout, session & consent TTL, **product catalog** (ticket, tenure, EMI or flat-rate formula), graduation **ladder** tiers/limits/deltas, supported languages, advisory guardrails, mock anchor date, feature constants, synthetic-data generator knobs |
| [`reason_codes.yaml`](reason_codes.yaml) | feature → reason code, English/Hindi/Marathi explanation text and **action templates**, all applicant-facing message templates |
| [`personas.yaml`](personas.yaml) | the 13 demo personas (profile, bureau result, language, outage flag, expected outcome) — add or edit entries freely; the dropdown and the tests pick them up |
| `.env` | secrets and deployment (see below) |

Restart after editing. Changing the `features:` section of `policy.yaml` changes model inputs → run `make train` (a startup warning tells you).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | *(dev value)* | HMAC for consent signatures and PAN/Aadhaar/mobile tokenisation — **change it** |
| `DATABASE_URL` | `sqlite+aiosqlite:///…/data/saksham.db` | SQLAlchemy URL |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | origin used for consent/plan links — must be reachable from a phone |
| `MOCK_SERVICES_BASE_URL` | `http://localhost:8000` | where the backend calls its own `/mock/*` vendors |
| `MESSAGING_MODE` | `simulated` | `simulated` · `whatsapp` · `both` (outbox is always written) |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_VERSION` | – / – / `v25.0` | Graph API (version is never hard-coded) |
| `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | `saksham-verify-token` / – | webhook challenge; optional `X-Hub-Signature-256` verification |
| `DEMO_RECIPIENT_NUMBER` | – | real sends are redirected here |
| `WHATSAPP_BUSINESS_NUMBER` | – | digits for the consent page's `wa.me` deep link |
| `WHATSAPP_CONSENT_TEMPLATE[_LANG/_PARAMS]`, `WHATSAPP_STATUS_TEMPLATE[_LANG/_PARAMS]` | `hello_world` / `en_US` | template names, language (`auto` → en/hi/mr) and body variables (`name,url`) |
| `GEMINI_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS` | – / `gemini-3.5-flash-lite` / `6` | advisory LLM (provider-agnostic `LLMClient`) |
| `LLM_FALLBACK_ONLY` | `false` | never call the LLM; deterministic templates only |

Secrets are only ever read from the environment, masked in logs/errors/config dumps, and never sent to the browser (`/demo/config` is secret-free).

---

## Demo personas

| # | Persona | Data profile | Outcome | Score (approx.) |
|---|---|---|---|---|
| 1 | Ramesh — small-town merchant | steady UPI/bank inflows, GST filings, regular recharges | `APPROVED` | ~766 |
| 2 | Sunil — gig rider (Hindi) | UPI-heavy, irregular inflows, low buffer, bounces, no business records | `DECLINED_WITH_PLAN` | ~551 |
| 3 | Mohan — farmer (Marathi) | regular mandi settlements, steady recharges, sparse bank data | `APPROVED` | ~783 |
| 4 | Sanjay — struggling farmer (Marathi) | few receipts, long settlement delays, recharge gaps | `DECLINED_WITH_PLAN` | ~325 |
| 5 | Anita — prime salaried | bureau HIT 760 | `BYPASSED_TO_LOS` | – |
| 6 | Vikram — consent denier | NO_HIT, denies consent | `CONSENT_DENIED` (no data requested) | – |
| 7 | Ramesh again, **AA outage** | persona 1 with the bank source timing out | `APPROVED` on the remaining sources | ~746 |
| 8 | Ananya — salon owner | UPI-first takings, no GST registration | `APPROVED` on bank + telecom alone | ~753 |
| 9 | Dinesh — auto-rickshaw driver (Hindi) | cash-heavy, irregular earnings, late recharges | `CONDITIONAL_APPROVAL` (smaller ticket) | ~621 |
| 10 | Lakshmi — dairy farmer (Marathi) | no bank account in her name | `CONDITIONAL_APPROVAL` on telecom + business only | ~633 |
| 11 | Kiran — tractor applicant | bank and telecom feeds both time out | `INSUFFICIENT_DATA` → manual review | – |
| 12 | Priya — first-time salaried borrower | steady salary credit, no bureau history | `APPROVED` | ~681 |
| 13 | Suresh — bureau score 590 (Marathi) | existing bureau record below the 700 bypass | `BYPASSED_TO_LOS` (Saksham not used) | – |

Scores are deterministic (same seed → same payloads → same score) and independent of `SECRET_KEY`. All thirteen are asserted in `tests/test_e2e_personas.py`.

---

## Architecture (hexagonal / ports-and-adapters)

```mermaid
graph LR
  UI[Dealer console · Under the hood<br/>Consent & Plan pages (opened on the customer's real phone)] -->|REST, 2s polling| API
  subgraph FastAPI single process
    API --> ORCH[Orchestrator + state machine]
    ORCH --> FEAT[build_features — ONE code path]
    FEAT --> MODEL[LightGBM + Platt + scorecard]
    MODEL --> SHAP[SHAP → reason codes]
    SHAP --> ADV[Advisory: Gemini → deterministic fallback]
    ORCH -- ports --> BUR[BureauAdapter] & SRC[DataSourceAdapter ×3] & LOS[LOSAdapter] & LMS[LMSAdapter] & MSG[MessagingProvider]
    BUR & SRC -->|HTTP| MOCK[/mock/* — consent enforced/]
    MOCK --> GEN[shared raw-payload generators]
  end
  GEN -. same generators .-> TRAIN[ml/generate_data → ml/train]
  MSG --> WA[WhatsApp Cloud API] & OUT[(outbox → dashboard message log)]
  ADV --> LLM[Gemini API]
  ORCH --> DB[(SQLite)]
```

Key decisions: **no Redis** (sessions are DB rows with a lazily-enforced TTL), **no Celery** (`asyncio.gather` with a per-source timeout and graceful degradation),
mocks are routers **in the same app** called over HTTP, one origin serves everything (one tunnel). See [`docs/architecture.md`](docs/architecture.md).

**Train/serve parity.** One generator module produces raw AA / telecom / GST / mandi payloads for *both* the `/mock/*` services and the training set; training rows are built by
running those payloads through the **same** `build_features()` used at inference. `tests/test_feature_parity.py` proves identical payloads give identical vectors in both paths
(serving path goes over real HTTP with consent enforced).

**Model** (`make train` → `backend/ml/artifacts/report.md`): LightGBM with monotone constraints, Platt calibration, scorecard `Score = Offset + Factor·ln((1−PD)/PD)`,
PDO 60, **650 ↔ 7 % PD** (offset derived from the anchor, not hard-coded). Test AUC ≈ 0.81 overall and 0.78–0.83 per segment on synthetic data.

**Privacy & audit.** PAN/Aadhaar stored only as HMAC tokens; raw vendor payloads are discarded after feature extraction (only the feature vector + hash is kept);
revoking consent purges the stored vector and blocks all future access. Every decision writes an insert-only audit record (model version, policy version, consent id,
feature hash, score, PD, SHAP drivers). The contact number is retained because the messaging channel needs it. Vendors are addressed by a stable pseudonymous `vendor_ref`, so rotating `SECRET_KEY` never changes persona data.

---

## Repository layout

```
policy.yaml  reason_codes.yaml  personas.yaml  .env.example  Makefile
backend/app/{api,core,domain,models,adapters,services,mock_services}   backend/ml/{generate_data,train}.py   backend/tests/
frontend/src/components/{DealerPOS,Messages,UnderTheHood,ConsentPage,PlanPage}
scripts/check_whatsapp.py   docs/{architecture,demo_script}.md
```

## Branding

All brand assets live in [`frontend/public/brand/`](frontend/public/brand/) (**not** `frontend/dist/`, which is wiped on every build):

| File | Used for |
|---|---|
| `saksham-logo.svg` | Saksham Engine logo (header, hero, favicon). Drawn through a CSS mask, so it takes the surrounding text colour |
| `tvs-credit.png` | Official TVS Credit logo (transparent background; shown on a white chip in the header and footers so it stays legible on the dark UI) |
| `hero-bg.mp4` + `hero-poster.jpg` | Looping muted background video for every hero card, the score tile and the plan page's closing card (`VideoBg` component). The poster frame is shown while loading or when the OS asks for reduced motion |

Replace a file (same name) to rebrand; the components are in `frontend/src/components/{Brand,VideoBg}.tsx`. The UI is dark-themed around the hero video; colours are design tokens at the top of `frontend/src/styles/index.css`.

## Tech stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy (async) · aiosqlite |
| **ML** | LightGBM · Platt calibration · SHAP · scikit-learn · pandas / numpy |
| **Frontend** | React 19 · TypeScript · Vite · Tailwind CSS v4 · Recharts · react-router-dom |
| **Messaging** | Meta WhatsApp Cloud API (Graph API v25.0) |
| **Advisory LLM** | Google Gemini (provider-agnostic `LLMClient`; falls back to deterministic templates) |
| **Database** | SQLite (dev/demo) — swap via `DATABASE_URL` |
| **Infra** | Single-process; no Redis, no Celery; ngrok for public tunnel |

---

## Testing

```bash
make test                      # all 110+ tests
make test ARGS='-k e2e'        # end-to-end persona suite only
make test ARGS='-k parity'     # feature-parity (train ↔ serve) only
```

| Test file | What it covers |
|---|---|
| `test_e2e_personas.py` | All 13 personas — deterministic score + outcome assertions (full pipeline over real HTTP with consent enforced) |
| `test_feature_parity.py` | Proves identical raw payloads give identical feature vectors via `build_features()` in both the training path and the serving path |
| `test_feature_pipeline.py` | Unit-level tests for every feature extraction function (AA/bank, telecom, GST/mandi) |
| `test_scorecard.py` | Scorecard formula (PDO, offset, factor), monotone constraints, calibration |
| `test_advisory.py` | Advisory LLM client — Gemini integration, deterministic fallback, language routing |
| `test_consent.py` | Consent lifecycle — grant, revoke, expiry, signature verification |
| `test_messaging.py` | MessagingProvider routing, outbox writes, template selection, 24 h window logic |
| `test_withdrawal.py` | Data withdrawal purges feature vector and blocks future fetches |
| `test_ledger.py` | Audit record correctness — model version, policy version, SHAP drivers, hash |
| `test_generators.py` | Raw payload generators produce valid, schema-conforming outputs |

Tests are fully self-contained (in-memory DB, mocked HTTP). No WhatsApp or Gemini credentials are required.

---

## Documentation

| File | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Design decisions, hexagonal architecture, port/adapter boundaries, sequence diagrams |
| [`docs/demo_script.md`](docs/demo_script.md) | Presenter script — step-by-step walkthrough of the live demo for the judges panel |
| [`docs/day_of_checklist.md`](docs/day_of_checklist.md) | Pre-demo checklist (credentials, tunnel, templates, reset) |
| [`docs/EXPLAINER.md`](docs/EXPLAINER.md) | Deep-dive explainer — model rationale, feature engineering, privacy design, policy knobs |
| [`docs/Saksham_Engine_Presentation.pptx`](docs/Saksham_Engine_Presentation.pptx) | Slide deck for the hackathon presentation |
| [`backend/ml/artifacts/report.md`](backend/ml/artifacts/report.md) | Auto-generated model report — AUC, calibration, feature importance, segment breakdown (regenerated by `make train`) |
| [`implementation_plan.md`](implementation_plan.md) | Original implementation plan and phased build log |
| [`spec.md`](spec.md) | Full functional specification |

---

## Known limitations

- Synthetic data only; the synthetic default process is simple, so scores saturate near the extremes for very clean profiles.
- Only the pre-approved `hello_world` template is assumed until your own templates are approved (see above).
- The mock services share the app's database to verify consent; a real vendor would verify a consent handle with the AA.
- The plan page (`/plan/{id}`) and consent page (`/consent/{id}`) are routes of the built SPA, so they need `make build-demo` (or the Vite dev server) to be reachable.

---

## Contributing

This is a hackathon prototype. If you want to extend it:

1. **Fork** the repo and create a feature branch (`git checkout -b feature/my-feature`).
2. **Install** with `make install`.
3. **Run tests** before and after your change: `make test`.
4. Keep `policy.yaml` / `reason_codes.yaml` as the single source of truth for thresholds and copy — avoid hard-coding business logic in Python.
5. If you change the `features:` block in `policy.yaml`, regenerate artifacts: `make train`.
6. Open a pull request with a description of what changed and why.

---

## License

This project was created for **TVS Credit e.p.i.c Season 8** and is released for evaluation and educational purposes.
All bureau, Account Aggregator, telecom, GST/mandi, LOS, LMS, and e-NACH integrations are **mocked**.
The WhatsApp and Gemini integrations are real — use your own credentials and comply with Meta's and Google's terms of service.
