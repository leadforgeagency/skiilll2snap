import base64, io, os, sys, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("ELEVENLABS_API_KEY", None)

import web_service as W
from samples import SAMPLE_EXTRACTIONS

def run():
    boot = W.bootstrap_payload()
    assert boot["status"] == "ready" and boot["gemma"]["configured"] is False
    assert boot["elevenlabs"]["configured"] is False
    assert len(boot["samples"]) == 2
    print("bootstrap OK — demo mode reported honestly, samples present")

    # Sample path returns a labelled sample without a model call
    name = list(SAMPLE_EXTRACTIONS)[0]
    out = W.extract_payload({"sample_name": name})
    assert out["extraction"]["_mode"] == "sample" and out["extraction"]["steps"]
    print("sample extraction OK")

    # Text-only path falls back to deterministic demo extraction (no key)
    out2 = W.extract_payload({"text": "1. Boil water\n2. Pour slowly\n3. Serve"})
    assert out2["extraction"]["_mode"] == "demo" and len(out2["extraction"]["steps"]) == 3
    print("demo text extraction OK — 3 steps, nothing invented")

    # A 1x1 PNG upload is accepted (Gemma absent -> demo mode still completes)
    png = base64.b64encode(bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000a49444154789c6360000000020001e221bc3300000000"
        "49454e44ae426082")).decode()
    out3 = W.extract_payload({"images": [{"name": "x.png", "mime_type": "image/png", "data_base64": png}], "text": "1. Only step"})
    assert out3["extraction"]["steps"]
    print("base64 image upload path OK")

    # Bad payloads are rejected cleanly
    for bad in ({"images": [{"name": "x", "mime_type": "image/png", "data_base64": "!!!"}]},
                {"images": [{"name": "x", "mime_type": "text/plain", "data_base64": png}]},
                {"sample_name": "does-not-exist"}):
        try:
            W.extract_payload(bad); raise AssertionError(f"should have rejected {bad}")
        except W.PayloadError:
            pass
    print("invalid payloads rejected with PayloadError")

    # Build produces a valid skill + zip, exactly like the Streamlit edition
    built = W.build_payload({"extraction": out["extraction"], "transcript": "expert words", "narration_script": "script"})
    assert built["validation"]["passed"] and built["validation"]["score"] == 13
    names = zipfile.ZipFile(io.BytesIO(base64.b64decode(built["zip_base64"]))).namelist()
    assert any(n.endswith("references/voice-transcript.txt") for n in names), names
    print(f"build OK — validator 13/13, zip {built['zip_size_bytes']}B, files={len(names)}")

    # Validate + repair endpoints
    bad_md = "# Quick Trick\n- alpha step\n- beta step"
    v = W.validate_payload({"markdown": bad_md})["validation"]
    assert not v["passed"]
    fixed = W.repair_payload({"markdown": bad_md})
    assert fixed["validation"]["passed"] and "alpha step" in fixed["skill_md"]
    print("validate + repair OK")

    # Narration fails soft and returns a speakable script with no ElevenLabs key
    nar = W.narrate_payload({"extraction": out["extraction"], "language": "English"})
    assert nar["mode"] == "voice-off" and "Step 1" in nar["script"] and nar["audio_base64"] == ""
    spk = W.speak_payload({"text": "Step 1. Boil water."})
    assert spk["mode"] == "voice-off"
    print("narration + speak fail soft without ElevenLabs key")

    # Clone is consent-gated at the backend, not just in the UI
    try:
        W.clone_payload({"name": "X", "consent": False, "samples": []}); raise AssertionError("clone without consent")
    except W.PayloadError:
        print("clone consent gate OK")

    print("ALL WEB SERVICE TESTS PASSED")

if __name__ == "__main__":
    run()
