# Deploying Snap2Skill on Vercel — the complete guide

Snap2Skill's production UI is **Vercel-native**. This document explains exactly
how it is built, why it is built that way, how to deploy it, and how every
future push redeploys it.

## TL;DR

1. Import `leadforgeagency/skiilll2snap` in Vercel (Add New → Project).
2. Framework preset: **Flask**. Root directory: `./`. No build command changes.
3. Add environment variables (below) for Production + Preview.
4. Deploy. Every push to `main` redeploys automatically.

## Why the project is shaped this way

The first Snap2Skill interface was Streamlit. Streamlit assumes a **persistent
Python process** holding a live session for each visitor. Vercel does not run
persistent app servers: it serves static files from a CDN and runs **stateless
Functions** per HTTP request. Pointing a Streamlit app at Vercel therefore
cannot work reliably.

So the product was re-architected — without changing its brain or its rules:

| Concern | Streamlit edition | Vercel edition (production) |
|---|---|---|
| UI | Python widgets in `streamlit_app.py` | Static HTML/CSS/JS in `public/` |
| Session state | Server memory (`st.session_state`) | Browser memory in `public/app.js` |
| Work | One long-lived process | One HTTP request per operation |
| Entry point | `streamlit run` | `app.py` — Flask `app` object, auto-detected by Vercel |
| Secrets | local `.env` | Vercel Environment Variables |
| Scaling | One process | CDN + Fluid compute Functions |

Everything that makes Snap2Skill trustworthy stayed identical: `gemma_client.py`
(open-weight Gemma), `voice.py` (ElevenLabs), and `skill_builder.py`
(deterministic builder + 13-point validator) are shared by both interfaces.

## Repository layout (what Vercel sees)

```
app.py                 Flask entry point — Vercel zero-config Flask detection
public/                Static UI, served from the CDN
  index.html           Page structure + full product/architecture detail
  styles.css           Design system (dark, responsive, accessible)
  app.js               All client state + API calls
web_service.py         JSON validation + orchestration for serverless calls
gemma_client.py        Gemma extraction / translation (in-memory image parts)
voice.py               ElevenLabs Scribe / TTS / cloning (optional, fails soft)
skill_builder.py       SKILL.md builder, validator, repair, zip packaging
samples.py             Labelled offline samples
requirements.txt       Vercel/production Python dependencies (no Streamlit)
vercel.json            Framework = flask; api function maxDuration = 300
.python-version        3.12
.vercelignore          Excludes tests, the legacy Streamlit app and caches
streamlit_app.py       Optional legacy local UI (requirements-streamlit.txt)
```

## Request flow

```
Browser (public/app.js)
  │  JSON + base64 uploads, one request per action
  ▼
Flask routes (app.py)  ──►  web_service.py  ──►  gemma_client.py  (Gemma)
                                            ├─►  voice.py         (ElevenLabs)
                                            └─►  skill_builder.py (validate + zip)
  │  JSON response (extraction / SKILL.md / verdict / base64 zip or audio)
  ▼
Browser renders, edits, previews, downloads — no server session anywhere
```

Routes: `GET /api/bootstrap`, `POST /api/extract`, `POST /api/build`,
`POST /api/validate`, `POST /api/repair`, `POST /api/narrate`,
`POST /api/speak`, `POST /api/clone`.

## Platform limits designed into the code

* **4.5 MB function payload** — Flask sets `MAX_CONTENT_LENGTH = 4_500_000`;
  the browser downscales images to ≤1600 px before upload; `web_service.py`
  re-validates every decoded file server-side (≤5 images, ≤3.5 MB each,
  ≤4 MB total).
* **Statelessness** — no files are written, no session is stored. The editor
  sends the full extraction with each build request.
* **Duration** — `vercel.json` sets `maxDuration: 300` for `app.py`, the
  current Hobby-plan Fluid compute ceiling, so a slow Gemma call is not cut
  off at the old 10-second default.
* **Response size** — if a narrated zip would exceed the response ceiling,
  `/api/build` returns the SKILL.md and verdict and tells the user to download
  the markdown or shorten narration instead of failing silently.
* **Bundle size** — Streamlit and Pillow were removed from the production
  `requirements.txt`; the legacy UI has its own `requirements-streamlit.txt`.

## Environment variables

Set in Vercel → Project → Settings → Environment Variables (Production + Preview):

| Name | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | For live vision | Google AI Studio key; called only with Gemma model IDs |
| `GEMMA_MODEL` | No | Defaults to `gemma-4-26b-a4b-it` |
| `ELEVENLABS_API_KEY` | No | Enables Scribe, narration and cloning |
| `ELEVENLABS_VOICE_ID` | No | Default/pre-created Professional Clone voice |

Without any keys the deployed app still runs in labelled demo mode: samples,
pasted-text extraction, validation, repair and zip download all work.

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

# Legacy local Streamlit edition (optional):
pip install -r requirements-streamlit.txt
streamlit run streamlit_app.py
```

## Verification (all passing, no API keys needed)

```bash
python tests/test_skill_builder.py   # deterministic core: builder/validator/zip/repair
python tests/test_web_service.py       # serverless service layer: payloads, limits, fail-soft voice
python tests/test_vercel_app.py        # the exact Flask app Vercel runs: routes + static + API over HTTP
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App loads but says "Demo mode" | `GOOGLE_API_KEY` missing in Vercel | Add it, then Redeploy |
| Voice buttons warn "not configured" | `ELEVENLABS_API_KEY` missing | Add it, then Redeploy |
| `413 FUNCTION_PAYLOAD_TOO_LARGE` | Uploads over 4.5 MB total | Use fewer/smaller snaps; the UI downscales automatically |
| Old version still live after env change | Env vars apply to new deployments only | Redeploy |
| Build picks Streamlit | An old commit is being deployed | Ensure the latest `main` (with Flask `app.py`) is deployed |
