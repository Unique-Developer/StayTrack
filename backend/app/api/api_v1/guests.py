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
from app.schemas.models import GuestMonitoringResponse, GuestAssessmentItem, MergeIdentitiesRequest, UpdateGuestIdentityRequest
from app.core.time_utils import to_utc_iso, get_ny_now
from app.api.deps import get_current_user, log_audit
from app.analytics.stay_detector import recalculate_all_analytics
from app.analytics.long_stay_pdf import get_continuous_stays, generate_long_stay_pdf

router = APIRouter(prefix="/guests", tags=["guests"])

@router.get("/monitoring", response_model=GuestMonitoringResponse)
def get_guest_monitoring(
    mode: Optional[str] = Query("continuous_stay", description="continuous_stay or repeated_appearance"),
    search: Optional[str] = Query(None, description="Search name, room, or confirmation"),
    verification_status: Optional[str] = Query(None, description="Verified or Needs Verification"),
    min_appearances: Optional[int] = Query(None),
    min_duration: Optional[int] = Query(None),
    room: Optional[str] = Query(None),
    property_id: Optional[int] = Query(None),
    sort_by: str = Query("stay_duration_days", description="stay_duration_days, reporting_dates_count, guest_name"),
    sort_order: str = Query("desc", description="asc or desc"),
    as_of_date: Optional[str] = Query(None, description="Date for date-wise report (YYYY-MM-DD)"),
    all_time: bool = Query(False, description="If true, include all historical data without date cutoff"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mode_str = mode if isinstance(mode, str) else "continuous_stay"
    sort_by_str = sort_by if isinstance(sort_by, str) else "stay_duration_days"
    sort_order_str = sort_order if isinstance(sort_order, str) else "desc"
    search_str = search if isinstance(search, str) else None
    room_str = room if isinstance(room, str) else None
    page_val = page if isinstance(page, int) else 1
    page_size_val = page_size if isinstance(page_size, int) else 25

    as_of_d = None
    if as_of_date and isinstance(as_of_date, str) and as_of_date.strip():
        try:
            as_of_d = datetime.date.fromisoformat(as_of_date.strip())
        except ValueError:
            pass

    prop = None
    if property_id and isinstance(property_id, int):
        prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        prop = db.query(Property).first()
    target_property_id = prop.id if prop else 1

    if mode_str == "repeated_appearance":
        query = (
            db.query(StayAssessment)
            .join(GuestIdentity, StayAssessment.guest_identity_id == GuestIdentity.id)
            .filter(StayAssessment.is_active_in_window == True, StayAssessment.property_id == target_property_id, StayAssessment.mode == "repeated_appearance")
        )

        if verification_status and isinstance(verification_status, str):
            query = query.filter(StayAssessment.verification_status == verification_status)
        if min_appearances and isinstance(min_appearances, int):
            query = query.filter(StayAssessment.reporting_dates_count >= min_appearances)
        if min_duration and isinstance(min_duration, int):
            query = query.filter(StayAssessment.stay_duration_days >= min_duration)
        if room_str:
            query = query.filter(StayAssessment.room_numbers.like(f"%{room_str}%"))
        if search_str:
            s = f"%{search_str.strip().upper()}%"
            query = query.filter(
                or_(
                    GuestIdentity.normalized_name.like(s),
                    StayAssessment.room_numbers.like(s),
                    StayAssessment.confirmation_numbers.like(s)
                )
            )

        sort_col = getattr(StayAssessment, sort_by_str, StayAssessment.stay_duration_days)
        if sort_by_str == "guest_name":
            sort_col = GuestIdentity.normalized_name

        if sort_order_str.lower() == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))

        total = query.count()
        items_db = query.offset((page_val - 1) * page_size_val).limit(page_size_val).all()

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
                    notes=a.notes,
                    fixed_rate=a.guest_identity.fixed_rate
                )
            )

        return GuestMonitoringResponse(
            total=total,
            page=page_val,
            page_size=page_size_val,
            items=items
        )

    # Mode A / Continuous stay or 90+ Days Guest List
    effective_min = min_duration if isinstance(min_duration, int) else (90 if mode_str == "continuous_stay_90" else 30)
    pname, stays, counts = get_continuous_stays(
        db=db,
        property_id=target_property_id,
        min_nights=effective_min,
        search=search_str,
        room=room_str,
        as_of_date=as_of_d,
        all_time=all_time
    )

    if mode_str == "continuous_stay_30_89":
        stays = [s for s in stays if 30 <= s["total_nights"] < 90]

    # Sorting
    if sort_by_str == "guest_name":
        stays.sort(key=lambda s: s["guest_name"], reverse=(sort_order_str.lower() == "desc"))
    elif sort_by_str == "first_date":
        stays.sort(key=lambda s: s["check_in"], reverse=(sort_order_str.lower() == "desc"))
    else:
        stays.sort(key=lambda s: (-s["total_nights"], s["check_in"]) if sort_order_str.lower() != "asc" else (s["total_nights"], s["check_in"]))

    total = len(stays)
    start_idx = (page_val - 1) * page_size_val
    paged_stays = stays[start_idx:start_idx + page_size_val]

    items = []
    for s in paged_stays:
        county_iso = s["county_exempt_date"].isoformat() if s.get("county_exempt_date") else None
        state_iso = s["state_exempt_date"].isoformat() if s.get("state_exempt_date") else None
        cin_iso = s["check_in"].isoformat() if s.get("check_in") else None
        cout_iso = s["check_out"].isoformat() if s.get("check_out") else None
        tier_cat = "30+ Days" if ("30" in s.get("category", "") and ("89" in s.get("category", "") or "Days" in s.get("category", "") or "Nights" in s.get("category", ""))) else s.get("category", "")

        items.append(
            GuestAssessmentItem(
                id=s["guest_identity_id"],
                guest_identity_id=s["guest_identity_id"],
                guest_name=s["guest_name"],
                mode="continuous_stay",
                stay_duration_days=s["total_nights"],
                reporting_dates_count=s.get("ext_count", 0) + 1,
                first_date=cin_iso,
                last_date=cout_iso,
                rooms=s["rooms_list"],
                confirmation_numbers=s["confirmations"],
                dates_appeared=[cin_iso, cout_iso] if cin_iso and cout_iso else [],
                evidence_source=f"Unbroken continuous stay: {s['total_nights']} nights ({tier_cat}).",
                verification_status="Verified",
                confidence_score=1.0,
                notes=f"Tier: {tier_cat} • {s.get('tax_status', '')}",
                original_check_in_date=cin_iso,
                county_exempt_date=county_iso,
                state_exempt_date=state_iso,
                tax_exempt_status=s.get("tax_status"),
                fixed_rate=s.get("fixed_rate"),
                tier_category=tier_cat
            )
        )

    return GuestMonitoringResponse(
        total=total,
        page=page_val,
        page_size=page_size_val,
        items=items,
        counts=counts
    )


