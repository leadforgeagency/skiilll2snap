# 📸 Snap2Skill

**Snap a photo of know-how. Get a reusable Agent Skill.**

The world's expertise is trapped where AI agents can't use it: on whiteboards, in handwritten notebooks, in screenshots of wikis, on taped-up SOP sheets above machines. Writing an Agent Skill by hand is slow and most people don't know the format — so that knowledge never becomes reusable.

**Snap2Skill fixes that in 30 seconds:** take a snap → open-weight **Gemma Vision** reads it and extracts the procedure → deterministic code builds a `SKILL.md` that **provably complies** with the Agent Skills open standard, validates it check-by-check, and hands you a zip you can drop into any project.

**The studio:** a strict single-screen developer UI — input hub on the left (dropzone, sample sketch, glowing **Compile to Skill**), studio on the right with three tabs: **📊 Visual Flowchart** (the detected workflow as connected nodes), **📄 SKILL.md Spec** (the generated file, validator verdict, one-click copy, zip download), and a **🚀 Live Sandbox** where you chat-test the compiled skill — Gemma answers *as* the skill, following only its steps. The API also keeps **Fix-My-Skill** (`/api/validate` + `/api/repair`) for repairing hand-written skills. Full design: `ARCHITECTURE.md`.

Built for the **Hacktoberfest Hack Day — Open-Source AI Prize Challenge (Best Open-Source AI Project)**.

## Why this is not "just another AI generator"

1. **AI reads, code proves.** Gemma extracts; `skill_builder.py` builds the file and runs a 13-point compliance validator (frontmatter, kebab-case name = folder name, license, required sections, numbered workflow, no placeholders). The validator's verdict is shown in the UI for every generation — and it can validate *any* skill, including hand-written ones.
2. **Honesty rule.** The extraction prompt forbids inventing steps: anything not visible in the snap is marked unclear, never hallucinated. A skill that invents a machine-safety step or a coffee ratio is worse than no skill.
3. **It eats its own cooking.** Snap2Skill itself ships as a compliant Agent Skill: `skills/snap2skill/SKILL.md`.

## What you can snap

Whiteboard SOPs · handwritten lab / workshop steps · screenshots of team wikis and checklists · manual and appliance pages · recipes · onboarding instructions · a senior worker's notebook before they retire.

Output structure:

```
<skill-name>/
  SKILL.md                    ← validated, Agent Skills open standard
  references/source-notes.md  ← what Gemma actually saw (audit trail)
```

**Just add your key and deploy** — the production web app is **Vercel-native** (static UI in `public/` + Flask Functions in `app.py`; full guide in `VERCEL_DEPLOYMENT.md`):

```bash
GOOGLE_API_KEY=...        # Vercel env var — Google AI Studio, used ONLY for open-weight Gemma
```

The header badge shows the live mode honestly (⚡ Gemma 4 Active vs Demo Mode — never the key itself). Without a key the deployed app still runs in labelled demo mode: samples and pasted text compile through the deterministic demo extractor, and the sandbox answers with a step walkthrough.

Drop the folder into `.agents/skills/` (or your agent's skills directory) and any compatible agent — Claude Code, Cursor, Copilot, OpenCode and others that read the open standard — can run that know-how forever.

## Open-source / open-weight AI — challenge compliance

| Requirement | This project |
|---|---|
| Open-weight AI is core | **Gemma Vision** performs the reading/extraction for every snap; without it there is no product |
| Model named + terms | **Primary: `gemma-4-26b-a4b-it`** — Gemma 4, 26B params (**large model, >10B**), text + image input, open weights under the **Gemma Terms of Use**: https://ai.google.dev/gemma/terms · Fallbacks in code: `gemma-4-31b-it`, `gemma-3-27b-it`, `gemma-3-12b-it` |
| Access | Google AI Studio API key via the Gemini API (`GOOGLE_API_KEY`). **No closed Gemini model is ever called** — model IDs in `gemma_client.py` are Gemma only |
| Public repo + licence | This repository, **MIT** (`LICENSE`) |
| Agent Skill standard | Every generated skill + this project's own skill pass `validate_skill_md()`; format = YAML frontmatter (`name`, `description`, `license`, `metadata`) + markdown body |
| Substantial work | Vision extraction schema with honesty rules, deterministic SKILL.md builder, 13-point validator, zip packaging, offline demo mode, tests |

**Dependencies (production/Vercel):** Python, Flask, `google-genai` (Apache-2.0), `python-dotenv`, requests. No other AI provider is involved — Gemma is the only model.

## Deploy it (Vercel)

Import this repository in Vercel → Framework: **Flask**, root `./` → add `GOOGLE_API_KEY` → Deploy. Every push to `main` redeploys automatically. Step-by-step, limits, and troubleshooting: **`VERCEL_DEPLOYMENT.md`**.

## Run it locally

```bash
git clone <your-repo-url>
cd snap2skill
pip install -r requirements.txt
cp .env.example .env   # add your Google AI Studio key
python app.py          # the same Flask app Vercel runs → http://127.0.0.1:3000
```

No key / no Wi-Fi? Load a built-in sample extraction, or paste steps as text — demo mode still builds, validates, and zips a real skill offline.

## Tests

```bash
python tests/test_skill_builder.py   # deterministic core, no API key needed
python tests/test_web_service.py       # serverless service layer
python tests/test_vercel_app.py        # the exact Flask app Vercel runs, over HTTP
```

## Limitations, honestly

- A blurry snap produces a weaker skill; unclear steps are flagged in the output rather than guessed.
- Generated skills should be read once by the human expert before an agent runs them on anything safety-critical — the source-notes audit file exists for exactly that check.

## Licence

Code: MIT (`LICENSE`). Model: Gemma, under the Gemma Terms of Use linked above; no model weights are redistributed.
