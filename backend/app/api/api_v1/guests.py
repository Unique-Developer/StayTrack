import csv
import io
import json
import logging
import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from app.db.session import get_db
from app.db.models import (
    GuestIdentity,
    GuestRecord,
    StayAssessment,
    GuestIdentityMatch,
    UploadedReport,
    Property,
    User
)
from app.schemas.models import GuestMonitoringResponse, GuestAssessmentItem, MergeIdentitiesRequest
from app.core.time_utils import to_utc_iso, get_ny_now
from app.api.deps import get_current_user, log_audit
from app.analytics.stay_detector import recalculate_all_analytics
from app.analytics.long_stay_pdf import get_continuous_stays, generate_long_stay_pdf

router = APIRouter(prefix="/guests", tags=["guests"])

@router.get("/monitoring", response_model=GuestMonitoringResponse)
def get_guest_monitoring(
    mode: Optional[str] = Query(None, description="continuous_stay or repeated_appearance"),
    search: Optional[str] = Query(None, description="Search name, room, or confirmation"),
    verification_status: Optional[str] = Query(None, description="Verified or Needs Verification"),
    min_appearances: Optional[int] = Query(None),
    min_duration: Optional[int] = Query(None),
    room: Optional[str] = Query(None),
    sort_by: str = Query("stay_duration_days", description="stay_duration_days, reporting_dates_count, guest_name"),
    sort_order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        db.query(StayAssessment)
        .join(GuestIdentity, StayAssessment.guest_identity_id == GuestIdentity.id)
        .filter(StayAssessment.is_active_in_window == True)
    )

    if mode:
        query = query.filter(StayAssessment.mode == mode)

    if verification_status:
        query = query.filter(StayAssessment.verification_status == verification_status)

    if min_appearances:
        query = query.filter(StayAssessment.reporting_dates_count >= min_appearances)

    if min_duration:
        query = query.filter(StayAssessment.stay_duration_days >= min_duration)

    if room:
        query = query.filter(StayAssessment.room_numbers.like(f"%{room}%"))

    if search:
        s = f"%{search.strip().upper()}%"
        query = query.filter(
            or_(
                GuestIdentity.normalized_name.like(s),
                StayAssessment.room_numbers.like(s),
                StayAssessment.confirmation_numbers.like(s)
            )
        )

    # Sorting
    sort_col = getattr(StayAssessment, sort_by, StayAssessment.stay_duration_days)
    if sort_by == "guest_name":
        sort_col = GuestIdentity.normalized_name

    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    total = query.count()
    items_db = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for a in items_db:
        rooms = json.loads(a.room_numbers or "[]")
        confs = json.loads(a.confirmation_numbers or "[]")
        dates = json.loads(a.date_list or "[]")

        items.append(
            GuestAssessmentItem(
                id=a.id,
                guest_identity_id=a.guest_identity_id,
                guest_name=a.guest_identity.normalized_name,
                mode=a.mode,
                stay_duration_days=a.stay_duration_days,
                reporting_dates_count=a.reporting_dates_count,
                first_date=a.first_date.isoformat() if a.first_date else None,
                last_date=a.last_date.isoformat() if a.last_date else None,
                rooms=rooms,
                confirmation_numbers=confs,
                dates_appeared=dates,
                evidence_source=a.evidence_source,
                verification_status=a.verification_status,
                confidence_score=1.0 if a.verification_status == "Verified" else 0.75,
                notes=a.notes
            )
        )

    return GuestMonitoringResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@router.get("/export")