# Column configuration for custom CSV export
CONTINUOUS_STAY_COLUMNS = {
    "property_name": ("Motel Property", lambda s: s.get("property_name", "")),
    "guest_name": ("Guest Name", lambda s: s["guest_name"]),
    "room_number": ("Room#", lambda s: ", ".join(s.get("rooms_list", []))),
    "check_in_date": ("Check-in Date", lambda s: s["check_in"].strftime("%m-%d-%Y") if s.get("check_in") else ""),
    "calculated_departure_date": ("Calculated Departure Date", lambda s: s["check_out"].strftime("%m-%d-%Y") if s.get("check_out") else ""),
    "total_nights": ("Total Consecutive Nights", lambda s: str(s["total_nights"])),
    "category": ("Stay Tier", lambda s: "30+ Days" if ("30" in s.get("category", "") and ("89" in s.get("category", "") or "Days" in s.get("category", "") or "Nights" in s.get("category", ""))) else s.get("category", "")),
    "county_exempt_date": ("County Tax Exempt Start Date (30+ Days)", lambda s: s["county_exempt_date"].strftime("%m-%d-%Y") if s.get("county_exempt_date") else ""),
    "state_exempt_date": ("State Tax Exempt Date (90+ Days)", lambda s: s["state_exempt_date"].strftime("%m-%d-%Y") if s.get("state_exempt_date") else ""),
    "tax_status": ("Tax Exemption Status", lambda s: s.get("tax_status", "")),
    "fixed_rate": ("Fixed Rate", lambda s: f"${s['fixed_rate']:.2f}" if s.get("fixed_rate") is not None else ""),
    "confirmations": ("Confirmation Numbers", lambda s: ", ".join(s.get("confirmations", []))),
}
DEFAULT_CONTINUOUS_COLUMNS = [
    "property_name",
    "guest_name",
    "room_number",
    "check_in_date",
    "calculated_departure_date",
    "total_nights",
    "category",
    "county_exempt_date",
    "state_exempt_date",
    "tax_status",
    "confirmations"
]

