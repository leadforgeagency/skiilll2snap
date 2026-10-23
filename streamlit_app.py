"""
Snap2Skill — Snap a photo of know-how. Get a validated, voiced Agent Skill.

SYSTEM DESIGN (see ARCHITECTURE.md):
  Presentation  : this Streamlit app (custom dark UI)
  Voice layer   : voice.py — ElevenLabs Scribe (in) + TTS / voice clone (out), optional + fails soft
  Brain layer   : gemma_client.py — OPEN-WEIGHT Gemma Vision (Google AI Studio key), Gemma-only model IDs
  Deterministic : skill_builder.py — builds SKILL.md, 13-point validator, Fix-My-Skill repair, zip packager
  State         : st.session_state only. Nothing is stored on disk. API keys live in .env, never in code.

Legacy local UI: streamlit run streamlit_app.py   →   add GOOGLE_API_KEY (+ optional ELEVENLABS_API_KEY) to .env
Primary Vercel UI: app.py + public/ (see VERCEL_DEPLOYMENT.md)
"""
from __future__ import annotations

import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

import voice as V
from gemma_client import extract_skill, translate_text
from samples import SAMPLE_EXTRACTIONS
from skill_builder import (build_skill_md, make_skill_zip, repair_skill_md,
                           slugify, validate_skill_md)

load_dotenv()
st.set_page_config(page_title="Snap2Skill — Snap it. Skill it. Hear it.", page_icon="📸",
                   layout="wide", initial_sidebar_state="expanded")

