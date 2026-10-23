"""
Gemma access via the Google AI Studio (Gemini API) key — OPEN-WEIGHT Gemma only.
Google documents hosted Gemma on this API as gemma-4-31b-it / gemma-4-26b-a4b-it;
Gemma 3 IDs are fallbacks if a project does not list Gemma 4 yet.
This project never calls a closed Gemini model.
"""
from __future__ import annotations

import json
import os
import re

MODEL_CANDIDATES = [m for m in [
    os.getenv("GEMMA_MODEL", "").strip(),
    "gemma-4-26b-a4b-it", "gemma-4-31b-it", "gemma-3-27b-it", "gemma-3-12b-it",
] if m]

PROMPT = """You turn a photo/screenshot/notes of HOW TO DO SOMETHING into a reusable Agent Skill.
Look at the source carefully. Return ONLY valid JSON, no markdown.

{{
  "skill_name": "short kebab-case name, e.g. pour-over-coffee",
  "title": "Human title of the skill",
  "description": "2-3 sentences: what this skill does and WHEN an agent should use it. Start with a verb.",
  "when_to_use": ["trigger situation 1", "trigger situation 2"],
  "prerequisites": ["tool/material/knowledge needed, only if visible in the source"],
  "inputs": ["what the agent needs from the user"],
  "steps": ["step 1 in imperative form", "step 2", "... include every step visible in the source, in order"],
  "tools": ["tools/materials visible in the source"],
  "constraints": ["warnings, timings, quantities, or 'do not' rules visible in the source"],
  "examples": [{{"input": "a realistic request", "output": "what success looks like following these steps"}}],
  "unclear_items": ["any step/fact that was hard to read or ambiguous in the source, in your own words — empty list if everything was clear"],
  "evidence": "one sentence: what you actually saw in the source (photo of whiteboard, screenshot, handwritten notes...)"
}}

HONESTY RULES (critical):
- Only include steps/facts VISIBLE in the source or in the user's extra notes below.
- If text in the image is unclear, write that step as 'Unclear in source — ask the user' instead of guessing.
- Never add expert steps that are not in the source, even if you know them.

USER EXTRA NOTES: {notes}
SOURCE TEXT (if the user pasted text instead of / as well as an image): \"\"\"{text}\"\"\"
"""


def _client():
    from google import genai
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    return genai.Client(api_key=key) if key else None


def _generate(contents) -> tuple[str, str]:
    client = _client()
    if client is None:
        raise RuntimeError("No GOOGLE_API_KEY — demo mode.")
    last = None
    for model in MODEL_CANDIDATES:
        try:
            r = client.models.generate_content(model=model, contents=contents)
            if r and r.text:
                return r.text.strip(), model
        except Exception as e:
            last = e
    raise RuntimeError(f"No Gemma model responded: {last}")


def _parse(raw: str) -> dict:
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def extract_skill(text: str = "", notes: str = "", image_path: str | None = None,
                  image_mime: str = "image/png", image_paths: list[tuple[str, str]] | None = None,
                  image_data: list[tuple[bytes, str]] | None = None) -> dict:
    """Returns extraction dict + _model + _mode ('gemma'|'demo').

    Multi-snap inputs can be supplied either as local paths (Streamlit/local
    use) or as in-memory ``(bytes, mime_type)`` pairs (Vercel Functions, where
    uploaded files never need to be written to a durable filesystem).
    Up to five snaps are merged in order.
    """
    try:
        prompt = PROMPT.format(notes=notes or "none", text=text or "(see image)")
        paths = list(image_paths or [])
        if image_path:
            paths.insert(0, (image_path, image_mime))
        in_memory = list(image_data or [])
        if paths or in_memory:
            from google.genai import types
            contents = []
            for p, mime in paths[:5]:
                with open(p, "rb") as f:
                    contents.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
            remaining = max(0, 5 - len(contents))
            for data, mime in in_memory[:remaining]:
                if data:
                    contents.append(types.Part.from_bytes(data=data, mime_type=mime or "image/png"))
            contents.append(prompt)
        else:
            contents = prompt
        raw, model = _generate(contents)
        d = _parse(raw)
        if d and d.get("steps"):
            d["_model"], d["_mode"] = model, "gemma"
            return d
    except Exception as e:
        return demo_extract(text, note=str(e))
    return demo_extract(text)


SANDBOX_PROMPT = """You are an AI agent that has loaded the Agent Skill below. A user is testing you in a sandbox.
Answer their request by FOLLOWING THE SKILL exactly: walk through its workflow steps in order, respect its
constraints, and only use knowledge contained in the skill. If the skill does not cover something, say so
plainly instead of inventing it. Keep the answer practical and structured: start with a one-line plan, then
the numbered steps you would take for this request, then the expected result.

=== SKILL (SKILL.md) ===
{skill_md}
=== END SKILL ===

USER REQUEST: {question}
"""


def answer_as_skill(skill_md: str, question: str, extraction: dict | None = None) -> dict:
    """Live Sandbox brain: Gemma answers AS the compiled skill.
    Falls back to a deterministic walkthrough of the skill's own steps when
    no Gemma key is configured, so the sandbox always works."""
    try:
        raw, model = _generate(SANDBOX_PROMPT.format(skill_md=skill_md[:12_000], question=question[:2_000]))
        if raw:
            return {"answer": raw, "mode": "gemma", "model": model}
    except Exception:
        pass
    x = extraction or {}
    steps = x.get("steps") or []
    lines = [
        f"Running **{x.get('title') or 'this skill'}** in demo sandbox mode (no Gemma key configured).",
        "",
        f"Your request: \"{question}\"",
        "",
        "Here is exactly how an agent loaded with this skill would handle it, step by step:",
    ]
    lines += [f"{i}. {s}" for i, s in enumerate(steps, 1)] or ["1. (The skill has no workflow steps yet.)"]
    if x.get("constraints"):
        lines += ["", "Constraints I would respect:"] + [f"- {c}" for c in x["constraints"]]
    lines += ["", "Add GOOGLE_API_KEY in Vercel to let Gemma answer freely as this skill."]
    return {"answer": "\n".join(lines), "mode": "demo", "model": "deterministic sandbox (no Gemma call)"}


def demo_extract(text: str = "", note: str = "") -> dict:
    """Offline demo: turns pasted numbered/bulleted notes into a skill with NO AI.
    Proves the builder+validator pipeline works even with no API key."""
    steps = []
    for ln in (text or "").splitlines():
        ln = re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", ln).strip()
        if ln:
            steps.append(ln)
    if not steps:
        steps = ["No readable steps were provided — upload a clearer snap or paste the steps as text."]
    return {
        "skill_name": "snap-demo-skill",
        "title": "Snap Demo Skill",
        "description": "Demo-mode skill built from pasted notes without a Gemma call. Add GOOGLE_API_KEY for full vision extraction from photos and screenshots.",
        "when_to_use": ["When the task described in the source notes comes up."],
        "prerequisites": ["As stated in the source notes."],
        "inputs": ["The user's specific version of this task."],
        "steps": steps,
        "tools": [],
        "constraints": ["Demo mode: only the pasted text was used, nothing was invented."],
        "examples": [{"input": "Do this task for me", "output": "Task completed by following the workflow steps in order."}],
        "unclear_items": [],
        "evidence": "pasted text notes (demo mode, no image was read by a model)",
        "_model": "demo-mode (no Gemma call)", "_mode": "demo", "_note": note,
    }
