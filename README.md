# 📸 Snap2Skill

**Snap a photo of know-how. Get a reusable Agent Skill.**

The world's expertise is trapped where AI agents can't use it: on whiteboards, in handwritten notebooks, in screenshots of wikis, on taped-up SOP sheets above machines. Writing an Agent Skill by hand is slow and most people don't know the format — so that knowledge never becomes reusable.

**Snap2Skill fixes that in 30 seconds:** take a snap → open-weight **Gemma Vision** reads it and extracts the procedure → deterministic code builds a `SKILL.md` that **provably complies** with the Agent Skills open standard, validates it check-by-check, and hands you a zip you can drop into any project.

**New in v2 — full voice workflow (ElevenLabs):** the expert can *talk* while they snap (ElevenLabs **Scribe** transcribes their voice note in 90+ languages and Gemma uses the transcript), you **edit the steps before export**, the finished skill is **narrated aloud** — optionally in the **expert's own cloned voice** (Creator-plan Professional/Instant Cloning, consent-gated) and in **7 narration languages** (Gemma translates, ElevenLabs speaks) — the MP3 is bundled inside the skill zip, and a **hands-free walkthrough mode** reads the skill back step-by-step for kitchens, workshops, and labs. Plus **Fix-My-Skill**: paste any broken `SKILL.md` and the validator + auto-repair make it compliant. Full design: `ARCHITECTURE.md`.

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
  references/voice-transcript.txt ← expert's voice note, if one was used (Scribe)
  audio/guide.mp3             ← the skill, narrated (ElevenLabs, expert clone if set)
  audio/narration.txt         ← the exact narration script
```

**Just add your keys and deploy** — the production web app is **Vercel-native** (static UI in `public/` + Flask Functions in `app.py`; full guide in `VERCEL_DEPLOYMENT.md`):

```bash
GOOGLE_API_KEY=...        # Vercel env var — Google AI Studio, used ONLY for open-weight Gemma
ELEVENLABS_API_KEY=...    # optional Vercel env var — enables the whole voice layer
```

The web UI shows a live status panel (key configured / not configured — never the key itself). Every ElevenLabs feature fails soft: no key or an API error disables voice only, never the core pipeline. Without any keys the deployed app still runs in labelled demo mode.

Drop the folder into `.agents/skills/` (or your agent's skills directory) and any compatible agent — Claude Code, Cursor, Copilot, OpenCode and others that read the open standard — can run that know-how forever.

## Open-source / open-weight AI — challenge compliance

| Requirement | This project |
|---|---|
| Open-weight AI is core | **Gemma Vision** performs the reading/extraction for every snap; without it there is no product |
| Model named + terms | **Primary: `gemma-4-26b-a4b-it`** — Gemma 4, 26B params (**large model, >10B**), text + image input, open weights under the **Gemma Terms of Use**: https://ai.google.dev/gemma/terms · Fallbacks in code: `gemma-4-31b-it`, `gemma-3-27b-it`, `gemma-3-12b-it` |
| Access | Google AI Studio API key via the Gemini API (`GOOGLE_API_KEY`). **No closed Gemini model is ever called** — model IDs in `gemma_client.py` are Gemma only |
| Voice integration | ElevenLabs is integrated as an **optional voice layer** (Scribe STT in, TTS + voice cloning out) via `ELEVENLABS_API_KEY`. It is never the reasoning/extraction engine — Gemma is — and the app runs fully without it. Voice cloning is consent-gated in the UI |
| Public repo + licence | This repository, **MIT** (`LICENSE`) |
| Agent Skill standard | Every generated skill + this project's own skill pass `validate_skill_md()`; format = YAML frontmatter (`name`, `description`, `license`, `metadata`) + markdown body |
| Substantial work | Vision extraction schema with honesty rules, deterministic SKILL.md builder, 13-point validator, zip packaging, offline demo mode, tests |

**Dependencies (production/Vercel):** Python, Flask, `google-genai` (Apache-2.0), `elevenlabs` SDK, `python-dotenv`, requests. The optional legacy Streamlit UI lives in `streamlit_app.py` with its own `requirements-streamlit.txt`.

## Deploy it (Vercel)

Import this repository in Vercel → Framework: **Flask**, root `./` → add `GOOGLE_API_KEY` (and optionally `ELEVENLABS_API_KEY`) → Deploy. Every push to `main` redeploys automatically. Step-by-step, limits, and troubleshooting: **`VERCEL_DEPLOYMENT.md`**.

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
