import os
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from flask import Flask, jsonify, request, abort, render_template, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from admin.auth import get_user_by_id, get_user_by_username, get_all_users, create_user, delete_user
from datastore import sheets
from datastore.sheets import get_source_team_members
from datastore.queries import compute_all_risk_scores
from utils.time_utils import edt_now, scheduled_weekdays, is_us_public_holiday

AVATAR_COLORS = [
    "bg-blue-600", "bg-green-600", "bg-purple-600", "bg-orange-500",
    "bg-pink-600", "bg-teal-600", "bg-indigo-600", "bg-cyan-600",
    "bg-rose-600", "bg-violet-600",
]


def _demo_seed(name: str, offset: int = 0) -> float:
    h = int(hashlib.md5(f"{name}{offset}".encode()).hexdigest()[:8], 16)
    return (h % 10000) / 10000.0

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
    try:
        active_interns = [i for i in sheets.get_all_interns() if i.active]
        intern_count = len(active_interns) or 1
    except Exception:
        active_interns = []
        intern_count = 1
    for i in range(7, -1, -1):
        w = now - timedelta(weeks=i)
        iso = w.isocalendar()
        labels.append(f"Wk {iso.week}")
        if active_interns:
            try:
                ci = sheets.get_checkins_for_week(iso.week, iso.year)
                validated = {c.intern_id for c in ci if c.validated}
                rate = round(len(validated) / intern_count * 100)
            except Exception:
                rate = 0
        else:
            rate = 0
        data.append(rate)
    return labels, data


def _week_monday(week: int, year: int):
    """Return the Monday date for a given ISO week + year."""
    from datetime import date
    jan4 = date(year, 1, 4)
    iso_start = jan4 - timedelta(days=jan4.isoweekday() - 1)
    return iso_start + timedelta(weeks=week - 1)


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
    week_num, year = now.isocalendar().week, now.year

    # Real attendance: how many days checked in vs working days elapsed this week
    monday = (now - timedelta(days=now.weekday())).date()
    days_elapsed = sum(1 for i in range(5) if (monday + timedelta(days=i)) <= now.date())
    days_elapsed = max(days_elapsed, 1)

    roster = {i.full_name.lower(): i for i in sheets.get_all_interns() if i.active}
    week_checkins = sheets.get_checkins_for_week(week_num, year)
    checked_days: dict[str, int] = {}
    for c in week_checkins:
        if c.validated:
            checked_days[c.intern_id] = checked_days.get(c.intern_id, 0) + 1

    members = get_source_team_members()
    rows = []
    for idx, m in enumerate(members):
        name = m.get("Full Name", "").strip()
        if not name:
            continue
        email = m.get("Google Account", "—").strip()
        intern = roster.get(name.lower())
        if intern:
            attendance = round(checked_days.get(intern.intern_id, 0) / days_elapsed * 100)
        else:
            attendance = 0
        risk_level = "GREEN" if attendance >= 75 else ("AMBER" if attendance >= 55 else "RED")
        rows.append({
            "row_num": len(rows) + 1,
            "name": name,
            "initials": "".join(p[0].upper() for p in name.split()[:2]),
            "email": email,
            "username": "@" + email.split("@")[0] if "@" in email else "—",
            "role": m.get("Role", "—").strip(),
            "department": m.get("Team/Department", "—").strip(),
            "shift": m.get("Preferred Shift | Interns Hours", "—").strip(),
            "inducted": m.get("Induction Y/N", "").strip().upper() == "Y",
            "color": AVATAR_COLORS[idx % len(AVATAR_COLORS)],
            "attendance": attendance,
            "risk_level": risk_level,
            "score": max(0, 100 - attendance),
        })
    return render_template("interns.html", active="interns", now=_now_str(), interns=rows)


@app.get("/risk-report")
@login_required
def risk_report():
    now = edt_now()
    week_num = now.isocalendar().week
    risk = {"green": 0, "amber": 0, "red": 0}
    scores = []
    demo = False
    try:
        raw = sorted(compute_all_risk_scores(week_num, now.year), key=lambda s: s.risk_score, reverse=True)
        intern_map = {i.intern_id: i for i in sheets.get_all_interns()}
        for idx, s in enumerate(raw):
            intern = intern_map.get(s.intern_id)
            username = f"@{intern.telegram_username}" if intern and intern.telegram_username else "—"
            scores.append(SimpleNamespace(
                full_name=s.full_name,
                username=username,
                initials="".join(p[0].upper() for p in s.full_name.split()[:2]),
                color=AVATAR_COLORS[idx % len(AVATAR_COLORS)],
                attendance=round(s.war * 100),
                max_consec_gap=s.cas,
                risk_score=s.risk_score,
                risk_band=s.risk_band,
            ))
    except Exception:
        demo = True
    risk = {
        "green": sum(1 for s in scores if s.risk_band == "GREEN"),
        "amber": sum(1 for s in scores if s.risk_band == "AMBER"),
        "red":   sum(1 for s in scores if s.risk_band == "RED"),
    }
    return render_template("risk_report.html",
        active="risk", now=_now_str(),
        risk=risk, scores=scores, week_number=week_num, demo=demo,
    )


