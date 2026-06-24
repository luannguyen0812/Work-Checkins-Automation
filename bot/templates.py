def morning_reminder(cutoff_time: str = "17:00") -> str:
    return (
        f"☀️ Good morning, interns! Day has started.\n\n"
        f"Please send your \"I'm online\" check-in message here to be marked present.\n"
        f"Cutoff: {cutoff_time} EDT. Early check-ins appreciated!\n\n"
        f"[Auto-reminder — reply in this chat to check in]"
    )


def second_reminder() -> str:
    return (
        "🔔 Reminder: If you haven't checked in yet, please do so now!\n\n"
        "Still waiting on a few of you. Just type \"I'm online\" or \"checking in\" here. ✅"
    )


def precut_reminder(cutoff_time: str = "17:00") -> str:
    return (
        f"⏰ Heads up — check-in cutoff is at {cutoff_time} EDT (15 minutes away).\n\n"
        f"If you haven't sent your check-in yet, please do so NOW to be marked present today."
    )


def dm_nudge(first_name: str, checkin_count: int, total_days: int, rate_pct: int, cutoff_time: str = "17:00") -> str:
    return (
        f"Hi {first_name} 👋\n\n"
        f"Just a quick reminder — you haven't checked in to the intern group today yet.\n\n"
        f"Please head over to the group and send a quick \"I'm online\" message before {cutoff_time} EDT.\n\n"
        f"Your current attendance this week: {checkin_count}/{total_days} days ({rate_pct}%)\n\n"
        f"Thanks!\n— Check-In Bot"
    )


def weekly_report_dm(
    week_number: int,
    date_range: str,
    total_interns: int,
    avg_rate: float,
    red_count: int,
    red_names: str,
    amber_count: int,
    amber_names: str,
    timestamp: str,
) -> str:
    return (
        f"📊 Weekly Intern Attendance Report — Week {week_number} ({date_range})\n\n"
        f"Total interns: {total_interns}\n"
        f"Average attendance rate: {avg_rate:.1f}%\n\n"
        f"🔴 RED risk ({red_count} interns): {red_names}\n"
        f"🟡 AMBER risk ({amber_count} interns): {amber_names}\n\n"
        f"Full Excel report attached. Executive summary included on Sheet 1.\n\n"
        f"Generated: {timestamp} EDT"
    )


def opt_out_confirmation(first_name: str, retention_weeks: int = 12) -> str:
    return (
        f"Hi {first_name},\n\n"
        f"You've been marked as opted out of daily check-in reminders. Your data will be retained "
        f"per policy ({retention_weeks} weeks) then deleted.\n\n"
        f"To opt back in, contact your program manager."
    )


def unknown_user_attempt() -> str:
    return (
        "Hi! It looks like you tried to check in, but I don't have you in my intern roster.\n\n"
        "If you're an intern, please ask your program manager to add you. "
        "If this was a mistake, no action needed."
    )
