# Submission text — copy/paste

**Project name:** Snap2Skill

**Tagline:** Snap a photo of know-how, get a validated, reusable Agent Skill.

**What it does:** You photograph know-how where it actually lives — a whiteboard SOP, handwritten steps, a wiki screenshot, a manual page. Open-weight Gemma Vision extracts the procedure (triggers, prerequisites, inputs, ordered steps, tools, constraints, example) under a strict no-invention rule. Deterministic code then builds a SKILL.md in the Agent Skills open standard, runs a 13-point compliance validator on its own output and shows the verdict, and packages the skill + a source-notes audit file as a zip ready to drop into `.agents/skills/`.

**How we built it:** Layered system (see ARCHITECTURE.md), deployed on **Vercel** (live: skiilll2snap.vercel.app): a strict single-screen web studio (static `public/` frontend + Flask Functions in `app.py`; Vercel is stateless so the browser owns the session and every action is one HTTP request) with an Input Hub (snap dropzone, sample sketch, Compile to Skill) and three studio tabs — Visual Flowchart of the detected workflow, the SKILL.md Spec with validator verdict and zip download, and a Live Sandbox where you chat-test the compiled skill; a brain layer on open-weight Gemma (`gemma-4-26b-a4b-it`, 26B, large model, Google AI Studio key — no closed Gemini models, and no other AI provider anywhere in the product) doing vision extraction, unclear-item flagging, and sandbox answers; and a deterministic core (`skill_builder.py`) that builds the SKILL.md, runs a 13-point compliance validator on its own output, auto-repairs broken skills (API: /api/validate + /api/repair), and packages SKILL.md + audit source-notes into one zip. Offline demo mode and three test suites need no keys at all. Snap2Skill itself is also submitted as a compliant Agent Skill (`skills/snap2skill/SKILL.md`).

**Why it matters:** Organisations lose expertise every day to erased whiteboards and retiring experts, and the Agent Skills ecosystem only grows if ordinary people can author skills. Snap2Skill turns any phone into a skill-authoring tool — in any workplace, classroom, clinic, or workshop on Earth.

**Open source:** MIT-licensed public repository. Model: Gemma under the Gemma Terms of Use (https://ai.google.dev/gemma/terms), named in the README with all dependencies.
