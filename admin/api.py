import os
from datetime import timedelta
from flask import Flask, jsonify, request, abort, render_template, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from admin.auth import get_user_by_id, get_user_by_username, get_all_users, create_user, delete_user, ensure_default_admin
from datastore import sheets
from datastore.queries import compute_all_risk_scores
from utils.time_utils import edt_now

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = ""


@login_manager.user_loader
def load_user(uid):
    return get_user_by_id(uid)


def _require_api_auth():
    token = request.headers.get("Authorization", "")
    if token != f"Bearer {os.environ.get('ADMIN_API_SECRET', '')}":
        abort(401)


def _now_str():
    return edt_now().strftime("%a, %b %d %Y · %I:%M %p EDT")


def _week_labels_and_trend():
    now = edt_now()
    labels, data = [], []
    for i in range(7, -1, -1):
        w = now - timedelta(weeks=i)
        labels.append(f"Week {w.isocalendar().week}")
        data.append(0)
    return labels, data


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("login.html", error=None)


@app.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = get_user_by_username(username)
    if not user or not user.check_password(password):
        return render_template("login.html", error="Invalid username or password.")
    login_user(user, remember=True)
    return redirect(request.args.get("next") or url_for("dashboard"))


@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ── HTML Pages ────────────────────────────────────────────────────────────────

@app.get("/")
@login_required
def index():
    return redirect(url_for("dashboard"))


@app.get("/dashboard")
@login_required
def dashboard():
    now = edt_now()
    week_num = now.isocalendar().week
    week_labels, trend_data = _week_labels_and_trend()

    try:
        all_interns = sheets.get_all_interns()
        todays = sheets.get_checkins_for_date(now.date())
        checked_ids = {c.intern_id for c in todays}
        active = [i for i in all_interns if i.active]
        total_interns = len(active)
        checked_in_today = sum(1 for i in active if i.intern_id in checked_ids)
        missing_count = total_interns - checked_in_today
        missing_today = [
            {
                "name": i.full_name,
                "initials": "".join(p[0].upper() for p in i.full_name.split()[:2]),
                "username": f"@{i.telegram_username}" if i.telegram_username else "—",
                "risk": "RED",
            }
            for i in active if i.intern_id not in checked_ids
        ]
    except NotImplementedError:
        total_interns = checked_in_today = missing_count = 0
        missing_today = []

    try:
        scores = compute_all_risk_scores(week_num, now.year)
        risk = {
            "green": sum(1 for s in scores if s.risk_band == "GREEN"),
            "amber": sum(1 for s in scores if s.risk_band == "AMBER"),
            "red":   sum(1 for s in scores if s.risk_band == "RED"),
        }
        avg_rate = round(sum(s.war for s in scores) / len(scores) * 100, 1) if scores else 0
    except NotImplementedError:
        risk = {"green": 0, "amber": 0, "red": 0}
        avg_rate = 0

    return render_template("dashboard.html",
        active="dashboard", now=_now_str(),
        total_interns=total_interns, checked_in_today=checked_in_today,
        missing_count=missing_count, missing_today=missing_today,
        risk=risk, avg_rate=avg_rate,
        week_labels=week_labels, trend_data=trend_data,
    )


@app.get("/interns")
@login_required
def interns_page():
    now = edt_now()
    week_num = now.isocalendar().week

    try:
        all_interns = sheets.get_all_interns()
        scores_map = {}
        try:
            for s in compute_all_risk_scores(week_num, now.year):
                scores_map[s.intern_id] = s
        except NotImplementedError:
            pass

        rows = []
        for i in [x for x in all_interns if x.active]:
            s = scores_map.get(i.intern_id)
            rows.append({
                "name": i.full_name,
                "initials": "".join(p[0].upper() for p in i.full_name.split()[:2]),
                "role": getattr(i, "notes", "") or "Intern",
                "days": ["absent"] * 5,
                "rate": round(s.war * 100) if s else 0,
                "risk": s.risk_band if s else "GREEN",
                "streak": s.cas if s else 0,
            })
        rows.sort(key=lambda x: x["rate"])
    except NotImplementedError:
        rows = []

    return render_template("interns.html", active="interns", now=_now_str(), interns=rows)


@app.get("/risk-report")
@login_required
def risk_report():
    now = edt_now()
    week_num = now.isocalendar().week
    risk = {"green": 0, "amber": 0, "red": 0}
    scores = []
    try:
        scores = sorted(compute_all_risk_scores(week_num, now.year), key=lambda s: s.risk_score)
        risk = {
            "green": sum(1 for s in scores if s.risk_band == "GREEN"),
            "amber": sum(1 for s in scores if s.risk_band == "AMBER"),
            "red":   sum(1 for s in scores if s.risk_band == "RED"),
        }
    except NotImplementedError:
        pass
    return render_template("risk_report.html",
        active="risk", now=_now_str(),
        risk=risk, scores=scores, week_number=week_num,
    )


@app.get("/weekly-data")
@login_required
def weekly_data():
    week_labels, trend_data = _week_labels_and_trend()
    return render_template("weekly_data.html",
        active="weekly", now=_now_str(),
        week_labels=week_labels, trend_data=trend_data,
        weekly_rows=[],
    )


@app.get("/settings")
@login_required
def settings():
    config = None
    try:
        cfg = sheets.get_config()
        config = cfg.model_dump()
    except NotImplementedError:
        pass

    user_error = session.pop("user_error", None)
    user_success = session.pop("user_success", None)

    return render_template("settings.html",
        active="settings", now=_now_str(),
        users=get_all_users(), config=config,
        user_error=user_error, user_success=user_success,
    )


@app.post("/settings/users/add")
@login_required
def add_user():
    try:
        create_user(
            username=request.form["username"].strip(),
            password=request.form["password"],
            role=request.form.get("role", "viewer"),
            display_name=request.form["display_name"].strip(),
        )
        session["user_success"] = f"Account '{request.form['username']}' created."
    except ValueError as e:
        session["user_error"] = str(e)
    return redirect(url_for("settings"))


@app.post("/settings/users/delete/<uid>")
@login_required
def remove_user(uid):
    if uid == current_user.id:
        session["user_error"] = "You can't delete your own account."
    else:
        delete_user(uid)
    return redirect(url_for("settings"))


@app.get("/audit-log")
@login_required
def audit_log():
    events = []
    try:
        raw = sheets.get_all_interns()  # placeholder — will use get_escalations()
    except NotImplementedError:
        pass
    return render_template("audit_log.html", active="audit", now=_now_str(), events=events)


# ── JSON API (bearer token) ───────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": edt_now().isoformat()})


@app.get("/api/status")
def api_status():
    _require_api_auth()
    raise NotImplementedError


@app.post("/api/config")
def api_config():
    _require_api_auth()
    body = request.get_json(force=True)
    sheets.update_config_key(body["key"], body["value"])
    return jsonify(sheets.get_config().model_dump())


@app.post("/api/report/run")
def api_report():
    _require_api_auth()
    raise NotImplementedError


@app.get("/api/interns")
def api_interns():
    _require_api_auth()
    return jsonify([i.model_dump() for i in sheets.get_all_interns()])


@app.post("/api/interns/<intern_id>/opt-out")
def api_opt_out(intern_id):
    _require_api_auth()
    sheets.deactivate_intern(intern_id)
    return jsonify({"status": "deactivated", "intern_id": intern_id})
