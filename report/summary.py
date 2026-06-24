import os
import anthropic

SYSTEM_PROMPT = (
    "You are an operations analyst writing a concise executive summary of intern attendance data. "
    "Your audience is a program manager who needs to act on this information. "
    "Write in plain, direct prose. No bullet points. Maximum 200 words. "
    "Always end with 1-2 specific recommended next steps."
)

USER_PROMPT_TEMPLATE = (
    "Week {week_number} ({date_range}) — {total_interns} interns tracked.\n\n"
    "Cohort average attendance: {avg_rate}%\n"
    "Risk distribution: {green_count} GREEN, {amber_count} AMBER, {red_count} RED\n\n"
    "Top at-risk interns (RED):\n{red_interns_table}\n\n"
    "Notable trends:\n- {trend_notes}\n\n"
    "Write a 150–200 word executive summary highlighting patterns, concerns, and recommended actions."
)


def generate_narrative(**kwargs) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_SUMMARY_MODEL", "claude-haiku-4-5-20251001")

    response = client.messages.create(
        model=model,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": USER_PROMPT_TEMPLATE.format(**kwargs)}],
    )
    return response.content[0].text
