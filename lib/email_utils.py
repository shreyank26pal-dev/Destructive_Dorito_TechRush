"""
Email utility for Dorito Vault — shared between Section A and Section B.
Uses Resend API if RESEND_API_KEY is configured in .env, otherwise logs to console
for local development convenience.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("email_utils")

def send_email(to_email: str = None, subject: str = "", body: str = "", to: str = None, html: str = "") -> dict:
    """
    Sends an email using Resend API if API key is provided, or logs to console.
    Flexible signature accepts (to_email, subject, body) or (to=..., subject=..., html=...).
    """
    recipient = to_email or to
    email_body = body or html

    if not recipient:
        return {"success": False, "message": "No recipient email provided"}

    # Always print to terminal console for local development testing (ASCII safe)
    print("\n" + "="*60)
    print(f"[LOCAL DEV EMAIL] To: {recipient}")
    print(f"Subject: {subject}")
    print(f"Content: {email_body}")
    print("="*60 + "\n")


    resend_key = os.getenv("RESEND_API_KEY")
    
    if resend_key and resend_key != "your_key_here":
        try:
            import resend
            resend.api_key = resend_key
            
            sender_email = os.getenv("SENDER_EMAIL", "Dorito Vault Security <onboarding@resend.dev>")
            params = {
                "from": sender_email,
                "to": [recipient],
                "subject": subject,
                "html": email_body if email_body.startswith("<") else f"<p>{email_body}</p>",
            }
            email = resend.Emails.send(params)
            logger.info(f"Email sent via Resend to {recipient}: {email}")
            return {"success": True, "method": "resend", "id": email.get("id") if isinstance(email, dict) else str(email)}
        except Exception as e:
            logger.error(f"Resend error: {e}")
            
    return {"success": True, "method": "console", "message": f"Dev email logged to terminal for {recipient}"}

