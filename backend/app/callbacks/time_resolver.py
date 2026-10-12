import re
from datetime import datetime, timedelta, timezone, time as dt_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Tuple, Optional, Dict, Any
from app.config import config
from app.utils.logging import logger


class TimeResolverError(Exception):
    """Exception raised when time resolution or phone validation fails."""
    def __init__(self, message: str, error_code: str = "INVALID_TIME_FORMAT"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def normalize_e164_phone(phone: str, default_country_code: str = "+91") -> str:
    """Normalizes raw input phone number string to strict E.164 format.
    
    Examples:
        "9876543210" -> "+919876543210"
        "+91 98765-43210" -> "+919876543210"
        "+1 (555) 019-9000" -> "+15550199000"
    """
    if not phone:
        raise TimeResolverError("Phone number cannot be empty.", error_code="INVALID_PHONE_NUMBER")

    clean = re.sub(r"[\s\-\(\)\.]", "", str(phone).strip())

    if not clean.startswith("+"):
        if clean.isdigit():
            if len(clean) == 10:
                clean = default_country_code + clean
            elif len(clean) == 12 and clean.startswith("91"):
                clean = "+" + clean
            elif len(clean) == 11 and clean.startswith("1"):
                clean = "+" + clean
            else:
                clean = "+" + clean

    pattern = re.compile(r"^\+[1-9]\d{6,14}$")
    if not pattern.match(clean):
        raise TimeResolverError(f"Phone number '{phone}' is not a valid E.164 formatted number.", error_code="INVALID_PHONE_NUMBER")

    return clean


def resolve_timezone(tz_name: Optional[str] = None) -> Tuple[ZoneInfo, str]:
    """Resolves and validates IANA timezone string. Defaults to CALLBACK_DEFAULT_TIMEZONE or Asia/Kolkata."""
    fallback_tz_str = getattr(config, "CALLBACK_DEFAULT_TIMEZONE", "Asia/Kolkata")
    candidate_str = tz_name or fallback_tz_str

    try:
        tz = ZoneInfo(candidate_str)
        return tz, candidate_str
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        try:
            tz = ZoneInfo(fallback_tz_str)
            return tz, fallback_tz_str
        except Exception:
            tz = ZoneInfo("UTC")
            return tz, "UTC"


def parse_natural_language_time(
    requested_text: str,
    user_tz_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministically resolves natural language callback request time into timezone-aware UTC datetime.
    
    Args:
        requested_text: Natural language string (e.g. "tomorrow at 3 PM", "in 30 minutes", "next Monday at 10 AM")
        user_tz_str: IANA timezone string (e.g. "Asia/Kolkata")
        
    Returns:
        dict containing:
            - scheduled_at_utc: ISO-8601 UTC string
            - scheduled_at_local: ISO-8601 local timezone string
            - timezone: resolved IANA timezone string
            - is_ambiguous: bool
            - message: human readable confirmation string
    """
    if not requested_text or not requested_text.strip():
        raise TimeResolverError("Requested callback time text cannot be empty.", error_code="MISSING_TIME")

    tz, tz_name = resolve_timezone(user_tz_str)
    now_local = datetime.now(tz)
    text = requested_text.lower().strip()

    # 1. Relative offset: "in X minutes" / "in X hours" / "in X days"
    rel_match = re.search(r"in\s+(\d+)\s*(min|minute|mins|minutes|hr|hour|hrs|hours|day|days)", text)
    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2)
        if "min" in unit:
            target_dt = now_local + timedelta(minutes=val)
        elif "hr" in unit or "hour" in unit:
            target_dt = now_local + timedelta(hours=val)
        elif "day" in unit:
            target_dt = now_local + timedelta(days=val)
        else:
            target_dt = now_local + timedelta(minutes=val)

        dt_utc = target_dt.astimezone(timezone.utc)
        return {
            "scheduled_at_utc": dt_utc.isoformat(),
            "scheduled_at_local": target_dt.isoformat(),
            "timezone": tz_name,
            "is_ambiguous": False,
            "display_time": target_dt.strftime("%I:%M %p, %A, %B %d, %Y"),
        }

    # 2. Time extraction (e.g., "3 PM", "3:30 PM", "15:00", "10 AM")
    target_date = now_local.date()
    is_tomorrow = "tomorrow" in text
    is_next_day = "next" in text

    if is_tomorrow:
        target_date = target_date + timedelta(days=1)

    # Day of week parsing: "next Monday", "Friday"
    days_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    for day_name, day_num in days_map.items():
        if day_name in text:
            days_ahead = day_num - target_date.weekday()
            if days_ahead <= 0:  # Target day already happened this week or is today
                days_ahead += 7
            if is_next_day and days_ahead < 7:
                days_ahead += 7
            target_date = target_date + timedelta(days=days_ahead)
            break

    # Time regex: "3:30 pm", "3 pm", "15:00", "10am"
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    has_specific_time = False
    hour = 10
    minute = 0

    if time_match:
        raw_hour = int(time_match.group(1))
        raw_min = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)

        if ampm:
            has_specific_time = True
            if ampm == "pm" and raw_hour < 12:
                hour = raw_hour + 12
            elif ampm == "am" and raw_hour == 12:
                hour = 0
            else:
                hour = raw_hour
            minute = raw_min
        elif raw_hour > 12 or (0 <= raw_hour <= 23 and ":" in text):
            has_specific_time = True
            hour = raw_hour
            minute = raw_min

    # Time of day heuristics if no explicit numeric time specified
    if not has_specific_time:
        if "morning" in text:
            hour, minute = 10, 0
        elif "afternoon" in text:
            hour, minute = 14, 0
        elif "evening" in text or "tonight" in text:
            hour, minute = 18, 0
        elif is_tomorrow and not has_specific_time:
            # "tomorrow" without time specifier
            hour, minute = 10, 0
            # Flag as slightly ambiguous, though default morning policy applies
            return {
                "scheduled_at_utc": (datetime.combine(target_date, dt_time(hour, minute), tzinfo=tz)).astimezone(timezone.utc).isoformat(),
                "scheduled_at_local": datetime.combine(target_date, dt_time(hour, minute), tzinfo=tz).isoformat(),
                "timezone": tz_name,
                "is_ambiguous": True,
                "ambiguity_reason": "Specific time not provided for tomorrow. Defaulting to 10:00 AM.",
                "display_time": "10:00 AM tomorrow",
            }

    # Construct target local datetime
    try:
        target_dt = datetime.combine(target_date, dt_time(hour, minute), tzinfo=tz)
    except Exception as e:
        raise TimeResolverError(f"Invalid date/time combination: {e}", error_code="INVALID_TIME")

    # If requested time is in the past, push to next day or fail
    if target_dt <= now_local:
        if not is_tomorrow:
            target_dt += timedelta(days=1)
        if target_dt <= now_local:
            raise TimeResolverError("Cannot schedule a callback in the past.", error_code="PAST_TIME_ERROR")

    # Validate working hours policy
    start_str = getattr(config, "CALLBACK_WORKING_HOURS_START", "09:00")
    end_str = getattr(config, "CALLBACK_WORKING_HOURS_END", "18:00")
    try:
        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))
        working_start = dt_time(start_h, start_m)
        working_end = dt_time(end_h, end_m)

        if not (working_start <= target_dt.time() <= working_end):
            logger.info(f"[TIME-RESOLVER] Scheduled time {target_dt.time()} is outside working hours ({start_str}-{end_str}).")
    except Exception as e:
        logger.warning(f"[TIME-RESOLVER] Working hours check notice: {e}")

    dt_utc = target_dt.astimezone(timezone.utc)
    return {
        "scheduled_at_utc": dt_utc.isoformat(),
        "scheduled_at_local": target_dt.isoformat(),
        "timezone": tz_name,
        "is_ambiguous": False,
        "display_time": target_dt.strftime("%I:%M %p on %A, %B %d, %Y"),
    }
