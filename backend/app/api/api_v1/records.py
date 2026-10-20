import csv
import io
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from app.db.session import get_db
from app.db.models import GuestRecord, UploadedReport, GuestIdentity, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/records", tags=["records"])

@router.get("")
def get_all_records(
    search: Optional[str] = Query(None),
    report_date: Optional[str] = Query(None),
    room: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("check_in_date"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        db.query(GuestRecord)
        .join(UploadedReport, GuestRecord.report_id == UploadedReport.id)
        .filter(UploadedReport.is_active == True)
    )

    if report_date:
        query = query.filter(UploadedReport.report_date == report_date)

    if room:
        query = query.filter(GuestRecord.room_number == room)

    if search:
        s = f"%{search.strip().upper()}%"
        query = query.filter(
            or_(
                GuestRecord.normalized_name.like(s),
                GuestRecord.room_number.like(s),
                GuestRecord.confirmation_number.like(s)
            )
        )

    sort_col = getattr(GuestRecord, sort_by, GuestRecord.check_in_date)
    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for r in records:
        flags = []
        try:
            flags = json.loads(r.validation_flags.replace("'", '"')) if r.validation_flags else []
        except Exception:
            flags = [r.validation_flags] if r.validation_flags else []

        items.append({
            "id": r.id,
            "report_id": r.report_id,
            "report_date": r.report.report_date.isoformat() if r.report else None,
            "report_filename": r.report.original_filename if r.report else None,
            "guest_identity_id": r.guest_identity_id,
            "confirmation_number": r.confirmation_number,
            "additional_guests": r.additional_guests,
            "room_number": r.room_number,
            "guest_name": r.normalized_name,
            "raw_guest_name": r.raw_guest_name,
            "first_name": r.first_name,
            "last_name": r.last_name,
            "check_in_date": r.check_in_date.isoformat() if r.check_in_date else None,
            "number_of_nights": r.number_of_nights,
            "calculated_departure_date": r.calculated_departure_date.isoformat() if r.calculated_departure_date else None,
            "status": r.status,
            "total_guest_balance": r.total_guest_balance,
            "actual_departed_time": r.actual_departed_time,
            "vip_guest": r.vip_guest,
            "guest_tier": r.guest_tier,
            "housekeeping_remarks": r.housekeeping_remarks,
            "source_page": r.source_page,
            "source_row_index": r.source_row_index,
            "confidence_score": r.confidence_score,
            "validation_flags": flags
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }


@router.get("/export")
def export_all_records(
    search: Optional[str] = Query(None),
    report_date: Optional[str] = Query(None),
    room: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        db.query(GuestRecord)
        .join(UploadedReport, GuestRecord.report_id == UploadedReport.id)
        .filter(UploadedReport.is_active == True)
    )
    if report_date:
        query = query.filter(UploadedReport.report_date == report_date)
    if room:
        query = query.filter(GuestRecord.room_number == room)
    if search:
        s = f"%{search.strip().upper()}%"
        query = query.filter(
            or_(
                GuestRecord.normalized_name.like(s),
                GuestRecord.room_number.like(s),
                GuestRecord.confirmation_number.like(s)
            )
        )

    records = query.order_by(GuestRecord.check_in_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Report Date", "Confirmation No", "Room No", "Guest Name",
        "Check In Date", "Nights", "Calculated Departure", "Status",
        "Balance", "Departed Time", "VIP", "Additional Guests"
    ])

    for r in records:
        writer.writerow([
            r.report.report_date.isoformat() if r.report else "",
            r.confirmation_number or "",
            r.room_number or "",
            r.normalized_name,
            r.check_in_date.isoformat() if r.check_in_date else "",
            r.number_of_nights or "",
            r.calculated_departure_date.isoformat() if r.calculated_departure_date else "",
            r.status or "",
            r.total_guest_balance or 0.0,
            r.actual_departed_time or "",
            r.vip_guest or "No",
            r.additional_guests or ""
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=staytrack_all_guest_records.csv"}
    )
