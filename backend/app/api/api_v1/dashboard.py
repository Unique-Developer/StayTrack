import datetime
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import (
    UploadedReport,
    GuestIdentity,
    GuestRecord,
    StayAssessment,
    ReportingCalendar,
    Property,
    User
)
from app.schemas.models import DashboardSummary, PropertyItem
from app.analytics.rolling_window import calculate_rolling_window
from app.core.time_utils import to_utc_iso
from app.api.deps import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/properties", response_model=List[PropertyItem])
def get_properties(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns all configured properties (e.g. Studio 6, Motel 6)."""
    props = db.query(Property).order_by(Property.id.asc()).all()
    return [
        PropertyItem(
            id=p.id,
            name=p.name,
            property_code=p.property_code,
            timezone=p.timezone,
            address=p.address
        )
        for p in props
    ]

@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    property_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prop = None
    if property_id:
        prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        prop = db.query(Property).first()
    target_property_id = prop.id if prop else 1
    property_id = target_property_id

    # Recalculate / retrieve rolling window metrics
    win_data = calculate_rolling_window(db, target_property_id)
    
    # 1. Total Reports Imported
    total_reports = (
        db.query(UploadedReport)
        .filter(
            UploadedReport.property_id == target_property_id,
            UploadedReport.status == "completed",
            UploadedReport.is_active == True
        )
        .count()
    )

    # 2. Reporting dates covered
    distinct_dates_count = win_data.get("total_reporting_dates", 0)

    # 3. Unique Guest Identities
    unique_guests = (
        db.query(GuestIdentity)
        .filter(GuestIdentity.property_id == target_property_id)
        .count()
    )

    # 4. Continuous Stay Count (Mode A)
    # Count continuous stays >= 30 days for this property
    from app.analytics.long_stay_pdf import get_continuous_stays
    _, stays, counts = get_continuous_stays(db, property_id=target_property_id, min_nights=30)
    continuous_stay_count = len(stays)
    continuous_stays = (
        db.query(StayAssessment)
        .filter(
            StayAssessment.property_id == property_id,
            StayAssessment.mode == "continuous_stay",
            StayAssessment.is_active_in_window == True
        )
        .count()
    )

    # 5. Needs Verification Count
    needs_verification = (
        db.query(StayAssessment)
        .filter(
            StayAssessment.property_id == property_id,
            StayAssessment.is_active_in_window == True,
            StayAssessment.verification_status == "Needs Verification"
        )
        .count()
    )

    # 6. Missing Dates
    missing_dates = win_data.get("missing_calendar_dates", [])

    # Latest import
    latest_report_obj = (
        db.query(UploadedReport)
        .filter(
            UploadedReport.property_id == property_id,
            UploadedReport.status == "completed",
            UploadedReport.is_active == True
        )
        .order_by(UploadedReport.created_at.desc())
        .first()
    )
    latest_import = None
    if latest_report_obj:
        latest_import = {
            "id": latest_report_obj.id,
            "filename": latest_report_obj.original_filename,
            "report_date": latest_report_obj.report_date.isoformat(),
            "records_count": latest_report_obj.valid_rows_count,
            "imported_at": to_utc_iso(latest_report_obj.created_at) or latest_report_obj.created_at.isoformat()
        }

    # Recent 5 reports
    recent_objs = (
        db.query(UploadedReport)
        .filter(UploadedReport.property_id == property_id, UploadedReport.is_active == True)
        .order_by(UploadedReport.created_at.desc())
        .limit(5)
        .all()
    )
    recent_reports = [
        {
            "id": r.id,
            "filename": r.original_filename,
            "report_date": r.report_date.isoformat(),
            "status": r.status,
            "rows": r.valid_rows_count,
            "created_at": to_utc_iso(r.created_at) or r.created_at.isoformat()
        }
        for r in recent_objs
    ]

    # Trends: appearances per reporting date
    # Group GuestRecords by report_date
    trend_rows = (
        db.query(UploadedReport.report_date, func.count(GuestRecord.id))
        .join(GuestRecord, GuestRecord.report_id == UploadedReport.id)
        .filter(
            UploadedReport.property_id == property_id,
            UploadedReport.status == "completed",
            UploadedReport.is_active == True
        )
        .group_by(UploadedReport.report_date)
        .order_by(UploadedReport.report_date.asc())
        .all()
    )
    trends = [
        {
            "date": r_date.isoformat(),
            "display_date": r_date.strftime("%b %d"),
            "departures_count": count
        }
        for r_date, count in trend_rows
    ]

    # Recent errors (status == 'failed')
    error_objs = (
        db.query(UploadedReport)
        .filter(UploadedReport.property_id == property_id, UploadedReport.status == "failed")
        .order_by(UploadedReport.created_at.desc())
        .limit(5)
        .all()
    )
    recent_errors = [
        {
            "id": e.id,
            "filename": e.original_filename,
            "error": e.error_message,
            "created_at": to_utc_iso(e.created_at) or e.created_at.isoformat()
        }
        for e in error_objs
    ]

    return DashboardSummary(
        total_reports_imported=total_reports,
        reporting_dates_covered=distinct_dates_count,
        unique_guest_identities=unique_guests,
        continuous_stay_count=continuous_stays,
        needs_verification_count=needs_verification,
        missing_reporting_dates_count=len(missing_dates),
        missing_dates=missing_dates,
        active_window_start=win_data.get("window_start_date"),
        active_window_end=win_data.get("window_end_date"),
        window_coverage_pct=win_data.get("coverage_percentage", 0.0),
        latest_import=latest_import,
        recent_reports=recent_reports,
        appearance_trends=trends,
        recent_errors=recent_errors
    )
