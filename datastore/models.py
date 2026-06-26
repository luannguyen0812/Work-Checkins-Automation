from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class Intern(BaseModel):
    intern_id: str
    full_name: str
    telegram_user_id: int
    telegram_username: Optional[str] = None
    cohort: str
    start_date: date
    end_date: date
    active: bool = True
    email: Optional[str] = None
    notes: Optional[str] = None
    schedule_json: Optional[str] = None  # JSON: list of {days, start, end} segments in ET
    schedule_raw: Optional[str] = None   # raw col E text — used to detect Team Members changes


class CheckIn(BaseModel):
    date: date
    intern_id: str
    telegram_user_id: int
    full_name: str
    checkin_timestamp_utc: datetime
    checkin_timestamp_edt: datetime
    message_text: str
    message_id: int
    validated: bool
    late: bool
    week_number: int


class Config(BaseModel):
    checkin_cutoff_time: str = "17:00"
    morning_reminder_time: str = "09:30"
    second_reminder_time: str = "11:30"
    dm_nudge_time: str = "13:00"
    precut_reminder_time: str = "17:45"
    report_day: int = 4
    report_time: str = "18:00"
    risk_amber_threshold: float = 0.70
    risk_red_threshold: float = 0.50
    streak_concern_days: int = 3
    retention_weeks: int = 12
    admin_telegram_id: Optional[int] = None
    admin_email: str = "minhluan081294@gmail.com"
    group_chat_id: Optional[int] = None


class Escalation(BaseModel):
    date: date
    intern_id: str
    trigger: str
    action_taken: str
    resolved_date: Optional[date] = None
    notes: Optional[str] = None


class RiskScore(BaseModel):
    intern_id: str
    full_name: str
    war: float   # weekly attendance rate
    rar: float   # 4-week rolling attendance rate
    cas: int     # current consecutive absence streak
    lcr: float   # late check-in rate this week
    risk_score: float
    risk_band: str  # GREEN | AMBER | RED
