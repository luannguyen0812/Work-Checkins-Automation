import os
from flask import Flask, jsonify, request, abort
from datastore import sheets
from datastore.queries import compute_all_risk_scores
from utils.time_utils import edt_now

app = Flask(__name__)


def _require_auth():
    token = request.headers.get("Authorization", "")
    if token != f"Bearer {os.environ['ADMIN_API_SECRET']}":
        abort(401)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/status")
def status():
    _require_auth()
    raise NotImplementedError


@app.post("/config")
def update_config():
    _require_auth()
    body = request.get_json(force=True)
    sheets.update_config_key(body["key"], body["value"])
    return jsonify(sheets.get_config().model_dump())


@app.post("/report/run")
def run_report():
    _require_auth()
    raise NotImplementedError


@app.get("/interns")
def list_interns():
    _require_auth()
    interns = sheets.get_all_interns()
    return jsonify([i.model_dump() for i in interns])


@app.post("/interns/<intern_id>/opt-out")
def opt_out(intern_id: str):
    _require_auth()
    sheets.deactivate_intern(intern_id)
    return jsonify({"status": "deactivated", "intern_id": intern_id})
