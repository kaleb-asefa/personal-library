from email.message import EmailMessage

import aiosmtplib
from app.config import settings

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

async def send_email(
        to_email: str,
        subject: str,
        plain_text_content: str,
        html_content: str,
):
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(plain_text_content)

    if html_content:
        message.add_alternative(html_content, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username,
        password=settings.mail_password.get_secret_value(),
        start_tls=settings.mail_use_tls,
    )
