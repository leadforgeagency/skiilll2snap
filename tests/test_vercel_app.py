import base64, io, os, sys, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("ELEVENLABS_API_KEY", None)

from app import app  # the exact Flask object Vercel detects in app.py

def run():
    c = app.test_client()
    r = c.get("/")
    assert r.status_code == 200 and b"Snap2Skill" in r.data and b'id="studio"' in r.data
    assert b"Flowchart" in r.data and b"Live Sandbox" in r.data
    print("GET / serves the single-screen studio UI")

    for asset in ("/styles.css", "/app.js"):
        r = c.get(asset)
        assert r.status_code == 200 and len(r.data) > 1000, asset
    # bright palette guard: the stylesheet must stay on the bright scheme
    css = c.get("/styles.css").data.decode()
    for token in ("#eef1ff", "#ffffff", "#f6f8ff", "#d8defc", "#7c3aed", "#0f172a", "#64748b"):
        assert token in css, token
    print("static assets served; bright palette tokens present")

    # Source files must NOT be reachable through the static route
    assert c.get("/app.py").status_code == 404
    assert c.get("/.env.example").status_code == 404
    print("source files are not exposed")

    r = c.get("/api/bootstrap")
    assert r.status_code == 200 and r.json["status"] == "ready" and len(r.json["samples"]) == 2
    assert "elevenlabs" not in r.json
    print("GET /api/bootstrap OK (no voice layer)")

    sample = list(r.json["samples"])[0]
    r = c.post("/api/extract", json={"sample_name": sample})
    assert r.status_code == 200 and r.json["extraction"]["steps"]
    extraction = r.json["extraction"]

    r = c.post("/api/build", json={"extraction": extraction})
    assert r.status_code == 200 and r.json["validation"]["passed"]
    names = zipfile.ZipFile(io.BytesIO(base64.b64decode(r.json["zip_base64"]))).namelist()
    assert any(n.endswith("/SKILL.md") for n in names)
    print("POST /api/extract + /api/build OK — valid skill zip over HTTP")

    r = c.post("/api/validate", json={"markdown": "# T\n- one step\n- two step"})
    assert r.status_code == 200 and r.json["validation"]["passed"] is False
    r = c.post("/api/repair", json={"markdown": "# T\n- one step\n- two step"})
    assert r.status_code == 200 and r.json["validation"]["passed"] is True
    print("POST /api/validate + /api/repair OK")

    r = c.post("/api/sandbox", json={"extraction": extraction, "question": "Do the thing"})
    assert r.status_code == 200 and r.json["mode"] == "demo" and len(r.json["answer"]) > 50
    print("POST /api/sandbox OK — deterministic walkthrough in demo mode")

    # Removed voice endpoints must be gone (404, or 405 from the method guard)
    for gone in ("/api/narrate", "/api/speak", "/api/clone"):
        assert c.post(gone, json={}).status_code in (404, 405), gone
    print("voice endpoints removed")

    r = c.post("/api/extract", data="not json", content_type="application/json")
    assert r.status_code == 400 and "error" in r.json
    r = c.get("/api/nope")
    assert r.status_code == 404
    print("error handling OK")
    print("ALL VERCEL APP TESTS PASSED")

if __name__ == "__main__":
    run()
