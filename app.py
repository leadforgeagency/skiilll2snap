"""
Snap2Skill web application -- Vercel-first entry point.

Vercel's zero-configuration Flask support detects the ``app`` object in this
file. The same file also runs locally with ``python app.py`` or
``flask --app app run``.

Architecture:
* ``public/``          -- static, responsive web UI served by Vercel's CDN
* ``app.py``           -- thin HTTP routing layer (this file)
* ``web_service.py``   -- JSON validation and orchestration for serverless use
* ``gemma_client.py``  -- open-weight Gemma extraction + Live Sandbox answers
* ``skill_builder.py`` -- deterministic Agent Skill builder and validator

No user state is kept in this process. The browser owns the editing session;
every API call is a complete, stateless request, as Vercel Functions require.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge

from web_service import (PayloadError, bootstrap_payload, build_payload,
                         extract_payload, repair_payload, sandbox_payload,
                         validate_payload)

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=4_500_000,  # Vercel Functions reject larger bodies.
    JSON_SORT_KEYS=False,
)


def _payload() -> dict:
    data = request.get_json(silent=True)
    if data is None:
        raise PayloadError("Send a JSON request body.")
    if not isinstance(data, dict):
        raise PayloadError("The request body must be a JSON object.")
    return data


def _json_service(callable_) -> tuple:
    try:
        return jsonify(callable_(_payload())), 200
    except PayloadError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # Keep provider failures comprehensible in the UI.
        app.logger.exception("Snap2Skill service failure")
        return jsonify({"error": f"The service could not complete that request: {exc}"}), 502


# --------------------------------------------------------------------------
# Web UI
# --------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/<path:asset_path>")
def static_asset(asset_path: str):
    """Serve only files that actually live in public/ (never source files)."""
    candidate = (PUBLIC / asset_path).resolve()
    if PUBLIC.resolve() not in candidate.parents and candidate != PUBLIC.resolve():
        return jsonify({"error": "Not found"}), 404
    if not candidate.is_file():
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(PUBLIC, asset_path)


# --------------------------------------------------------------------------
# JSON API
# --------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify(bootstrap_payload())


@app.get("/api/bootstrap")
def bootstrap():
    return jsonify(bootstrap_payload())


@app.post("/api/extract")
def extract():
    return _json_service(extract_payload)


@app.post("/api/build")
def build():
    return _json_service(build_payload)


@app.post("/api/validate")
def validate():
    return _json_service(validate_payload)


@app.post("/api/repair")
def repair():
    return _json_service(repair_payload)


@app.post("/api/sandbox")
def sandbox():
    return _json_service(sandbox_payload)


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "API route not found."}), 404
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    return jsonify({
        "error": "This request is larger than Vercel's 4.5 MB function limit. "
                 "Use fewer or smaller snaps/samples; the web UI downscales images automatically."
    }), 413


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "That method is not supported for this route."}), 405


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    app.run(host="127.0.0.1", port=port, debug=False)
