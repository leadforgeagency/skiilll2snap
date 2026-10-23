---
name: snap2skill
description: |
  Turn a photo, screenshot, or pasted notes of a procedure into a validated,
  reusable Agent Skill (SKILL.md). Use when a user shares know-how as an image
  or rough notes — a whiteboard, SOP, manual page, checklist, recipe, or wiki
  screenshot — and wants it captured as a skill other agents can run.
license: MIT
metadata:
  version: "1.0.0"
  author: Jawad
  model: gemma-4-26b-a4b-it (open-weight Gemma vision, via Gemini API)
---

# Snap2Skill

## When to use
- The user uploads a photo/screenshot of a process and says "make this reusable / a skill / a SOP"
- Knowledge exists only on a whiteboard, in handwriting, or in a screenshot

## Workflow
1. Extract only what is visible in the source: title, triggers, prerequisites, inputs, ordered steps, tools, constraints, and one example. Mark unclear items as unclear — never invent expert steps.
2. Build the skill with `skill_builder.build_skill_md(extraction)` — do not hand-format frontmatter.
3. Validate with `skill_builder.validate_skill_md(md, folder_name)` and show the user the compliance result.
4. Deliver the zip from `skill_builder.make_skill_zip(extraction)` so the user can drop the folder into `.agents/skills/`.

## Constraints
- Never add steps, quantities, or warnings that are not in the source or the user's own notes.
- Keep the frontmatter `name` kebab-case and identical to the folder name.
- If the snap is unreadable, say so and ask for a clearer snap instead of generating a plausible skill.

## Example
Input: a photo of a cafe whiteboard, "POUR OVER — HOUSE METHOD, 15g, bloom 45g 30s…"
Output: a `pour-over-coffee/` folder containing a validated `SKILL.md` and `references/source-notes.md`, zipped for download.