# ------------------------------------------------------------------ UI / CSS
st.markdown("""
<style>
  #MainMenu, footer {visibility: hidden;}
  .block-container {padding-top: 1.2rem; max-width: 1280px;}
  .hero {background: linear-gradient(120deg,#241447 0%,#3B1D78 45%,#0E5E6F 100%);
         border: 1px solid rgba(255,255,255,.14); border-radius: 22px; padding: 30px 34px 24px; margin-bottom: 18px;}
  .hero h1 {color:#fff; font-size: 44px; margin:0; letter-spacing:-1px;}
  .hero p  {color:#D9D2FF; font-size:17px; margin:8px 0 0;}
  .hero .tag {display:inline-block; background:rgba(255,255,255,.14); color:#fff; border-radius:999px;
              padding:4px 12px; font-size:12.5px; margin-right:6px; margin-top:12px;}
  .steps {display:flex; gap:8px; flex-wrap:wrap; margin: 4px 0 14px;}
  .step {flex:1; min-width:150px; background:#131A2A; border:1px solid rgba(255,255,255,.09);
         border-radius:14px; padding:10px 14px; color:#C9D4F2; font-size:13.5px;}
  .step b {color:#fff;}
  .card {background:#131A2A; border:1px solid rgba(255,255,255,.09); border-radius:18px; padding:18px 20px;}
  .bigstep {background:linear-gradient(135deg,#1B2440,#131A2A); border:1px solid #7C5CFF55; border-radius:20px;
            padding:28px; font-size:26px; line-height:1.45; color:#fff; min-height:150px;}
  .ok {color:#4ADE80; font-weight:700;} .bad {color:#F87171; font-weight:700;} .warn{color:#FBBF24; font-weight:700;}
  div[data-testid="stDownloadButton"] button, div[data-testid="stButton"] button {border-radius:12px; font-weight:600;}
</style>
<div class="hero">
  <h1>📸 Snap2Skill</h1>
  <p>Snap a photo of know-how — a whiteboard, a notebook, a screenshot — and get a
     <b>validated Agent Skill</b>, narrated in a real voice. In about 30 seconds.</p>
  <span class="tag">🧠 Open-weight Gemma Vision</span><span class="tag">🎙️ ElevenLabs voice</span>
  <span class="tag">✅ 13-point skill validator</span><span class="tag">📦 One-click skill zip</span>
</div>
<div class="steps">
  <div class="step"><b>1 · Snap</b><br>Photo, screenshots, voice note</div>
  <div class="step"><b>2 · Gemma reads</b><br>Extracts steps, never invents</div>
  <div class="step"><b>3 · You check</b><br>Edit steps before export</div>
  <div class="step"><b>4 · Code validates</b><br>13 compliance checks</div>
  <div class="step"><b>5 · Hear + ship</b><br>Voice narration + zip</div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ Sidebar: status
with st.sidebar:
    st.markdown("### ⚙️ System status")
    gemma_ok = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    st.markdown(f"{'🟢' if gemma_ok else '🔴'} **Gemma (core brain)** — {'key found' if gemma_ok else 'add GOOGLE_API_KEY to .env'}")
    st.markdown(f"{'🟢' if V.available() else '⚪'} **ElevenLabs (voice)** — {'key found' if V.available() else 'optional: add ELEVENLABS_API_KEY to .env'}")
    st.caption("Keys are read from your local `.env` only — never typed here, never uploaded, never committed.")
    st.divider()
    st.markdown("### 🎙️ Expert voice")
    custom_vid = st.text_input("Pre-created clone voice ID (optional)", placeholder="Paste a Professional Clone voice_id")
    if custom_vid:
        st.session_state["expert_voice_id"] = custom_vid.strip()
    if st.session_state.get("expert_voice_id"):
        st.markdown("<span class='ok'>● Expert voice active for narration</span>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### 📦 What you get")
    st.caption("`SKILL.md` (validated) · `references/source-notes.md` · `audio/guide.mp3` (if narrated) · `audio/narration.txt` · `references/voice-transcript.txt` (if a voice note was used)")

ss = st.session_state
ss.setdefault("gen_id", 0)

tab_create, tab_walk, tab_fix, tab_clone = st.tabs(
    ["✨ Create a Skill", "🙌 Hands-Free Walkthrough", "🛠️ Fix My Skill", "🎙️ Clone an Expert Voice"])

# ================================================================== TAB 1 — CREATE
with tab_create:
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### 1 · Snap the know-how")
        imgs = st.file_uploader("Photos / screenshots — up to 5 snaps, merged in order",
                                type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
        if imgs:
            for im in imgs[:3]:
                st.image(im, caption=im.name, use_container_width=True)
        voice_note = st.file_uploader("🎙️ Expert voice note (optional) — ElevenLabs Scribe transcribes it, Gemma uses it",
                                      type=["mp3", "wav", "m4a", "ogg", "webm"])
        text = st.text_area("…or paste steps / notes as text", height=110,
                            placeholder="1. First step\n2. Second step\nWarning: never do X")
        notes = st.text_input("Anything not in the snap the agent should know? (optional)")
        sample = st.selectbox("No snap handy? Load a sample", ["— none —"] + list(SAMPLE_EXTRACTIONS.keys()))
        run = st.button("✨ Turn it into a Skill", type="primary", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if run:
        transcript = ""
        if sample != "— none —" and not imgs and not text and not voice_note:
            ex = dict(SAMPLE_EXTRACTIONS[sample]); ex["_mode"], ex["_model"] = "sample", "sample extraction (offline demo)"
        else:
            if voice_note is not None:
                with st.spinner("ElevenLabs Scribe is transcribing the expert…"):
                    tr = V.transcribe(voice_note.getvalue())
                transcript = tr["text"]
                if transcript:
                    st.success(f"Voice note transcribed ({tr.get('language') or 'auto-detected'}): “{transcript[:160]}…”")
                elif not V.available():
                    st.warning("Voice note ignored — add ELEVENLABS_API_KEY to .env to enable Scribe. Continuing with snap/text.")
            paths = []
            for im in (imgs or [])[:5]:
                suffix = "." + (im.name.rsplit(".", 1)[-1].lower() if "." in im.name else "png")
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                    f.write(im.getbuffer()); paths.append((f.name, im.type or "image/png"))
            merged_notes = (notes + " " if notes else "") + (f"Expert said (voice transcript): {transcript}" if transcript else "")
            with st.spinner("Gemma Vision is reading your snap…"):
                ex = extract_skill(text=text, notes=merged_notes.strip(), image_paths=paths)
        ss["extraction"] = ex
        ss["transcript"] = transcript
        ss["gen_id"] += 1
        ss.pop("audio_bytes", None); ss.pop("audio_script", None)
        ss["walk_idx"] = 0

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### 2 · Check, hear, and ship it")
        ex0 = ss.get("extraction")
        if not ex0:
            st.info("Upload a whiteboard snap from this room, record the expert explaining it, or load a sample — then press **Turn it into a Skill**.")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            gid = ss["gen_id"]
            st.caption(f"Extraction: {ex0.get('_mode')} · Model: {ex0.get('_model')}")
            for u in (ex0.get("unclear_items") or []):
                st.markdown(f"<span class='warn'>⚠️ Unclear in source (not invented):</span> {u}", unsafe_allow_html=True)
            title = st.text_input("Skill title", value=ex0.get("title", "My Skill"), key=f"title_{gid}")
            desc = st.text_area("Description (when should an agent use this?)", value=ex0.get("description", ""), key=f"desc_{gid}", height=70)
            steps_txt = st.text_area("Steps — edit freely, one per line (human-in-the-loop ✓)",
                                     value="\n".join(ex0.get("steps") or []), key=f"steps_{gid}", height=170)
            cons_txt = st.text_area("Constraints / warnings — one per line",
                                    value="\n".join(ex0.get("constraints") or []), key=f"cons_{gid}", height=80)
            edited = dict(ex0)
            edited.update({
                "title": title, "skill_name": slugify(title), "description": desc,
                "steps": [s.strip(" -•\t") for s in steps_txt.splitlines() if s.strip()],
                "constraints": [s.strip(" -•\t") for s in cons_txt.splitlines() if s.strip()],
            })

            folder, _, md_preview = make_skill_zip(edited)
            verdict = validate_skill_md(md_preview, folder_name=folder)
            if verdict["passed"]:
                st.markdown(f"<span class='ok'>✅ VALID Agent Skill — {verdict['score']}/{verdict['total']} compliance checks passed · folder `{folder}/`</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span class='bad'>⚠️ {verdict['score']}/{verdict['total']} checks passed</span>", unsafe_allow_html=True)
                st.table([{"Check": n, "Pass": "✅" if ok else "❌", "Detail": d} for n, ok, d in verdict["checks"] if not ok])

            st.markdown("**🎧 Narrate this skill (ElevenLabs)**")
            c1, c2 = st.columns(2)
            lang = c1.selectbox("Narration language", ["English", "Urdu", "Hindi", "Arabic", "Spanish", "French", "German"], key=f"lang_{gid}")
            use_clone = c2.selectbox("Voice", ["Library voice", "Expert clone (if set)"] if ss.get("expert_voice_id") else ["Library voice"], key=f"voice_{gid}")
            if st.button("▶️ Generate narration", use_container_width=True):
                if not V.available():
                    st.warning("Add ELEVENLABS_API_KEY to .env to enable narration. The skill itself still works below.")
                else:
                    with st.spinner("Gemma translates (if needed)… ElevenLabs speaks…"):
                        script = V.narration_script(edited)
                        if lang != "English":
                            script = translate_text(script, lang)
                        vid = ss.get("expert_voice_id") if use_clone.startswith("Expert") else None
                        audio = V.speak(script, voice_id=vid, multilingual=(lang != "English"))
                    if audio:
                        ss["audio_bytes"], ss["audio_script"] = audio, script
                    else:
                        st.error("Narration failed (check ElevenLabs key/credits). Text skill is unaffected.")
            if ss.get("audio_bytes"):
                st.audio(ss["audio_bytes"], format="audio/mp3")
                st.caption("This MP3 is bundled into the zip as `audio/guide.mp3`.")

            folder, zip_bytes, md = make_skill_zip(edited, audio_bytes=ss.get("audio_bytes"),
                                                   transcript=ss.get("transcript", ""),
                                                   narration_script=ss.get("audio_script", ""))
            with st.expander("Preview generated SKILL.md"):
                st.code(md, language="markdown")
            st.download_button("⬇️ Download Skill Zip — drop into .agents/skills/", data=zip_bytes,
                               file_name=f"{folder}.zip", mime="application/zip",
                               type="primary", use_container_width=True)
            st.caption("Works with any Agent-Skills-compatible agent. Only source-visible facts are in the skill — unclear items are flagged, never invented.")
            ss["edited"] = edited
            st.markdown('</div>', unsafe_allow_html=True)

# ================================================================== TAB 2 — WALKTHROUGH
with tab_walk:
    exw = ss.get("edited") or ss.get("extraction")
    st.markdown("#### 🙌 Hands-free walkthrough — for kitchens, workshops, and labs where hands are busy")
    if not exw or not (exw.get("steps") or []):
        st.info("Create a skill first (tab 1), then come back here to be walked through it step by step, out loud.")
    else:
        steps = exw["steps"]; idx = max(0, min(ss.get("walk_idx", 0), len(steps) - 1))
        st.progress((idx) / max(len(steps) - 1, 1) if len(steps) > 1 else 1.0, text=f"Step {idx+1} of {len(steps)} — {exw.get('title','Skill')}")
        st.markdown(f'<div class="bigstep"><b>Step {idx+1}</b><br>{steps[idx]}</div>', unsafe_allow_html=True)
        b1, b2, b3 = st.columns(3)
        if b1.button("⬅️ Previous", use_container_width=True, disabled=idx == 0):
            ss["walk_idx"] = idx - 1; st.rerun()
        if b2.button("🔊 Speak this step", type="primary", use_container_width=True):
            audio = V.speak(f"Step {idx+1}. {steps[idx]}") if V.available() else None
            if audio:
                st.audio(audio, format="audio/mp3")
            else:
                st.warning("Voice is off — add ELEVENLABS_API_KEY to .env, or just read the step above.")
        if b3.button("Next ➡️", use_container_width=True, disabled=idx >= len(steps) - 1):
            ss["walk_idx"] = idx + 1; st.rerun()
        if idx == len(steps) - 1:
            st.success("🎉 That's the last step — skill complete.")

# ================================================================== TAB 3 — FIX MY SKILL
with tab_fix:
    st.markdown("#### 🛠️ Fix My Skill — paste any broken SKILL.md, get a compliant one back")
    broken = st.text_area("Paste a SKILL.md", height=220, placeholder="---\nname: my skill\ndescription: ...\n---\n# My Skill\n- step one\n- step two", key="fix_in")
    f1, f2 = st.columns(2)
    if f1.button("🔍 Validate only", use_container_width=True) and broken.strip():
        v = validate_skill_md(broken)
        st.markdown(f"**{v['score']}/{v['total']} checks passed**")
        st.table([{"Check": n, "Pass": "✅" if ok else "❌", "Detail": d} for n, ok, d in v["checks"]])
    if f2.button("🪄 Auto-repair it", type="primary", use_container_width=True) and broken.strip():
        fixed = repair_skill_md(broken)
        import re as _re
        _nm = _re.search(r"^name:\s*(\S+)", fixed, flags=_re.MULTILINE)
        v = validate_skill_md(fixed, folder_name=_nm.group(1) if _nm else None)
        st.success(f"Repaired — validator now: {v['score']}/{v['total']} checks passed. Original workflow content preserved.")
        st.code(fixed, language="markdown")
        st.download_button("⬇️ Download repaired SKILL.md", data=fixed.encode(), file_name="SKILL.md", mime="text/markdown")

# ================================================================== TAB 4 — CLONE
with tab_clone:
    st.markdown("#### 🎙️ Clone an expert's voice — with their consent")
    st.caption("Creator plan includes Professional Voice Cloning — best created BEFORE a demo (it takes time to train). "
               "Instant Cloning below works live from ~1 minute of clean audio and is the in-app path. Only clone a voice you own or have explicit permission to clone.")
    cname = st.text_input("Expert's name (voice name)", placeholder="e.g. Master Barista — Ahmed")
    samples_up = st.file_uploader("Voice samples (mp3/wav, clean, no background noise)", type=["mp3", "wav", "m4a"], accept_multiple_files=True)
    consent = st.checkbox("I confirm this is my voice, or I have the speaker's explicit consent to clone it.")
    if st.button("🎙️ Create instant clone", type="primary"):
        if not V.available():
            st.warning("Add ELEVENLABS_API_KEY to .env first.")
        elif not consent:
            st.error("Consent confirmation is required — no consent, no clone.")
        elif not samples_up:
            st.error("Upload at least one voice sample.")
        else:
            with st.spinner("Creating clone on ElevenLabs…"):
                res = V.clone_instant_voice(cname, [s.getvalue() for s in samples_up])
            if res.get("voice_id"):
                ss["expert_voice_id"] = res["voice_id"]
                st.success(f"Clone created and set as the expert voice: `{res['voice_id']}` — now generate a narration in tab 1 and hear the skill in their voice.")
            else:
                st.error(f"Clone failed: {res.get('_mode')}. Tip: for the demo, paste a pre-created Professional Clone voice_id in the sidebar instead.")
