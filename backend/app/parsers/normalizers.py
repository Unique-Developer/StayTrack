import re
import datetime
from typing import Optional, Tuple

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def clean_whitespace(val: Optional[str]) -> str:
    """Trim, replace newlines and multiple spaces with a single space."""
    if not val:
        return ""
    return re.sub(r'\s+', ' ', str(val)).strip()

def normalize_confirmation_number(raw_conf: Optional[str]) -> Optional[str]:
    """
    Remove all whitespace, newlines, and hyphens from confirmation number.
    e.g. '3756AAJ34\\n3' -> '3756AAJ343'
    """
    if not raw_conf:
        return None
    cleaned = re.sub(r'[\s\-]+', '', str(raw_conf)).upper()
    return cleaned if cleaned else None

def normalize_name(raw_name: Optional[str]) -> str:
    """
    Normalize guest name:
    - Replace newlines and commas with spaces
    - Standardize whitespace
    - Uppercase for consistent matching
    e.g. 'PRESTON,\\nGEORGE\\nSTANLEY' -> 'PRESTON GEORGE STANLEY'
    """
    if not raw_name:
        return ""
    # Replace punctuation (commas, slashes) with space
    cleaned = re.sub(r'[,/]+', ' ', str(raw_name))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().upper()
    return cleaned

def parse_date_flexible(date_str: Optional[str]) -> Optional[datetime.date]:
    """
    Parse date from formats such as:
    - '28-Sep-26' or '28-Sep-2026'
    - 'Oct 01, 2026' or 'October 1, 2026'
    - '2026-10-01'
    - '09/28/2026' or '09/28/26'
    """
    if not date_str:
        return None
    clean = clean_whitespace(date_str)
    
    # Format: 28-Sep-26 or 01-Sep-2026
    match_dmy = re.match(r'^(\d{1,2})-([A-Za-z]{3})-(\d{2,4})$', clean)
    if match_dmy:
        day = int(match_dmy.group(1))
        mon_str = match_dmy.group(2).lower()
        yr_str = match_dmy.group(3)
        month = MONTH_MAP.get(mon_str)
        if month:
            year = int(yr_str)
            if year < 100:
                year += 2000
            try:
                return datetime.date(year, month, day)
            except ValueError:
                return None

    # Format: Oct 01, 2026 or October 1, 2026
    match_mdy = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', clean)
    if match_mdy:
        mon_name = match_mdy.group(1)[:3].lower()
        day = int(match_mdy.group(2))
        year = int(match_mdy.group(3))
        month = MONTH_MAP.get(mon_name)
        if month:
            try:
                return datetime.date(year, month, day)
            except ValueError:
                return None

    # Format: YYYY-MM-DD
    match_iso = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', clean)
    if match_iso:
        try:
            return datetime.date(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
        except ValueError:
            return None

    # Format: MM/DD/YYYY or MM/DD/YY
    match_slash = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', clean)
    if match_slash:
        m = int(match_slash.group(1))
        d = int(match_slash.group(2))
        y = int(match_slash.group(3))
        if y < 100:
            y += 2000
        try:
            return datetime.date(y, m, d)
        except ValueError:
            return None

    return None

def calculate_departure_date(
    check_in_date: Optional[datetime.date],
    nights: Optional[int],
    convention: str = "checkin_plus_nights"
) -> Optional[datetime.date]:
    """
    Calculate provisional departure date.
    Default convention: checkin_plus_nights
    e.g. Check-in 2026-09-01 + 30 nights = 2026-10-01.
    """
    if not check_in_date or nights is None or nights < 0:
        return None
    return check_in_date + datetime.timedelta(days=nights)

def clean_room_number(room_val: Optional[str]) -> Optional[str]:
    if not room_val:
        return None
    cleaned = clean_whitespace(room_val)
    return cleaned if cleaned else None
