# Submission text — copy/paste

**Project name:** Snap2Skill

**Tagline:** Snap a photo of know-how, get a validated, reusable Agent Skill.

**What it does:** You photograph know-how where it actually lives — a whiteboard SOP, handwritten steps, a wiki screenshot, a manual page. Open-weight Gemma Vision extracts the procedure (triggers, prerequisites, inputs, ordered steps, tools, constraints, example) under a strict no-invention rule. Deterministic code then builds a SKILL.md in the Agent Skills open standard, runs a 13-point compliance validator on its own output and shows the verdict, and packages the skill + a source-notes audit file as a zip ready to drop into `.agents/skills/`.

**How we built it:** Layered system (see ARCHITECTURE.md): a custom dark Streamlit UI (4 tabs: Create, Hands-Free Walkthrough, Fix-My-Skill, Clone a Voice); a voice layer on ElevenLabs (Scribe STT for the expert's voice note, Flash/Multilingual TTS narration, consent-gated Instant/Professional voice cloning — the skill can be narrated in the expert's own voice, in 7 languages); a brain layer on open-weight Gemma (`gemma-4-26b-a4b-it`, 26B, large model, Google AI Studio key — no closed Gemini models) doing vision extraction, unclear-item flagging, and translation; and a deterministic core (`skill_builder.py`) that builds the SKILL.md, runs a 13-point compliance validator on its own output, auto-repairs broken skills, and packages SKILL.md + audit notes + narration MP3 + transcripts into one zip. ElevenLabs is an optional layer — remove its key and the whole text pipeline still runs; offline demo mode and tests need no keys at all. Snap2Skill itself is also submitted as a compliant Agent Skill (`skills/snap2skill/SKILL.md`).

**Why it matters:** Organisations lose expertise every day to erased whiteboards and retiring experts, and the Agent Skills ecosystem only grows if ordinary people can author skills. Snap2Skill turns any phone into a skill-authoring tool — in any workplace, classroom, clinic, or workshop on Earth.

**Open source:** MIT-licensed public repository. Model: Gemma under the Gemma Terms of Use (https://ai.google.dev/gemma/terms), named in the README with all dependencies.