REPEATED_APPEARANCE_COLUMNS = {
    "property_name": ("Motel Property", lambda r: r.property.name if hasattr(r, "property") and r.property else ""),
    "guest_name": ("Guest Name", lambda r: r.guest_identity.normalized_name),
    "mode": ("Tracking Mode", lambda r: r.mode),
    "stay_duration_days": ("Stay Duration (Days)", lambda r: str(r.stay_duration_days)),
    "reporting_dates_count": ("Appearance Count", lambda r: str(r.reporting_dates_count)),
    "first_date": ("First Date", lambda r: r.first_date.strftime("%m-%d-%Y") if r.first_date else ""),
    "last_date": ("Last Date", lambda r: r.last_date.strftime("%m-%d-%Y") if r.last_date else ""),
    "rooms": ("Rooms", lambda r: ", ".join(json.loads(r.room_numbers or "[]"))),
    "confirmation_numbers": ("Confirmation Numbers", lambda r: ", ".join(json.loads(r.confirmation_numbers or "[]"))),
    "verification_status": ("Verification Status", lambda r: r.verification_status),
    "evidence_source": ("Evidence Source", lambda r: r.evidence_source or ""),
    "notes": ("Notes", lambda r: r.notes or ""),
}
DEFAULT_REPEATED_COLUMNS = [
    "property_name",
    "guest_name",
    "mode",
    "stay_duration_days",
    "reporting_dates_count",
    "first_date",
    "last_date",
    "rooms",
    "confirmation_numbers",
    "verification_status",
    "evidence_source",
    "notes"
]


