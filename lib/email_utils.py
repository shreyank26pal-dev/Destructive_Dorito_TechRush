"""
Email utility for Dorito Vault — shared between Section A and Section B.
Uses Resend API if RESEND_API_KEY is configured in .env, otherwise logs to console
for local development convenience.
"""

import os
import sys
import logging
from dotenv import load_dotenv

logger = logging.getLogger("email_utils")

def send_email(to_email: str = None, subject: str = "", body: str = "", to: str = None, html: str = "") -> dict:
    """
    Sends an email using Resend API if API key is provided, or logs to console.
    Flexible signature accepts (to_email, subject, body) or (to=..., subject=..., html=...).
    """
    # Reload environment to pick up freshly pasted API keys without restarting
    load_dotenv(override=True)
    
    recipient = to_email or to
    email_body = body or html

    if not recipient:
        return {"success": False, "message": "No recipient email provided"}

    # Always log to terminal console for local visibility
    print("\n" + "="*60)
    print(f"[TRANSACTIONAL EMAIL DISPATCH] To: {recipient}")
    print(f"Subject: {subject}")
    print(f"Content: {email_body}")
    print("="*60 + "\n")
    sys.stdout.flush()

    resend_key = os.getenv("RESEND_API_KEY")
    
    if resend_key and resend_key != "your_key_here" and not resend_key.startswith("your_"):
        try:
            import resend
            resend.api_key = resend_key
            
            configured_sender = os.getenv("SENDER_EMAIL", "Dorito Vault Security <security@doritovault.in>")
            senders_to_try = [
                configured_sender,
                "Dorito Vault Security <security@doritovault.in>",
                "Dorito Vault Security <security@send.doritovault.in>",
                "Dorito Vault Security <onboarding@resend.dev>"
            ]
            # Deduplicate while preserving order
            senders_to_try = list(dict.fromkeys(senders_to_try))


            last_error = None
            for sender in senders_to_try:
                try:
                    params = {
                        "from": sender,
                        "to": [recipient],
                        "subject": subject,
                        "html": email_body if email_body.startswith("<") else f"<p>{email_body}</p>",
                    }
                    email_result = resend.Emails.send(params)
                    email_id = email_result.get("id") if isinstance(email_result, dict) else getattr(email_result, "id", str(email_result))
                    print(f" [RESEND DELIVERED] Email successfully sent to {recipient} via {sender}! ID: {email_id}")
                    sys.stdout.flush()
                    return {"success": True, "method": "resend", "id": email_id}
                except Exception as send_err:
                    last_error = send_err
                    print(f" [RESEND SENDER ERROR with {sender}]: {send_err}")
                    sys.stdout.flush()

            if last_error:
                print(f"\n [RESEND FAILURE]: {last_error}\n")
                sys.stdout.flush()
                return {"success": False, "method": "resend_failed", "error": str(last_error)}
        except Exception as e:
            print(f" [RESEND UNHANDLED ERROR]: {e}")
            sys.stdout.flush()
            
    return {"success": True, "method": "console", "message": f"Dev email logged to terminal for {recipient}"}