def export_guests(
    mode: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export filtered assessments to CSV format."""
    query = (
        db.query(StayAssessment)
        .join(GuestIdentity, StayAssessment.guest_identity_id == GuestIdentity.id)
        .filter(StayAssessment.is_active_in_window == True)
    )

    if mode:
        query = query.filter(StayAssessment.mode == mode)
    if verification_status:
        query = query.filter(StayAssessment.verification_status == verification_status)
    if search:
        s = f"%{search.strip().upper()}%"
        query = query.filter(
            or_(
                GuestIdentity.normalized_name.like(s),
                StayAssessment.room_numbers.like(s),
                StayAssessment.confirmation_numbers.like(s)
            )
        )

    rows = query.order_by(StayAssessment.stay_duration_days.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Guest Name",
        "Tracking Mode",
        "Stay Duration (Days)",
        "Appearance Count",
        "First Date",
        "Last Date",
        "Rooms",
        "Confirmation Numbers",
        "Verification Status",
        "Evidence Source",
        "Notes"
    ])

    for r in rows:
        rooms_str = ", ".join(json.loads(r.room_numbers or "[]"))
        confs_str = ", ".join(json.loads(r.confirmation_numbers or "[]"))
        writer.writerow([
            r.guest_identity.normalized_name,
            r.mode,
            r.stay_duration_days,
            r.reporting_dates_count,
            r.first_date.isoformat() if r.first_date else "",
            r.last_date.isoformat() if r.last_date else "",
            rooms_str,
            confs_str,
            r.verification_status,
            r.evidence_source or "",
            r.notes or ""
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=staytrack_guest_monitoring.csv"}
    )


@router.get("/export-pdf")
def export_guests_pdf(
    search: Optional[str] = Query(None, description="Filter by guest name, room, or confirmation"),
    min_nights: int = Query(7, ge=1, description="Minimum continuous nights threshold"),
    property_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports a high-fidelity PDF report of continuous long-stay guests,
    starting from 30 days+ continuous stay down to lesser continuous stay customers,
    ignoring customers who did not stay continuously in a row.
    """
    try:
        prop = None
        if property_id:
            prop = db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            prop = db.query(Property).first()

        pid = prop.id if prop else 1
        pname = prop.name if prop else "Motel 6"

        prop_name, stays, counts = get_continuous_stays(
            db=db,
            property_id=pid,
            min_nights=min_nights,
            search=search
        )

        pdf_bytes = generate_long_stay_pdf(
            property_name=pname,
            stays=stays,
            counts=counts
        )

        today_str = get_ny_now().date().isoformat()
        filename = f"staytrack_long_stay_monitoring_{today_str}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )
    except Exception as e:
        import traceback
        logging.error(f"Error generating long stay PDF: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate long-stay PDF report: {str(e)}"
        )


@router.get("/{identity_id}")
def get_guest_detail(
    identity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns complete profile and audit timeline for a guest identity:
    - Demographics
    - All associated records from daily reports
    - Identity match history
    - Stay assessment calculations and evidence
    """
    identity = db.query(GuestIdentity).filter(GuestIdentity.id == identity_id).first()
    if not identity:
        raise HTTPException(status_code=404, detail="Guest identity not found")

    records = (
        db.query(GuestRecord)
        .join(UploadedReport, GuestRecord.report_id == UploadedReport.id)
        .filter(GuestRecord.guest_identity_id == identity.id)
        .order_by(UploadedReport.report_date.desc(), GuestRecord.check_in_date.desc())
        .all()
    )

    matches = db.query(GuestIdentityMatch).filter(GuestIdentityMatch.guest_identity_id == identity.id).all()
    assessments = db.query(StayAssessment).filter(StayAssessment.guest_identity_id == identity.id).all()

    timeline = []
    for r in records:
        flags = []
        try:
            flags = json.loads(r.validation_flags.replace("'", '"')) if r.validation_flags else []
        except Exception:
            flags = [r.validation_flags] if r.validation_flags else []

        timeline.append({
            "record_id": r.id,
            "report_id": r.report_id,
            "report_date": r.report.report_date.isoformat() if r.report else None,
            "report_file": r.report.original_filename if r.report else None,
            "confirmation_number": r.confirmation_number,
            "room_number": r.room_number,
            "check_in_date": r.check_in_date.isoformat() if r.check_in_date else None,
            "number_of_nights": r.number_of_nights,
            "calculated_departure_date": r.calculated_departure_date.isoformat() if r.calculated_departure_date else None,
            "status": r.status,
            "total_guest_balance": r.total_guest_balance,
            "actual_departed_time": r.actual_departed_time,
            "source_page": r.source_page,
            "source_row_index": r.source_row_index,
            "confidence_score": r.confidence_score,
            "validation_flags": flags
        })

    match_history = [
        {
            "id": m.id,
            "guest_record_id": m.guest_record_id,
            "match_type": m.match_type,
            "confidence_score": m.confidence_score,
            "status": m.status,
            "review_notes": m.review_notes,
            "created_at": to_utc_iso(m.created_at) or m.created_at.isoformat()
        }
        for m in matches
    ]

    assessment_data = [
        {
            "id": a.id,
            "mode": a.mode,
            "stay_duration_days": a.stay_duration_days,
            "reporting_dates_count": a.reporting_dates_count,
            "first_date": a.first_date.isoformat() if a.first_date else None,
            "last_date": a.last_date.isoformat() if a.last_date else None,
            "rooms": json.loads(a.room_numbers or "[]"),
            "confirmations": json.loads(a.confirmation_numbers or "[]"),
            "dates_list": json.loads(a.date_list or "[]"),
            "evidence_source": a.evidence_source,
            "verification_status": a.verification_status,
            "notes": a.notes
        }
        for a in assessments
    ]

    return {
        "identity_id": identity.id,
        "normalized_name": identity.normalized_name,
        "first_name": identity.primary_first_name,
        "last_name": identity.primary_last_name,
        "verification_status": identity.verification_status,
        "notes": identity.notes,
        "records_count": len(records),
        "timeline": timeline,
        "matches": match_history,
        "assessments": assessment_data
    }


@router.post("/merge")
def merge_guest_identities(
    payload: MergeIdentitiesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Merges multiple guest identity profiles into a single primary identity.
    Reassigns all records, recalculates continuous stays, and updates audit history.
    """
    primary = db.query(GuestIdentity).filter(GuestIdentity.id == payload.primary_identity_id).first()
    if not primary:
        raise HTTPException(status_code=404, detail="Primary guest identity not found")

    secondary_ids = [sid for sid in payload.secondary_identity_ids if sid != payload.primary_identity_id]
    if not secondary_ids:
        raise HTTPException(status_code=400, detail="No valid secondary identities provided for merge")

    secondaries = db.query(GuestIdentity).filter(GuestIdentity.id.in_(secondary_ids)).all()
    if not secondaries:
        raise HTTPException(status_code=404, detail="No secondary guest identities found")

    # Reassign all GuestRecord rows
    db.query(GuestRecord).filter(GuestRecord.guest_identity_id.in_(secondary_ids)).update(
        {GuestRecord.guest_identity_id: primary.id},
        synchronize_session=False
    )

    # Reassign all GuestIdentityMatch rows
    db.query(GuestIdentityMatch).filter(GuestIdentityMatch.guest_identity_id.in_(secondary_ids)).update(
        {GuestIdentityMatch.guest_identity_id: primary.id},
        synchronize_session=False
    )

    # Remove secondaries
    for sec in secondaries:
        db.delete(sec)

    db.commit()

    recalculate_all_analytics(db, primary.property_id)

    log_audit(
        db,
        current_user.id,
        "merge_guest_identities",
        "guest_identity",
        str(primary.id),
        {"merged_identity_ids": secondary_ids, "primary_identity_id": primary.id}
    )

    return {
        "success": True,
        "primary_identity_id": primary.id,
        "merged_count": len(secondaries),
        "message": f"Successfully merged {len(secondaries)} customer profiles into #{primary.id} ({primary.normalized_name})."
    }

