# Deploying Snap2Skill on Vercel — the complete guide

Snap2Skill's production UI is **Vercel-native**. This document explains exactly
how it is built, why it is built that way, how to deploy it, and how every
future push redeploys it.

## TL;DR

1. Import `leadforgeagency/skiilll2snap` in Vercel (Add New → Project).
2. Framework preset: **Flask**. Root directory: `./`. No build command changes.
3. Add `GOOGLE_API_KEY` (below) for Production + Preview.
4. Deploy. Every push to `main` redeploys automatically.

Live instance: **https://skiilll2snap.vercel.app**

## Why the project is shaped this way

Vercel serves static files from a CDN and runs **stateless Functions** per HTTP
request — there is no persistent app server and no server-side session. The
product is designed around that from the start:

| Concern | Design |
|---|---|
| UI | Static HTML/CSS/JS in `public/` (single-screen studio) |
| Session state | Browser memory in `public/app.js` |
| Work | One HTTP request per operation (extract / build / validate / repair / sandbox) |
| Entry point | `app.py` — Flask `app` object, auto-detected by Vercel |
| Secrets | Vercel Environment Variables |
| Scaling | CDN + Fluid compute Functions |

The brain and the rules are plain Python modules shared by the API and the
tests: `gemma_client.py` (open-weight Gemma — the only model) and
`skill_builder.py` (deterministic builder + 13-point validator).

## Repository layout (what Vercel sees)

```
app.py                 Flask entry point — Vercel zero-config Flask detection
public/                Static UI, served from the CDN
  index.html           Single-screen studio (Input Hub + 3 studio tabs)
  styles.css           Strict palette: #09090b / #18181b / #27272a / #6366f1 / #fafafa / #a1a1aa
  app.js               Client state machine + API calls
web_service.py         JSON validation + orchestration for serverless calls
gemma_client.py        Gemma extraction + Live Sandbox answers (in-memory image parts)
skill_builder.py       SKILL.md builder, validator, repair, zip packaging
samples.py             Labelled offline samples
requirements.txt       Vercel/production Python dependencies
vercel.json            Framework = flask; api function maxDuration = 300
.python-version        3.12
.vercelignore          Excludes tests and caches from the deployment bundle
```

## Request flow

```
Browser (public/app.js)
  │  JSON + base64 uploads, one request per action
  ▼
Flask routes (app.py)  ──►  web_service.py  ──►  gemma_client.py   (Gemma: extract, sandbox)
                                            └─►  skill_builder.py (build, validate, repair, zip)
  │  JSON response (extraction / flowchart data / SKILL.md / verdict / base64 zip / sandbox answer)
  ▼
Browser renders flowchart + spec, downloads, chats — no server session anywhere
```

Routes: `GET /api/bootstrap`, `POST /api/extract`, `POST /api/build`,
`POST /api/validate`, `POST /api/repair`, `POST /api/sandbox`.

## Platform limits designed into the code

* **4.5 MB function payload** — Flask sets `MAX_CONTENT_LENGTH = 4_500_000`;
  the browser downscales images to ≤1600 px before upload; `web_service.py`
  re-validates every decoded file server-side (≤5 images, ≤3.5 MB each,
  ≤4 MB total).
* **Statelessness** — no files are written, no session is stored. The client
  sends the full extraction with each build/sandbox request.
* **Duration** — `vercel.json` sets `maxDuration: 300` for `app.py`, the
  current Hobby-plan Fluid compute ceiling, so a slow Gemma call is not cut
  off at the old 10-second default.
* **Response size** — if a zip would exceed the response ceiling,
  `/api/build` returns the SKILL.md and verdict and tells the user to download
  the markdown instead of failing silently.

## Environment variables

Set in Vercel → Project → Settings → Environment Variables (Production + Preview):

| Name | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | For live vision + sandbox | Google AI Studio key; called only with Gemma model IDs |
| `GEMMA_MODEL` | No | Defaults to `gemma-4-26b-a4b-it` |

Without the key the deployed app still runs in labelled demo mode: samples,
pasted-text extraction, validation, repair, zip download and the deterministic
sandbox walkthrough all work.

> Changing an environment variable does **not** update already-running
> deployments. Redeploy (Deployments → ⋯ → Redeploy) or push a commit after
> changing one.

## Redeploy behaviour

* **Push to `main`** → Vercel builds a new production deployment automatically
  (Git integration).
* **Pull request / other branch** → preview deployment with its own URL.
* **Same commit, new env vars** → manual Redeploy from the Deployments tab.
* Rollback: Deployments → choose a previous Ready deployment → Promote.

## Local development

```bash
pip install -r requirements.txt
python app.py            # http://127.0.0.1:3000  (same code Vercel runs)
# or: flask --app app run --port 3000
# or with the Vercel CLI: vercel dev
```

## Verification (all passing, no API keys needed)

```bash
python tests/test_skill_builder.py   # deterministic core: builder/validator/zip/repair
python tests/test_web_service.py       # serverless service layer: payloads, limits, sandbox
python tests/test_vercel_app.py        # the exact Flask app Vercel runs: routes + static + API over HTTP
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App loads but badge says "Demo Mode" | `GOOGLE_API_KEY` missing in Vercel | Add it, then Redeploy |
| `413 FUNCTION_PAYLOAD_TOO_LARGE` | Uploads over 4.5 MB total | Use fewer/smaller snaps; the UI downscales automatically |
| Old version still live after env change | Env vars apply to new deployments only | Redeploy |
| Sandbox answers are step walkthroughs | Demo mode (no Gemma key) | Add `GOOGLE_API_KEY`, then Redeploy |
