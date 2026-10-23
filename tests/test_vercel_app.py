import base64, io, os, sys, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("ELEVENLABS_API_KEY", None)

from app import app  # the exact Flask object Vercel detects in app.py

def run():
    c = app.test_client()
    r = c.get("/")
    assert r.status_code == 200 and b"Snap2Skill" in r.data and b'id="studio"' in r.data
    print("GET / serves the web UI")

    for asset in ("/styles.css", "/app.js"):
        r = c.get(asset)
        assert r.status_code == 200 and len(r.data) > 1000, asset
    print("static assets served from public/")

    # Source files must NOT be reachable through the static route
    assert c.get("/app.py").status_code == 404
    assert c.get("/.env.example").status_code == 404
    print("source files are not exposed")

    r = c.get("/api/bootstrap")
    assert r.status_code == 200 and r.json["status"] == "ready" and len(r.json["samples"]) == 2
    print("GET /api/bootstrap OK")

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

    r = c.post("/api/narrate", json={"extraction": extraction, "language": "English"})
    assert r.status_code == 200 and r.json["mode"] == "voice-off" and "Step 1" in r.json["script"]
    r = c.post("/api/clone", json={"name": "X", "consent": False, "samples": []})
    assert r.status_code == 400
    print("narration fails soft; clone consent enforced over HTTP")

    r = c.post("/api/extract", data="not json", content_type="application/json")
    assert r.status_code == 400 and "error" in r.json
    r = c.get("/api/nope")
    assert r.status_code == 404
    print("error handling OK")
    print("ALL VERCEL APP TESTS PASSED")

if __name__ == "__main__":
    run()
