# Snap2Skill — System Design

Production runs on **Vercel**. One product, one workflow:
*snap → Gemma extracts → deterministic code compiles a compliant SKILL.md →
the user tests it in a Live Sandbox.* (Deployment guide: `VERCEL_DEPLOYMENT.md`.)

```mermaid
flowchart LR
    U[User: whiteboard photo / notebook flowchart / SOP sketch] --> UI[Browser UI — single screen<br/>public/index.html · styles.css · app.js<br/>Input Hub 40% · Studio 60%<br/>owns ALL session state]
    UI -->|JSON + base64, one request per action| FL[Flask entry point<br/>app.py — auto-detected by Vercel<br/>thin routes, 4.5 MB guard]
    FL --> SV[Service layer<br/>web_service.py<br/>schema + size validation, orchestration]
    SV --> BL[Brain layer<br/>gemma_client.py<br/>OPEN-WEIGHT Gemma 4 Vision<br/>extraction + sandbox answers]
    SV --> CORE[Deterministic core<br/>skill_builder.py<br/>build SKILL.md · 13-point validator<br/>Fix-My-Skill repair · zip packager]
    CORE --> SV --> UI
    UI --> ZIP[Skill Zip<br/>SKILL.md + references/source-notes.md]
    ZIP --> AGENTS[Any Agent-Skills agent<br/>Claude Code · Cursor · Copilot · OpenCode]
```

## Design principles
1. **AI proposes, code disposes.** Gemma is the only model, at the edge. Every trust-critical output — the skill file format, its compliance verdict, the zip layout — is produced by deterministic code that can be unit-tested with no API key (`tests/`).
2. **Stateless by platform design.** No server session, no disk writes, no in-memory user state. The browser sends the full extraction with each build request, so cold starts, scale-out and redeploys cannot corrupt a session.
3. **Fail soft, never fail closed.** No Google key → labelled demo mode completes (sample + pasted-text extraction, deterministic sandbox walkthrough). A provider outage cannot kill the demo.
4. **Honesty is a feature, enforced in prompts + code.** Gemma must flag unclear source content in `unclear_items` instead of inventing steps; the flowchart surfaces those flags; the sandbox prompt forbids the answering agent from using knowledge outside the skill.
5. **One builder, everywhere.** The studio UI, the Fix-My-Skill repair endpoints, and Snap2Skill's own shipped skill all go through the same `build_skill_md()` / `validate_skill_md()` — there is no second, weaker code path for generated output.
6. **Respect the platform's physics.** Vercel's 4.5 MB payload ceiling is enforced three times: the browser downscales images before upload, Flask caps request size, and `web_service.py` re-validates every decoded file. Function duration is set to 300s in `vercel.json` for slow model calls.

## Layers & files
| Layer | File(s) | Responsibility | External dependency |
|---|---|---|---|
| Presentation | `public/index.html`, `public/styles.css`, `public/app.js` | Single-screen studio: Input Hub (dropzone, sample, compile state machine) + Studio tabs (Visual Flowchart, SKILL.md Spec, Live Sandbox). Strict palette: zinc-950/900/800 + indigo-500 + white/zinc-400. Browser-owned state, image downscaling | none (static CDN) |
| HTTP | `app.py` | Flask routes for the UI and the JSON API; serves only `public/` as static | Flask |
| Service | `web_service.py` | Payload cleaning, base64 decode + size limits, orchestration, JSON-safe results | none |
| Brain | `gemma_client.py` | Vision extraction (multi-snap ≤5, in-memory image parts), sandbox answers as the skill, demo fallbacks | Gemma via Gemini API (Gemma IDs only) |
| Core | `skill_builder.py` | slugify, SKILL.md builder, 13-point validator, repair, zip | none (pure Python) |
| Data | `samples.py` | Labelled offline sample extractions | none |

## API summary
`GET /api/bootstrap` (status + samples) · `POST /api/extract` · `POST /api/build` ·
`POST /api/validate` · `POST /api/repair` · `POST /api/sandbox`.
Details and limits: `VERCEL_DEPLOYMENT.md`.

## Scaling note
The core is UI- and platform-independent: `skill_builder` + `gemma_client` are
called unchanged by the Flask API and the test-suite. Model IDs are
environment-configured, so Gemma can be swapped (e.g. via Ollama locally)
without touching the core.
