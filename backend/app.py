import os
import sys
import logging
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS

# Allow running as `python backend/app.py`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
from license_manager import (
    check_and_activate,
    create_license,
    revoke_license,
    delete_license,
    list_licenses,
    VALID_DURATIONS,
)
from api_client import search_request, get_me, VALID_SEARCH_TYPES


# ---------- app setup ----------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY") or "cloviss-dev-insecure-secret"

# Cross-domain session cookie settings (Vercel <-> Render)
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
)

# Allow Vercel frontend to call this API
CORS(
    app,
    supports_credentials=True,
    origins=[
        "https://eraskye-dox.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("cloviss")

# init DB at import time so gunicorn workers also have it ready
init_db()


# ---------- helpers ----------

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401
        return fn(*args, **kwargs)
    return wrapper


def _require_active_license(payload: dict):
    """Returns (status_code, response_dict) or (None, license_info)."""
    key = (payload.get("key") or "").strip()
    device_id = (payload.get("device_id") or "").strip()
    if not key or not device_id:
        return 400, {"ok": False, "error": "MISSING_FIELDS"}
    info = check_and_activate(key, device_id)
    if not info.get("ok") or info.get("status") != "ACTIVE":
        return 403, info
    return None, info


# ---------- static pages ----------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/admin")
def admin_page():
    return send_from_directory(FRONTEND_DIR, "admin.html")


# ---------- health ----------

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "CLOVISS SYSTEM PYDXSN",
        "api_configured": bool(os.environ.get("JITLER_API_KEY")),
    })


# ---------- license ----------

@app.post("/api/license/check")
def license_check():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    device_id = (data.get("device_id") or "").strip()
    if not key or not device_id:
        return jsonify({"ok": False, "error": "MISSING_FIELDS"}), 400
    info = check_and_activate(key, device_id)
    return jsonify(info), (200 if info.get("ok") else 403)


# ---------- search ----------

@app.post("/api/search")
def api_search():
    data = request.get_json(silent=True) or {}
    err, info = _require_active_license(data)
    if err:
        return jsonify(info), err

    search_type = (data.get("type") or "").strip()
    query = (data.get("query") or "").strip()
    page_raw = data.get("page", 1)

    if search_type not in VALID_SEARCH_TYPES:
        return jsonify({"ok": False, "error": "INVALID_SEARCH_TYPE"}), 400
    if not query:
        return jsonify({"ok": False, "error": "EMPTY_QUERY"}), 400
    if len(query) > 256:
        return jsonify({"ok": False, "error": "QUERY_TOO_LONG"}), 400

    try:
        page = int(page_raw)
        if page < 1:
            page = 1
        if page > 1000:
            page = 1000
    except (TypeError, ValueError):
        page = 1

    result = search_request(search_type, query, page)

    if "error" in result:
        http_status = 504 if result["error"] == "API_TIMEOUT" else 502
        if result["error"] in ("INVALID_SEARCH_TYPE", "EMPTY_QUERY"):
            http_status = 400
        return jsonify({"ok": False, **result}), http_status

    return jsonify({"ok": True, "data": result.get("data")})


# ---------- /me passthrough (license-gated) ----------

@app.post("/api/account/me")
def account_me():
    data = request.get_json(silent=True) or {}
    err, info = _require_active_license(data)
    if err:
        return jsonify(info), err

    result = get_me()
    if "error" in result:
        return jsonify({"ok": False, **result}), 502
    return jsonify({"ok": True, "data": result.get("data")})


# ---------- admin ----------

@app.post("/api/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    u = (data.get("username") or "").strip()
    p = (data.get("password") or "").strip()
    expected_u = os.environ.get("ADMIN_USERNAME", "")
    expected_p = os.environ.get("ADMIN_PASSWORD", "")
    if not expected_u or not expected_p:
        return jsonify({"ok": False, "error": "ADMIN_NOT_CONFIGURED"}), 500
    if u == expected_u and p == expected_p:
        session["admin"] = True
        session.permanent = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "INVALID_CREDENTIALS"}), 401


@app.post("/api/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return jsonify({"ok": True})


@app.get("/api/admin/me")
def admin_me():
    return jsonify({"ok": True, "admin": bool(session.get("admin"))})


@app.post("/api/admin/license/create")
@admin_required
def admin_create_license():
    data = request.get_json(silent=True) or {}
    try:
        days = int(data.get("duration", 0))
    except (TypeError, ValueError):
        days = 0
    if days not in VALID_DURATIONS:
        return jsonify({"ok": False, "error": "INVALID_DURATION"}), 400
    lic = create_license(days)
    return jsonify({"ok": True, "license": lic})


@app.get("/api/admin/licenses")
@admin_required
def admin_list_licenses():
    return jsonify({"ok": True, "licenses": list_licenses()})


@app.post("/api/admin/license/revoke")
@admin_required
def admin_revoke_license():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "MISSING_KEY"}), 400
    return jsonify({"ok": revoke_license(key)})


@app.post("/api/admin/license/delete")
@admin_required
def admin_delete_license():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "MISSING_KEY"}), 400
    return jsonify({"ok": delete_license(key)})


# ---------- errors ----------

@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "NOT_FOUND"}), 404
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.errorhandler(500)
def server_error(e):
    log.exception("server error: %s", e)
    return jsonify({"ok": False, "error": "SERVER_ERROR"}), 500


# ---------- entry ----------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
