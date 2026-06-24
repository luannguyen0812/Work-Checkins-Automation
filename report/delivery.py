import os
import smtplib
from email.message import EmailMessage


async def send_report_telegram(bot, report_bytes: bytes, filename: str, caption: str) -> None:
    admin_id = int(os.environ["ADMIN_TELEGRAM_USER_ID"])
    from io import BytesIO
    await bot.send_document(
        chat_id=admin_id,
        document=BytesIO(report_bytes),
        filename=filename,
        caption=caption,
    )


def send_report_email(report_bytes: bytes, filename: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["REPORT_RECIPIENT_EMAIL"]
    msg.set_content(body)
    msg.add_attachment(report_bytes, maintype="application", subtype="octet-stream", filename=filename)

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)