@router.get("/export")
def export_guests(
    mode: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    room: Optional[str] = Query(None),
    min_duration: Optional[int] = Query(None),
    property_id: Optional[int] = Query(None),
    sort_by: str = Query("stay_duration_days"),
    sort_order: str = Query("desc"),
    as_of_date: Optional[str] = Query(None, description="Date for date-wise report (YYYY-MM-DD)"),
    all_time: bool = Query(False, description="If true, include all historical stays without date cutoff"),
    columns: Optional[str] = Query(None, description="Comma-separated column keys to customize CSV export"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export guests to CSV format with optional custom columns and date-wise filtering.
    For Continuous Stays / Mode A (30+ and 90+ days): exports the matching dataset as the PDF report
    and Guest Monitoring table, evaluating occupancy as of today or a target date.
    """
    as_of_d = None
    if as_of_date and isinstance(as_of_date, str) and as_of_date.strip():
        try:
            as_of_d = datetime.date.fromisoformat(as_of_date.strip())
        except ValueError:
            pass

    prop = None
    if property_id and isinstance(property_id, int):
        prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        prop = db.query(Property).first()
    target_property_id = prop.id if prop else 1

    # Continuous Stay CSV export matching the PDF report and monitoring table exactly
    if mode in ("continuous_stay", "continuous_stay_90", "continuous_stay_30_89"):
        export_min_nights = min_duration if isinstance(min_duration, int) else (90 if mode == "continuous_stay_90" else 30)
        prop_name, stays, counts = get_continuous_stays(
            db=db,
            property_id=target_property_id,
            min_nights=export_min_nights,
            search=search,
            room=room,
            as_of_date=as_of_d,
            all_time=all_time
        )

        if mode == "continuous_stay_30_89":
            stays = [s for s in stays if 30 <= s["total_nights"] < 90]

        # Apply exact matching sorting
        if sort_by == "guest_name":
            stays.sort(key=lambda s: s["guest_name"], reverse=(sort_order.lower() == "desc"))
        elif sort_by == "first_date":
            stays.sort(key=lambda s: s["check_in"], reverse=(sort_order.lower() == "desc"))
        else:
            stays.sort(key=lambda s: (-s["total_nights"], s["check_in"]) if sort_order.lower() != "asc" else (s["total_nights"], s["check_in"]))

        # Determine custom or default columns
        active_keys = DEFAULT_CONTINUOUS_COLUMNS
        if columns and isinstance(columns, str) and columns.strip():
            req_keys = [k.strip() for k in columns.split(",") if k.strip() in CONTINUOUS_STAY_COLUMNS]
            if req_keys:
                active_keys = req_keys

        output = io.StringIO()
        output.write('\ufeff')
        writer = csv.writer(output)
        writer.writerow([CONTINUOUS_STAY_COLUMNS[k][0] for k in active_keys])

        for s in stays:
            writer.writerow([CONTINUOUS_STAY_COLUMNS[k][1](s) for k in active_keys])

        date_suffix = as_of_d.strftime("%m-%d-%Y") if as_of_d else get_ny_now().date().strftime("%m-%d-%Y")
        prop_slug = "motel_6" if (prop and "MOTEL 6" in prop.name.upper()) else "studio_6"
        if mode == "continuous_stay_90":
            csv_filename = f"staytrack_{prop_slug}_90plus_days_tax_exempt_{date_suffix}.csv"
        elif mode == "continuous_stay_30_89":
            csv_filename = f"staytrack_{prop_slug}_30to89_days_tax_exempt_{date_suffix}.csv"
        else:
            csv_filename = f"staytrack_{prop_slug}_30_and_90_tax_exempt_{date_suffix}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{csv_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    # General / Repeated appearances assessment export
    query = (
        db.query(StayAssessment)
        .join(GuestIdentity, StayAssessment.guest_identity_id == GuestIdentity.id)
        .filter(StayAssessment.is_active_in_window == True, StayAssessment.property_id == target_property_id)
    )

    if mode:
        query = query.filter(StayAssessment.mode == mode)
    if verification_status:
        query = query.filter(StayAssessment.verification_status == verification_status)
    if room:
        query = query.filter(StayAssessment.room_numbers.like(f"%{room.strip()}%"))
    if search and isinstance(search, str):
        s = f"%{search.strip().upper()}%"
        query = query.filter(
            or_(
                GuestIdentity.normalized_name.like(s),
                StayAssessment.room_numbers.like(s),
                StayAssessment.confirmation_numbers.like(s)
            )
        )

    # Determine custom or default columns for repeated appearances
    active_keys = DEFAULT_REPEATED_COLUMNS
    if columns and isinstance(columns, str) and columns.strip():
        req_keys = [k.strip() for k in columns.split(",") if k.strip() in REPEATED_APPEARANCE_COLUMNS]
        if req_keys:
            active_keys = req_keys

    rows = query.order_by(StayAssessment.stay_duration_days.desc()).all()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([REPEATED_APPEARANCE_COLUMNS[k][0] for k in active_keys])

    for r in rows:
        writer.writerow([REPEATED_APPEARANCE_COLUMNS[k][1](r) for k in active_keys])

    date_suffix = as_of_d.strftime("%m-%d-%Y") if as_of_d else get_ny_now().date().strftime("%m-%d-%Y")
    prop_slug = "motel_6" if (prop and "MOTEL 6" in prop.name.upper()) else "studio_6"
    csv_filename = f"staytrack_{prop_slug}_repeated_appearances_{date_suffix}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{csv_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.get("/export-pdf")
def export_guests_pdf(
    search: Optional[str] = Query(None, description="Filter by guest name, room, or confirmation"),
    min_nights: Optional[int] = Query(None, ge=1, description="Minimum continuous nights threshold"),
    mode: Optional[str] = Query(None, description="continuous_stay_90, continuous_stay, etc."),
    room: Optional[str] = Query(None, description="Filter by room number"),
    property_id: Optional[int] = Query(None),
    sort_by: str = Query("stay_duration_days"),
    sort_order: str = Query("desc"),
    as_of_date: Optional[str] = Query(None, description="Date for date-wise report (YYYY-MM-DD)"),
    all_time: bool = Query(False, description="If true, include all historical data without date cutoff"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports a high-fidelity PDF report of continuous long-stay guests,
    starting from 30 days+ continuous stay down to lesser continuous stay customers,
    ignoring customers who did not stay continuously in a row.
    """
    try:
        as_of_d = None
        if as_of_date and isinstance(as_of_date, str) and as_of_date.strip():
            try:
                as_of_d = datetime.date.fromisoformat(as_of_date.strip())
            except ValueError:
                pass

        prop = None
        if property_id and isinstance(property_id, int):
            prop = db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            prop = db.query(Property).first()

        pid = prop.id if prop else 1
        pname = prop.name if prop else "Studio 6"

        effective_min = min_nights if isinstance(min_nights, int) else (90 if mode == "continuous_stay_90" else 30)

        prop_name, stays, counts = get_continuous_stays(
            db=db,
            property_id=pid,
            min_nights=effective_min,
            search=search,
            room=room,
            as_of_date=as_of_d,
            all_time=all_time
        )

        if mode == "continuous_stay_30_89":
            stays = [s for s in stays if 30 <= s["total_nights"] < 90]
            counts = {"90+": 0, "30+": len(stays), "21+": 0, "7+": 0}

        # Apply exact same sorting
        if sort_by == "guest_name":
            stays.sort(key=lambda s: s["guest_name"], reverse=(sort_order.lower() == "desc"))
        elif sort_by == "first_date":
            stays.sort(key=lambda s: s["check_in"], reverse=(sort_order.lower() == "desc"))
        else:
            stays.sort(key=lambda s: (-s["total_nights"], s["check_in"]) if sort_order.lower() != "asc" else (s["total_nights"], s["check_in"]))

        pdf_bytes = generate_long_stay_pdf(
            property_name=pname,
            stays=stays,
            counts=counts,
            as_of_date=as_of_d
        )

        date_suffix = as_of_d.strftime("%m-%d-%Y") if as_of_d else get_ny_now().date().strftime("%m-%d-%Y")
        prop_slug = "motel_6" if "MOTEL 6" in pname.upper() else "studio_6"
        if mode == "continuous_stay_90":
            filename = f"staytrack_{prop_slug}_90plus_days_tax_exempt_{date_suffix}.pdf"
        elif mode == "continuous_stay_30_89":
            filename = f"staytrack_{prop_slug}_30to89_days_tax_exempt_{date_suffix}.pdf"
        else:
            filename = f"staytrack_{prop_slug}_30_and_90_continuous_tax_exempt_{date_suffix}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
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
        "original_check_in_date": identity.original_check_in_date.isoformat() if identity.original_check_in_date else None,
        "fixed_rate": identity.fixed_rate,
        "county_exempt_date": (identity.original_check_in_date + datetime.timedelta(days=30)).isoformat() if identity.original_check_in_date else None,
        "state_exempt_date": (identity.original_check_in_date + datetime.timedelta(days=90)).isoformat() if identity.original_check_in_date else None,
        "tax_exempt_status": (
            "Fully Tax Exempt (State + County)" if identity.original_check_in_date and (get_ny_now().date() - identity.original_check_in_date).days >= 90
            else ("County Tax Exempt Only (30+ Days)" if identity.original_check_in_date and (get_ny_now().date() - identity.original_check_in_date).days >= 30
            else "Standard Taxable")
        ),
        "records_count": len(records),
        "timeline": timeline,
        "matches": match_history,
        "assessments": assessment_data
    }


@router.patch("/{identity_id}")
def update_guest_identity(
    identity_id: int,
    req: UpdateGuestIdentityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Allows setting or overriding the original check-in date, fixed rate, verification status, and notes.
    """
    identity = db.query(GuestIdentity).filter(GuestIdentity.id == identity_id).first()
    if not identity:
        raise HTTPException(status_code=404, detail="Guest identity not found")

    if req.original_check_in_date is not None:
        if req.original_check_in_date.strip() == "":
            identity.original_check_in_date = None
        else:
            try:
                identity.original_check_in_date = datetime.date.fromisoformat(req.original_check_in_date.strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format for original_check_in_date (expected YYYY-MM-DD)")

    if req.fixed_rate is not None:
        identity.fixed_rate = req.fixed_rate

    if req.verification_status is not None:
        identity.verification_status = req.verification_status

    if req.notes is not None:
        identity.notes = req.notes

    identity.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(identity)

    log_audit(
        db,
        current_user.id,
        "update_guest_identity",
        f"Updated guest identity #{identity.id} ({identity.normalized_name}): cin={identity.original_check_in_date}, rate={identity.fixed_rate}"
    )

    county_d = (identity.original_check_in_date + datetime.timedelta(days=30)).isoformat() if identity.original_check_in_date else None
    state_d = (identity.original_check_in_date + datetime.timedelta(days=90)).isoformat() if identity.original_check_in_date else None

    return {
        "success": True,
        "identity_id": identity.id,
        "normalized_name": identity.normalized_name,
        "original_check_in_date": identity.original_check_in_date.isoformat() if identity.original_check_in_date else None,
        "fixed_rate": identity.fixed_rate,
        "verification_status": identity.verification_status,
        "notes": identity.notes,
        "county_exempt_date": county_d,
        "state_exempt_date": state_d
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

    # Strict Property Isolation: do not allow merging across different motel properties
    cross_prop = [s for s in secondaries if s.property_id != primary.property_id]
    if cross_prop:
        raise HTTPException(
            status_code=400,
            detail="Cannot merge guest identities across different motel properties. Motel 6 and Studio 6 guest data must remain separate."
        )

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

