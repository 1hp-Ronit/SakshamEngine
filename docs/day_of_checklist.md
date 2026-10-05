# Day-of checklist

Written for: you, on the morning of the presentation. Work top to bottom. Each step says what "done" looks like.

## T-60 minutes: services

- [ ] **Token.** Open `.env`, confirm `WHATSAPP_ACCESS_TOKEN` is a System User token (or a temporary one generated in the last hour). Temporary tokens expire in hours.
- [ ] **Tunnel.** Run `ngrok http 8000`. Note the `https://…ngrok-free.dev` URL it prints.
  - If the URL is the same as `PUBLIC_BASE_URL` in `.env`, carry on.
  - If it's different, update `PUBLIC_BASE_URL` in `.env`, and update the webhook callback in Meta (App → WhatsApp → Configuration) to `<new URL>/webhooks/whatsapp`.
- [ ] **Server.** From the repo root, run `make demo`. Done when the log shows `Saksham Engine started` and `curl localhost:8000/health` returns `{"status":"ok"}`.

## T-30 minutes: validation

- [ ] Run `make check-whatsapp`. Done when all four checks pass:
  - the public URL responds
  - WhatsApp credentials authenticate
  - the token has more than 24 hours left (or a note that it's a System User token)
  - Gemini responds
- [ ] Look at the test WhatsApp message on your phone. If it didn't arrive, check the sender number and the template name, then re-run the check.

## T-15 minutes: the WhatsApp window

- [ ] From your phone, text **"Hi"** to **+1 555-669-7571**. This opens the 24-hour window so the consent link goes out as real text, not the generic `hello_world` template.
- [ ] Start one test application with persona 1. Done when the consent link arrives on your phone as a text message. Then press **Reset demo**, which clears the applications but keeps the open window.

## T-5 minutes: the screen

- [ ] Open `http://localhost:8000` in the browser you'll present from. Hard-refresh (Ctrl+Shift+R).
- [ ] Check the **System** menu (top right): WhatsApp shows *live*, the model shows its version, Advisory LLM shows the model name.
- [ ] Check the **Approved loans** toggle under the form. It should be empty after Reset demo, or show only the loans you want to show.
- [ ] Close every other browser tab and app notification.

## During the demo: the path

1. Pick **1. Ramesh Gupta** from the dropdown → **Start application**. Show the bureau NO_HIT on the timeline.
2. Open the consent link on your phone. Show the three toggles and the countdown. Press **I Authorize**.
3. Back on the screen: Score tile, Loan summary, Data sources, then the **Pipeline trace** (open it to show the per-source latency).
4. Open **Why this score** to show the reason codes and the waterfall.
5. Open **Consent & data-rights ledger** to show every read and what we hold.
6. Optional: Persona 9 (Dinesh) for the borderline band, or Persona 2 (Sunil) for the Hindi plan on the phone.

## If something goes wrong

| Symptom | Fix (in order) |
|---|---|
| Consent link arrived as `hello_world` | You're outside the 24-hour window. Text "Hi" again, then start a new application. The link is also on the dashboard with a QR code, so you can still show it. |
| "Awaiting score" never finishes | Check the terminal running `make demo` for errors. A simulated outage ticks for 5 seconds, which is expected. |
| WhatsApp send fails | Run `make check-whatsapp` to see the exact reason. The flow still completes; the link stays in the dashboard. |
| Phone can't open the link | The tunnel changed. Update `PUBLIC_BASE_URL`, restart `make demo`, and rebuild the consent link with a new application. |
| Dashboard is stuck on an old application | Press **New application**, or **Reset demo**. |
| Total failure | Stop everything (`ss -ltnp` to find the PIDs, then `kill`). Restart with the steps above. Fall back to the QR code and the recorded screen capture if you made one. |

## After the demo

- [ ] Press **Reset demo** so the next presenter starts clean.
- [ ] Stop the server and the tunnel if you're finished for the day.
