import datetime
from typing import Optional

def get_ny_timezone():
    """
    Returns the America/New_York timezone object (IANA tz).
    Falls back to fixed offset EDT/EST if tzdata is missing.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:
        # Fallback to EDT (UTC-4) / EST (UTC-5)
        # Daylight Saving in US runs from second Sunday in March to first Sunday in November
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        # Approximate: March (3) to November (11) is EDT
        if 3 <= now_utc.month <= 10:
            return datetime.timezone(datetime.timedelta(hours=-4), name="EDT")
        return datetime.timezone(datetime.timedelta(hours=-5), name="EST")


def get_ny_now() -> datetime.datetime:
    """
    Returns the current datetime in America/New_York timezone.
    """
    tz = get_ny_timezone()
    return datetime.datetime.now(tz)


def format_ny_now_str(fmt: str = "%b %d, %Y • %I:%M %p %Z") -> str:
    """
    Returns formatted current time in New York.
    """
    return get_ny_now().strftime(fmt)


def to_utc_iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    """
    Serializes a datetime to an ISO-8601 string with an explicit UTC indicator 'Z'.
    e.g. '2026-10-22T14:15:30Z'
    This prevents browser JavaScript from incorrectly treating naive UTC datetimes as local device time.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        iso = iso[:-6] + "Z"
    return iso


def to_ny_iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    """
    Converts a datetime to America/New_York timezone and formats as ISO 8601 with offset.
    e.g. '2026-10-22T10:15:30-04:00'
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    tz = get_ny_timezone()
    return dt.astimezone(tz).isoformat()


def to_ny_display_str(dt: Optional[datetime.datetime], fmt: str = "%b %d, %Y • %I:%M %p %Z") -> Optional[str]:
    """
    Converts a datetime to America/New_York timezone and returns human-readable formatted string.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    tz = get_ny_timezone()
    return dt.astimezone(tz).strftime(fmt)
