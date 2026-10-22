
import smtplib
from email.message import EmailMessage

import streamlit as st


def send_otp_email(recipient_email, otp, purpose):
    mail = st.secrets["mail"]

    purpose_messages = {
        "REGISTER": "verify your email address",
        "LOGIN": "sign in to SupportIQ",
        "RESET_PASSWORD": "reset your SupportIQ password",
    }

    if purpose not in purpose_messages:
        raise ValueError("Invalid email OTP purpose.")

    message = EmailMessage()
    message["Subject"] = "Your SupportIQ verification code"
    message["From"] = mail["sender_email"]
    message["To"] = recipient_email
    message.set_content(
        f"""Hello,

Your SupportIQ OTP is: {otp}

Use this code to {purpose_messages[purpose]}.
This code expires in 10 minutes.

If you did not request this code, you can ignore this email.

SupportIQ Team
"""
    )

    with smtplib.SMTP(
        mail["smtp_server"],
        int(mail["smtp_port"]),
        timeout=15,
    ) as server:
        server.starttls()
        server.login(mail["smtp_username"], mail["smtp_password"])
        server.send_message(message)
