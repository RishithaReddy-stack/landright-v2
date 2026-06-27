"""
Notifications Service
---------------------
Runs nightly via APScheduler. For every user with a complete profile:
  1. Calculate their deadlines
  2. Check for upcoming urgent/warning thresholds
  3. Create a Notification record (deduped — one per kind per day)
  4. Send an SES email for urgent notifications (skipped in dev)

Thresholds:
  OPT application window opens in ≤ 90 days  → warning
  OPT application window opens in ≤ 30 days  → urgent
  Tax deadline in ≤ 30 days                  → warning
  Program end date in ≤ 14 days              → urgent
"""
import logging
from datetime import datetime, timedelta

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.models.user import User, Profile
from backend.models.notification import Notification
from backend.services.deadline import calculate_all, is_stem

logger = logging.getLogger(__name__)


# ── Threshold definitions ──────────────────────────────────────────────────────

THRESHOLDS = [
    {
        # OPT window not yet open — opening within 30 days
        "key": "opt_urgent",
        "kind": "urgent",
        "title": "⚠️ Apply for OPT Now — Window Opens Soon",
        "body_template": (
            "Your OPT application window opens in {days} days ({date}). "
            "USCIS takes 3–5 months to process — apply immediately to avoid gaps in work authorization."
        ),
        "days_before": 30,
        "deadline_fn": lambda p: p.program_end_date - timedelta(days=90) if p.program_end_date else None,
    },
    {
        # OPT window not yet open — opening within 90 days
        "key": "opt_warning",
        "kind": "warning",
        "title": "📋 OPT Application Window Opening Soon",
        "body_template": (
            "Your OPT application window opens in {days} days ({date}). "
            "Start gathering documents: I-20, I-765, passport photos, proof of status."
        ),
        "days_before": 90,
        "deadline_fn": lambda p: p.program_end_date - timedelta(days=90) if p.program_end_date else None,
    },
    {
        # Graduation in ≤ 30 days (OPT window already open)
        "key": "graduation_urgent",
        "kind": "urgent",
        "title": "🎓 Graduation in 30 Days — OPT Window is Open",
        "body_template": (
            "Your program ends in {days} days ({date}) and your OPT application window is already open. "
            "Submit your OPT application ASAP — USCIS processing takes 3–5 months."
        ),
        "days_before": 30,
        "deadline_fn": lambda p: p.program_end_date,
    },
    {
        "key": "tax_warning",
        "kind": "warning",
        "title": "🧾 Tax Deadline in 30 Days",
        "body_template": (
            "April 15 tax deadline is in {days} days. "
            "As an F-1 student, file Form 8843 even if you had no income. "
            "If you had income, also file Form 1040-NR."
        ),
        "days_before": 30,
        "deadline_fn": lambda p: _next_april_15(),
    },
]


def _next_april_15() -> datetime:
    now = datetime.utcnow()
    candidate = datetime(now.year, 4, 15)
    return candidate if candidate > now else datetime(now.year + 1, 4, 15)


def _dedup_key(user_id: int, threshold_key: str) -> str:
    """One notification per user per threshold per calendar day."""
    return f"{threshold_key}_{datetime.utcnow().date()}"


# ── Core check ─────────────────────────────────────────────────────────────────

async def check_user_deadlines(db: AsyncSession, user: User, profile: Profile) -> int:
    """
    Evaluate all thresholds for one user. Create Notification rows for any
    that are triggered and haven't been sent today. Returns count created.
    """
    now = datetime.utcnow()
    created = 0

    for t in THRESHOLDS:
        deadline = t["deadline_fn"](profile)
        if not deadline:
            print(f"[NOTIF] {t['key']}: no deadline, skipping")
            continue

        days_remaining = (deadline - now).days
        print(f"[NOTIF] {t['key']}: days_remaining={days_remaining}, days_before={t['days_before']}, passes={0 <= days_remaining <= t['days_before']}")
        if not (0 <= days_remaining <= t["days_before"]):
            continue

        # Dedup: skip if we already created this notification today
        existing = await db.execute(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.title == t["title"],
                Notification.created_at >= datetime(now.year, now.month, now.day),
            )
        )
        existing_row = existing.scalar_one_or_none()
        print(f"[NOTIF] {t['key']}: dedup check → existing={existing_row}")
        if existing_row:
            continue

        body = t["body_template"].format(
            days=days_remaining,
            date=deadline.strftime("%B %d, %Y"),
        )

        try:
            notif = Notification(
                user_id=user.id,
                title=t["title"],
                body=body,
                kind=t["kind"],
            )
            db.add(notif)
            await db.flush()
            print(f"[NOTIF] {t['key']}: flushed OK, notif.id={notif.id}")
        except Exception as e:
            print(f"[NOTIF] {t['key']}: FLUSH FAILED — {e}")
            raise

        if t["kind"] == "urgent":
            sent = await _send_ses_email(user.email, t["title"], body)
            if sent:
                notif.email_sent = True

        created += 1
        print(f"[NOTIF] {t['key']}: created += 1, total so far={created}")

    print(f"[NOTIF] done for user {user.id}: created={created}")
    if created:
        await db.commit()
        print(f"[NOTIF] committed {created} notifications for user {user.id}")

    return created


# ── Nightly job (called by APScheduler) ───────────────────────────────────────

async def run_nightly_check() -> None:
    """
    Entry point for the nightly scheduler job.
    Opens its own DB session (scheduler runs outside request context).
    """
    logger.info("Running nightly deadline check...")
    total = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User, Profile)
            .join(Profile, Profile.user_id == User.id)
            .where(Profile.program_end_date.isnot(None))
        )
        rows = result.all()

        for user, profile in rows:
            try:
                count = await check_user_deadlines(db, user, profile)
                total += count
            except Exception as e:
                logger.error(f"Failed deadline check for user {user.id}: {e}")

    logger.info(f"Nightly check complete — {total} notifications created for {len(rows)} users.")


# ── SES email (skipped in dev) ─────────────────────────────────────────────────

async def _send_ses_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email via AWS SES.
    Returns True on success, False if AWS not configured or send fails.
    """
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        logger.info(f"[DEV] SES skipped — would email {to_email}: {subject}")
        return False

    try:
        ses = boto3.client(
            "ses",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        ses.send_email(
            Source=settings.ses_from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        logger.info(f"SES email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"SES send failed for {to_email}: {e}")
        return False
