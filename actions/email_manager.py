"""
EVA Email Manager — Read, compose, and send emails by voice.
Supports Gmail (IMAP/SMTP) with App Password authentication.
"""

import email
import imaplib
import logging
import smtplib
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.email_manager")


def _get_credentials() -> tuple[str, str]:
    """Get email credentials from config."""
    from memory.config_manager import config
    addr = config.get("email_address", "")
    pwd = config.get("email_app_password", "")
    return addr, pwd


def _decode_subject(raw_subject) -> str:
    """Decode an email subject header."""
    if raw_subject is None:
        return "(No subject)"
    decoded_parts = decode_header(raw_subject)
    parts = []
    for data, charset in decoded_parts:
        if isinstance(data, bytes):
            parts.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(data))
    return " ".join(parts)


def _decode_body(msg) -> str:
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")[:1000]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")[:1000]
    return "(Could not extract body)"


def _detect_provider(addr: str) -> tuple[str, int, str, int]:
    """Detect IMAP/SMTP servers from email address."""
    domain = addr.split("@")[-1].lower()
    providers = {
        "gmail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 587),
        "outlook.com": ("imap-mail.outlook.com", 993, "smtp-mail.outlook.com", 587),
        "hotmail.com": ("imap-mail.outlook.com", 993, "smtp-mail.outlook.com", 587),
        "yahoo.com": ("imap.mail.yahoo.com", 993, "smtp.mail.yahoo.com", 587),
        "icloud.com": ("imap.mail.me.com", 993, "smtp.mail.me.com", 587),
    }
    return providers.get(domain, (f"imap.{domain}", 993, f"smtp.{domain}", 587))


@register_tool(
    name="manage_email",
    description="Read, search, compose, and send emails. "
                "Actions: read (latest emails), search (find by keyword), "
                "send (compose and send), count (unread count). "
                "Requires email_address and email_app_password in settings.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: read | search | send | count",
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of emails to read (default: 3, max: 10)",
            },
            "query": {
                "type": "STRING",
                "description": "Search keyword for search action (searches subject lines)",
            },
            "to": {
                "type": "STRING",
                "description": "Recipient email address for send action",
            },
            "subject": {
                "type": "STRING",
                "description": "Email subject for send action",
            },
            "body": {
                "type": "STRING",
                "description": "Email body text for send action",
            },
        },
        "required": ["action"],
    },
    category="communication",
)
def manage_email(
    action: str,
    count: int = 3,
    query: str = "",
    to: str = "",
    subject: str = "",
    body: str = "",
) -> str:
    """Manage emails — read, search, send, or count unread."""
    addr, pwd = _get_credentials()
    if not addr or not pwd:
        return (
            "Email not configured. Please add your email_address and "
            "email_app_password in Settings → API Keys. "
            "For Gmail, use an App Password (not your regular password)."
        )

    action = action.lower().strip()
    imap_host, imap_port, smtp_host, smtp_port = _detect_provider(addr)

    # ── Read latest emails ──────────────────────────────────────
    if action == "read":
        count = min(max(count, 1), 10)
        try:
            imap = imaplib.IMAP4_SSL(imap_host, imap_port)
            imap.login(addr, pwd)
            imap.select("INBOX")

            _, msg_ids = imap.search(None, "ALL")
            ids = msg_ids[0].split()
            if not ids:
                imap.logout()
                return "Your inbox is empty."

            latest = ids[-count:]
            latest.reverse()  # newest first

            results = []
            for mid in latest:
                _, data = imap.fetch(mid, "(RFC822)")
                raw = data[0][1]
                msg = email.message_from_bytes(raw)
                subj = _decode_subject(msg.get("Subject"))
                sender = msg.get("From", "Unknown")
                date_str = msg.get("Date", "Unknown date")
                # Truncate sender
                if "<" in sender:
                    sender_name = sender.split("<")[0].strip().strip('"')
                    if sender_name:
                        sender = sender_name
                body_preview = _decode_body(msg)[:200]
                results.append(
                    f"📧 From: {sender}\n"
                    f"   Subject: {subj}\n"
                    f"   Date: {date_str}\n"
                    f"   Preview: {body_preview}..."
                )

            imap.logout()
            header = f"Latest {len(results)} email(s):\n\n"
            return header + "\n\n".join(results)

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
            return f"Email login failed: {e}. Check your credentials."
        except Exception as e:
            logger.error(f"Email read failed: {e}")
            return f"Failed to read emails: {e}"

    # ── Search emails ───────────────────────────────────────────
    elif action == "search":
        if not query:
            return "What should I search for? Give me a keyword or sender name."
        try:
            imap = imaplib.IMAP4_SSL(imap_host, imap_port)
            imap.login(addr, pwd)
            imap.select("INBOX")

            # Search subject and from
            _, msg_ids = imap.search(None, f'(OR SUBJECT "{query}" FROM "{query}")')
            ids = msg_ids[0].split()

            if not ids:
                imap.logout()
                return f"No emails found matching '{query}'."

            latest = ids[-5:]  # last 5 matches
            latest.reverse()

            results = []
            for mid in latest:
                _, data = imap.fetch(mid, "(RFC822)")
                raw = data[0][1]
                msg = email.message_from_bytes(raw)
                subj = _decode_subject(msg.get("Subject"))
                sender = msg.get("From", "Unknown")
                if "<" in sender:
                    sender_name = sender.split("<")[0].strip().strip('"')
                    if sender_name:
                        sender = sender_name
                results.append(f"📧 {sender}: {subj}")

            imap.logout()
            return f"Found {len(results)} email(s) matching '{query}':\n" + "\n".join(results)

        except Exception as e:
            logger.error(f"Email search failed: {e}")
            return f"Search failed: {e}"

    # ── Send email ──────────────────────────────────────────────
    elif action == "send":
        if not to:
            return "Who should I send the email to? I need a recipient address."
        if not subject:
            return "What should the subject line be?"
        if not body:
            return "What should the email say?"

        try:
            msg = MIMEMultipart()
            msg["From"] = addr
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(addr, pwd)
                server.send_message(msg)

            logger.info(f"Email sent to {to}: {subject}")
            return f"✉️ Email sent to {to} with subject '{subject}'."

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return f"Failed to send email: {e}"

    # ── Count unread ────────────────────────────────────────────
    elif action == "count":
        try:
            imap = imaplib.IMAP4_SSL(imap_host, imap_port)
            imap.login(addr, pwd)
            imap.select("INBOX")
            _, msg_ids = imap.search(None, "UNSEEN")
            count = len(msg_ids[0].split()) if msg_ids[0] else 0
            imap.logout()
            if count == 0:
                return "📭 No unread emails."
            return f"📬 You have {count} unread email(s)."

        except Exception as e:
            logger.error(f"Email count failed: {e}")
            return f"Failed to check emails: {e}"

    else:
        return f"Unknown email action '{action}'. Use: read, search, send, or count."
