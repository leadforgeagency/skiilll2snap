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
    assert "elevenlabs" not in boot  # voice layer removed by design
    assert len(boot["samples"]) == 2
    print("bootstrap OK — demo mode reported honestly, samples present, no voice layer")

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

    # Build produces a valid skill + zip
    built = W.build_payload({"extraction": out["extraction"]})
    assert built["validation"]["passed"] and built["validation"]["score"] == 13
    names = zipfile.ZipFile(io.BytesIO(base64.b64decode(built["zip_base64"]))).namelist()
    assert any(n.endswith("/SKILL.md") for n in names) and len(names) == 2, names
    print(f"build OK — validator 13/13, zip {built['zip_size_bytes']}B, files={len(names)}")

    # Validate + repair endpoints
    bad_md = "# Quick Trick\n- alpha step\n- beta step"
    v = W.validate_payload({"markdown": bad_md})["validation"]
    assert not v["passed"]
    fixed = W.repair_payload({"markdown": bad_md})
    assert fixed["validation"]["passed"] and "alpha step" in fixed["skill_md"]
    print("validate + repair OK")

    # Live Sandbox: demo mode answers as a deterministic walkthrough of the skill
    sbx = W.sandbox_payload({"extraction": out["extraction"], "question": "Make one for two people"})
    assert sbx["mode"] == "demo" and len(sbx["answer"]) > 50
    assert out["extraction"]["steps"][0] in sbx["answer"]
    print("sandbox OK — deterministic skill walkthrough without a key")

    print("ALL WEB SERVICE TESTS PASSED")

if __name__ == "__main__":
    run()
