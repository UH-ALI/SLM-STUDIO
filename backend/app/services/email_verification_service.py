"""
Email deliverability check via Verifalia's REST API, used during signup to
catch typo'd or non-existent domains before an account gets created with
an email nobody can actually reach.

Fails OPEN by design: if VERIFALIA_USERNAME/PASSWORD aren't configured, the
API call errors, or the job doesn't complete within the wait window, we
treat the email as deliverable rather than blocking signup. This is a
best-effort quality check against a third-party service, not a security
boundary — a Verifalia outage should never be able to take down signups.
"""

import logging
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

VERIFALIA_BASE_URL = "https://api.verifalia.com/v2.7"

# Milliseconds the Verifalia API will hold the connection open waiting for
# the validation job to finish, before we fall back to polling (which we
# don't do here — we just accept whatever result comes back at this point,
# fail-open, rather than adding more round trips to the signup flow).
_WAIT_TIME_MS = 12000
_REQUEST_TIMEOUT_S = 15  # a little above _WAIT_TIME_MS to leave room for the response itself


def _fail_open(reason: str) -> dict:
    return {"checked": False, "deliverable": True, "classification": None, "reason": reason}


def check_email_deliverability(email: str) -> dict:
    """
    Returns:
        {
          "checked": bool,        # whether Verifalia actually returned a result
          "deliverable": bool,    # True unless Verifalia positively says Undeliverable
          "classification": str | None,  # "Deliverable" | "Risky" | "Undeliverable" | "Unknown"
          "reason": str | None,
        }
    """
    if not settings.VERIFALIA_USERNAME or not settings.VERIFALIA_PASSWORD:
        return _fail_open("Verifalia not configured")

    try:
        response = requests.post(
            f"{VERIFALIA_BASE_URL}/email-validations",
            params={"waitTime": _WAIT_TIME_MS},
            json={"entries": [{"inputData": email}]},
            auth=(settings.VERIFALIA_USERNAME, settings.VERIFALIA_PASSWORD),
            headers={"Content-Type": "application/json"},
            timeout=_REQUEST_TIMEOUT_S,
        )
    except requests.RequestException as e:
        logger.warning(f"Verifalia request failed ({type(e).__name__}) — failing open")
        return _fail_open("Verification service unreachable")

    # 202 here means the job didn't complete within waitTime (still processing) —
    # we don't poll further, we just fail open rather than stalling signup.
    if response.status_code == 202:
        logger.info("Verifalia job still processing after wait window — failing open")
        return _fail_open("Verification still in progress")

    if response.status_code == 429:
        logger.warning("Verifalia rate limit hit — failing open")
        return _fail_open("Verification service rate-limited")

    if response.status_code != 200:
        logger.warning(f"Verifalia returned unexpected status {response.status_code} — failing open")
        return _fail_open("Verification service error")

    try:
        data = response.json()
        entries = data.get("entries", {}).get("data", [])
        entry = entries[0] if entries else None
    except (ValueError, AttributeError, IndexError):
        logger.warning("Verifalia response could not be parsed — failing open")
        return _fail_open("Verification response unreadable")

    if not entry:
        return _fail_open("No verification result returned")

    classification = entry.get("classification")  # Deliverable | Risky | Undeliverable | Unknown
    status_code = entry.get("status")

    return {
        "checked": True,
        "deliverable": classification != "Undeliverable",
        "classification": classification,
        "reason": None if classification == "Deliverable" else status_code,
    }
