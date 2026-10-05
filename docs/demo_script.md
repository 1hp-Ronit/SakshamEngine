# Demo script (~4–5 minutes)

**Before you start** — `make check-whatsapp` is green · `ngrok http 8000` is up and `PUBLIC_BASE_URL` matches · `make demo` is running · text "Hi" to the business
number from your phone (opens the 24 h window) · browser on `http://localhost:8000`, projector mirrored · press **Reset demo**.
*Fallback if WhatsApp fails:* the dashboard's message log shows the failure reason and keeps the consent link (with QR + copy button) — open it on any phone and continue.

## 1 · The problem (20 s)
"Gig workers, farmers and small merchants have real cash flow but no CIBIL score — the bureau returns NO_HIT and they are auto-rejected."

## 2 · Approve path — persona 1 (90 s)
1. Select **1. Ramesh Gupta** → form auto-fills → **Start application**.
2. Status timeline: *Bureau check → NO_HIT*. "Saksham only fires when the bureau has nothing; a score ≥ 700 never reaches us."
3. On your real phone: the consent request arrives on WhatsApp. Tap the link → granular toggles per source, purpose, 6-month validity, 15-minute countdown.
4. **I Authorize.** Under the hood: AA, telecom and business fetched **in parallel** — open **Pipeline trace** to show per-source latency and the total "consent → decision" time. The **Loan summary** tile shows the EMI against estimated income and the dealer's next step.
5. Score gauge animates to ~766 with the 650 cutoff marked; **SHAP waterfall** shows exactly which signals moved the score (in points).
6. Decision card: *Approved*, top reasons with codes, audit record id. LOS handoff + LMS account (mocked).
7. Optionally **Revoke consent (demo)** → features purged, mock data endpoints now return 403.

## 3 · Decline → vernacular plan — persona 2 (60 s)
**New application → 2. Sunil Yadav.** Same flow; amber *Guidance plan sent* (never red). The **Hindi** action plan lands on your phone's WhatsApp: three concrete steps derived from SHAP
reason codes (low buffer, bounces, irregular recharges). Tap *Full plan* to show the mobile page and flip EN / हिं / मरा.
Mention: with no `GEMINI_API_KEY` (or the LLM timing out) the deterministic templates produce the same structure.

## 4 · Resilience (45 s)
- **Persona 7** — "persona 1, but the bank source times out": pipeline trace shows `aa: timeout`, still **Approved** on telecom + GST (missing data is a first-class case).
- **Persona 6** — customer denies consent: *no data is ever requested*.
- (Optional) persona 3 — a farmer with sparse bank data but mandi settlements is approved; persona 4 gets a **Marathi** plan.

## 5 · Graduation ladder (45 s)
Back on an approved application: **Simulate 6 on-time EMIs** — the behaviour score climbs 50 → 80, the tier unlocks (Growth), the limit rises to ₹1,20,000 and used-car becomes available.

## 6 · Close (20 s)
"Hexagonal: swap a mock adapter for the real AA/bureau client and nothing else changes. Same feature code in training and serving, signed revocable consent,
immutable audit trail, config-driven policy. Trained on synthetic data — production starts in shadow mode."