@app.get("/weekly-data")
@login_required
def weekly_data():
    now = edt_now()
    current_iso = now.isocalendar()

    try:
        sel_week = int(request.args.get("week", current_iso.week))
        sel_year = int(request.args.get("year", current_iso.year))
    except (ValueError, TypeError):
        sel_week, sel_year = current_iso.week, current_iso.year

    is_current = (sel_week == current_iso.week and sel_year == current_iso.year)

    monday = _week_monday(sel_week, sel_year)
    days = [monday + timedelta(days=i) for i in range(7)]
    day_headers = [d.strftime("%a %b %d") for d in days]

    prev_monday = monday - timedelta(weeks=1)
    prev_iso = prev_monday.isocalendar()
    next_monday = monday + timedelta(weeks=1)
    next_iso = next_monday.isocalendar()
    can_go_next = next_monday <= now.date()

    week_checkins = sheets.get_checkins_for_week(sel_week, sel_year)
    checked_set = {(c.intern_id, c.date) for c in week_checkins if c.validated}
    active_interns = [i for i in sheets.get_all_interns() if i.active]

    heatmap = []
    for idx, intern in enumerate(active_interns):
        allowed = scheduled_weekdays(intern)
        row_days = []
        for d in days:
            if d.weekday() not in allowed or is_us_public_holiday(d):
                row_days.append("na")          # not scheduled or holiday → hyphen, excluded from rate
            elif is_current and d > now.date():
                row_days.append(None)          # future scheduled day → pending
            else:
                row_days.append((intern.intern_id, d) in checked_set)
        present = sum(1 for v in row_days if v is True)
        applicable = sum(1 for v in row_days if v is True or v is False)
        rate = round(present / applicable * 100) if applicable else 0
        heatmap.append({
            "name": intern.full_name,
            "initials": "".join(p[0].upper() for p in intern.full_name.split()[:2]),
            "color": AVATAR_COLORS[idx % len(AVATAR_COLORS)],
            "days": row_days,
            "rate": rate,
            "scheduled_count": len(allowed),
        })

    week_label = f"Week {sel_week} · {monday.strftime('%b %d')} – {days[-1].strftime('%b %d, %Y')}"
    week_labels, trend_data = _week_labels_and_trend()

    return render_template("weekly_data.html",
        active="weekly", now=_now_str(),
        week_labels=week_labels, trend_data=trend_data,
        heatmap=heatmap, day_headers=day_headers,
        week_label=week_label, weekly_rows=[], demo=False,
        is_current=is_current,
        prev_week=prev_iso.week, prev_year=prev_iso.year,
        next_week=next_iso.week, next_year=next_iso.year,
        can_go_next=can_go_next,
        sel_week=sel_week, sel_year=sel_year,
        current_week=current_iso.week, current_year=current_iso.year,
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
    try:
        ss = sheets._get_spreadsheet()
        ws = ss.worksheet("ESCALATIONS")
        records = ws.get_all_records()
        events = []
        for r in records:
            events.append({
                "ts":    str(r.get("date", "") or r.get("timestamp", "")),
                "type":  str(r.get("trigger", "EVENT")).upper(),
                "badge": str(r.get("trigger", "event")).lower(),
                "actor": str(r.get("action_taken", "System") or "System"),
                "desc":  str(r.get("notes", "") or r.get("intern_id", "")),
            })
        events = list(reversed(events))
    except Exception:
        events = []
    return render_template("audit_log.html", active="audit", now=_now_str(), events=events)


# ── JSON API (bearer token) ───────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": edt_now().isoformat()})


@app.get("/api/status")
def api_status():
    _require_api_auth()
    now = edt_now()
    all_interns = sheets.get_all_interns()
    active = [i for i in all_interns if i.active]
    todays = sheets.get_checkins_for_date(now.date())
    checked_ids = {c.intern_id for c in todays}
    return jsonify({
        "status": "ok",
        "time": now.isoformat(),
        "total_interns": len(active),
        "checked_in_today": sum(1 for i in active if i.intern_id in checked_ids),
        "missing_today": len(active) - sum(1 for i in active if i.intern_id in checked_ids),
        "week_number": now.isocalendar().week,
    })


@app.post("/api/config")
def api_config():
    _require_api_auth()
    body = request.get_json(force=True)
    sheets.update_config_key(body["key"], body["value"])
    return jsonify(sheets.get_config().model_dump())


@app.post("/settings/config")
@login_required
def settings_config():
    """Session-authenticated batch config update for the dashboard UI."""
    body = request.get_json(force=True)
    for key, value in body.items():
        sheets.update_config_key(key, str(value))
    return jsonify({"ok": True, "config": sheets.get_config().model_dump()})


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
