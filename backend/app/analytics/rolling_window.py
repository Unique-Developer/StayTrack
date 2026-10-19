import datetime
from typing import List, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import UploadedReport, ReportingCalendar, SystemSetting
from app.core.config import settings

def get_window_size(db: Session) -> int:
    setting = db.query(SystemSetting).filter(SystemSetting.key == "rolling_window_days").first()
    if setting and setting.value:
        try:
            return int(setting.value)
        except ValueError:
            pass
    return settings.DEFAULT_ROLLING_WINDOW_DAYS

def calculate_rolling_window(db: Session, property_id: int) -> Dict[str, Any]:
    """
    Computes the rolling date window based on distinct active reporting dates.
    Works from Day 1 without requiring 30 files.
    - If 1 date available -> window has 1 date
    - If 4 dates available -> window has 4 dates
    - If 32 dates available -> window has latest 30 dates
    Identifies missing dates in the calendar between start and end date.
    """
    window_limit = get_window_size(db)

    # 1. Fetch all distinct active reporting dates ordered ascending
    reports = (
        db.query(UploadedReport.report_date, UploadedReport.id)
        .filter(
            UploadedReport.property_id == property_id,
            UploadedReport.status == "completed",
            UploadedReport.is_active == True
        )
        .order_by(UploadedReport.report_date.asc())
        .all()
    )

    if not reports:
        return {
            "window_size_setting": window_limit,
            "total_reporting_dates": 0,
            "active_window_dates": [],
            "window_start_date": None,
            "window_end_date": None,
            "missing_calendar_dates": [],
            "coverage_percentage": 0.0
        }

    # Distinct dates map: date -> report_id
    date_to_report = {}
    for r_date, r_id in reports:
        date_to_report[r_date] = r_id

    distinct_dates = sorted(list(date_to_report.keys()))
    total_dates_count = len(distinct_dates)

    # Rolling window: take the latest N dates
    if total_dates_count <= window_limit:
        active_dates = distinct_dates
    else:
        active_dates = distinct_dates[-window_limit:]

    start_date = active_dates[0]
    end_date = active_dates[-1]

    # Find missing calendar days between active window start and end
    active_dates_set = set(active_dates)
    missing_dates = []
    
    curr = start_date
    while curr <= end_date:
        if curr not in active_dates_set:
            missing_dates.append(curr.isoformat())
        curr += datetime.timedelta(days=1)

    total_span_days = (end_date - start_date).days + 1
    coverage = round((len(active_dates) / total_span_days) * 100.0, 1) if total_span_days > 0 else 100.0

    # Sync to ReportingCalendar table
    # Clear existing entries for this property
    db.query(ReportingCalendar).filter(ReportingCalendar.property_id == property_id).delete()
    
    # Insert for all distinct dates
    for d in distinct_dates:
        is_in_win = d in active_dates_set
        rep_id = date_to_report.get(d)
        cal = ReportingCalendar(
            property_id=property_id,
            reporting_date=d,
            report_id=rep_id,
            has_report=True,
            is_in_active_window=is_in_win
        )
        db.add(cal)

    db.flush()

    return {
        "window_size_setting": window_limit,
        "total_reporting_dates": total_dates_count,
        "active_window_dates": [d.isoformat() for d in active_dates],
        "window_start_date": start_date.isoformat(),
        "window_end_date": end_date.isoformat(),
        "missing_calendar_dates": missing_dates,
        "coverage_percentage": coverage
    }
