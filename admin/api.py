import os
from flask import Flask, jsonify, request, abort, render_template, redirect, url_for
from datastore import sheets
from datastore.queries import compute_all_risk_scores
from utils.time_utils import edt_now

app = Flask(__name__)


def _require_auth():
    token = request.headers.get("Authorization", "")
    if token != f"Bearer {os.environ.get('ADMIN_API_SECRET', '')}":
        abort(401)


@app.get("/")
def index():
    return redirect(url_for("dashboard"))


@app.get("/dashboard")
def dashboard():
    now = edt_now()
    week_num = now.isocalendar().week
    year = now.year

    # Safe data fetch — gracefully handles unimplemented stubs
    try:
        all_interns = sheets.get_all_interns()
        todays_checkins = sheets.get_checkins_for_date(now.date())
        checked_ids = {c.intern_id for c in todays_checkins}
        missing_today = [i.full_name for i in all_interns if i.active and i.intern_id not in checked_ids]
        total_interns = sum(1 for i in all_interns if i.active)
        checked_in_today = total_interns - len(missing_today)

        try:
            risk_scores = compute_all_risk_scores(week_num, year)
            risk = {
                "green": sum(1 for r in risk_scores if r.risk_band == "GREEN"),
                "amber": sum(1 for r in risk_scores if r.risk_band == "AMBER"),
                "red":   sum(1 for r in risk_scores if r.risk_band == "RED"),
            }
            avg_rate = round(
                sum(r.war for r in risk_scores) / len(risk_scores) * 100, 1
            ) if risk_scores else 0
            intern_rows = [
                {
                    "name": r.full_name,
                    "days": ["absent"] * 5,  # populated by sheets impl
                    "rate": round(r.war * 100),
                    "risk": r.risk_band,
                }
                for r in sorted(risk_scores, key=lambda x: x.risk_score)
            ]
        except NotImplementedError:
            risk = {"green": 0, "amber": 0, "red": 0}
            avg_rate = 0
            intern_rows = []

    except NotImplementedError:
        total_interns = 0
        checked_in_today = 0
        missing_today = []
        risk = {"green": 0, "amber": 0, "red": 0}
        avg_rate = 0
        intern_rows = []

    # Week date range Mon–Fri
    from datetime import timedelta
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)
    date_range = f"{monday.strftime('%b %d')} – {friday.strftime('%b %d, %Y')}"

    return render_template(
        "dashboard.html",
        bot_online=True,
        week_number=week_num,
        date_range=date_range,
        generated_at=now.strftime("%H:%M EDT"),
        total_interns=total_interns,
        checked_in_today=checked_in_today,
        missing_count=len(missing_today),
        missing_today=missing_today,
        avg_rate=avg_rate,
        risk=risk,
        interns=intern_rows,
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": edt_now().isoformat()})


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
