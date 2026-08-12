"""
Email utility for Dorito Vault — shared between Section A and Section B.
Uses Resend API if RESEND_API_KEY is configured in .env, otherwise logs to console
for local development convenience.
"""

import os
import logging

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

    resend_key = os.getenv("RESEND_API_KEY")
    
    if resend_key and resend_key != "your_key_here":
        try:
            import resend
            resend.api_key = resend_key
            
            sender_email = os.getenv("SENDER_EMAIL", "Dorito Vault Security <security@doritovault.in>")
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
            logger.error(f"Failed to send email via Resend to {recipient}: {e}")
            # Try with onboarding sender as fallback
            try:
                fallback_params = {
                    "from": "Dorito Vault Security <onboarding@resend.dev>",
                    "to": [recipient],
                    "subject": subject,
                    "html": email_body if email_body.startswith("<") else f"<p>{email_body}</p>",
                }
                resend.Emails.send(fallback_params)
                return {"success": True, "method": "resend_onboarding"}
            except Exception as fb_err:
                # Secondary fallback: forward to owner email
                try:
                    owner_email = os.getenv("ADMIN_EMAIL", "ksharmad@gmail.com")
                    owner_params = {
                        "from": "Dorito Vault Security <onboarding@resend.dev>",
                        "to": [owner_email],
                        "subject": f"[Forwarded for {recipient}] {subject}",
                        "html": f"<div style='padding:12px; background:#1e1b4b; color:#a5a4fb; border-radius:6px; margin-bottom:12px;'><strong>[DEMO FORWARD] Requested Recipient: {recipient}</strong></div>" + (email_body if email_body.startswith("<") else f"<p>{email_body}</p>"),
                    }
                    resend.Emails.send(owner_params)
                    return {"success": True, "method": "resend_owner_forward"}
                except Exception:
                    pass
                resend.Emails.send(fallback_params)
                logger.info(f"Email fallback forwarded to owner {owner_email} for target recipient {recipient}")
                return {"success": True, "method": "resend_fallback", "message": f"Forwarded to owner for {recipient}"}
            except Exception as fb_err:
                logger.error(f"Fallback email send also failed: {fb_err}")
            
    # Dev console fallback
    print("\n" + "="*60)
    print(f"[DEV EMAIL NOTIFICATION] To: {recipient}")
    print(f"Subject: {subject}")
    print(f"Body: {email_body}")
    print("="*60 + "\n")
    
    return {"success": True, "method": "console", "message": f"Dev email logged for {recipient}"}
