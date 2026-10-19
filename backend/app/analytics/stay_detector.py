import json
import datetime
from typing import Dict, Any, List, Set, Tuple
from sqlalchemy.orm import Session
from app.db.models import (
    GuestIdentity,
    GuestRecord,
    UploadedReport,
    StayAssessment,
    SystemSetting,
    Property
)
from app.analytics.rolling_window import calculate_rolling_window
from app.core.config import settings

def get_analytics_settings(db: Session) -> Tuple[int, int, str]:
    """Retrieve continuous stay days, min appearance days, and departure convention."""
    cont_days = settings.DEFAULT_CONTINUOUS_STAY_DAYS
    app_days = settings.DEFAULT_MIN_APPEARANCE_DAYS
    convention = settings.DEFAULT_DEPARTURE_CONVENTION

    s1 = db.query(SystemSetting).filter(SystemSetting.key == "continuous_stay_days").first()
    if s1 and s1.value:
        try:
            cont_days = int(s1.value)
        except ValueError:
            pass

    s2 = db.query(SystemSetting).filter(SystemSetting.key == "min_appearance_days").first()
    if s2 and s2.value:
        try:
            app_days = int(s2.value)
        except ValueError:
            pass

    s3 = db.query(SystemSetting).filter(SystemSetting.key == "departure_convention").first()
    if s3 and s3.value:
        convention = s3.value

    return cont_days, app_days, convention


def recalculate_all_analytics(db: Session, property_id: int):
    """
    Recalculates rolling window and both Mode A and Mode B assessments for a property.
    Deletes outdated assessments for the property and populates updated findings.
    """
    window_data = calculate_rolling_window(db, property_id)
    active_date_strs = set(window_data.get("active_window_dates", []))
    
    if not active_date_strs:
        # No active dates
        db.query(StayAssessment).filter(StayAssessment.property_id == property_id).delete()
        db.commit()
        return

    active_dates = {datetime.date.fromisoformat(d) for d in active_date_strs}
    cont_threshold, app_threshold, convention = get_analytics_settings(db)

    # Clean existing assessments for property
    db.query(StayAssessment).filter(StayAssessment.property_id == property_id).delete()

    # Fetch all identities for this property
    identities = db.query(GuestIdentity).filter(GuestIdentity.property_id == property_id).all()

    for identity in identities:
        # Fetch all records for this identity from active reports
        records = (
            db.query(GuestRecord)
            .join(UploadedReport, GuestRecord.report_id == UploadedReport.id)
            .filter(
                GuestRecord.guest_identity_id == identity.id,
                UploadedReport.status == "completed",
                UploadedReport.is_active == True
            )
            .order_by(GuestRecord.check_in_date.asc(), UploadedReport.report_date.asc())
            .all()
        )

        if not records:
            continue

        # Filter records within the active window reporting dates
        window_records = [r for r in records if r.report.report_date in active_dates]
        if not window_records:
            continue

        # -------------------------------------------------------------
        # Mode B: Repeated Daily Appearance Detection
        # -------------------------------------------------------------
        distinct_appearance_dates = sorted(list({r.report.report_date for r in window_records}))
        distinct_rooms = sorted(list({r.room_number for r in window_records if r.room_number}))
        distinct_confs = sorted(list({r.confirmation_number for r in window_records if r.confirmation_number}))
        
        appearance_count = len(distinct_appearance_dates)
        if appearance_count >= app_threshold:
            # Mode B record meets threshold!
            first_seen = distinct_appearance_dates[0]
            last_seen = distinct_appearance_dates[-1]

            # Verification status for Mode B
            # If records have low confidence or multiple rooms without review, mark provisional
            confidences = [r.confidence_score for r in window_records]
            avg_conf = sum(confidences) / len(confidences) if confidences else 1.0
            v_status = "Verified" if avg_conf >= 0.85 else "Needs Verification"

            b_assessment = StayAssessment(
                guest_identity_id=identity.id,
                property_id=property_id,
                mode="repeated_appearance",
                is_active_in_window=True,
                stay_duration_days=appearance_count,
                reporting_dates_count=appearance_count,
                first_date=first_seen,
                last_date=last_seen,
                date_list=json.dumps([d.isoformat() for d in distinct_appearance_dates]),
                confirmation_numbers=json.dumps(distinct_confs),
                room_numbers=json.dumps(distinct_rooms),
                evidence_source=f"Found in {appearance_count} distinct daily departure reports.",
                verification_status=v_status,
                notes=f"Distinct appearance count ({appearance_count}) meets threshold ({app_threshold})."
            )
            db.add(b_assessment)

        # -------------------------------------------------------------
        # Mode A: Continuous Stay Detection
        # -------------------------------------------------------------
        # Calculate stay intervals from reservations
        # Each record has check_in_date and calculated_departure_date (check_in + nights)
        stay_spans = []
        for r in window_records:
            c_in = r.check_in_date
            nights = r.number_of_nights or 0
            if c_in and nights > 0:
                c_out = r.calculated_departure_date or (c_in + datetime.timedelta(days=nights))
                stay_spans.append({
                    "start": c_in,
                    "end": c_out,
                    "nights": nights,
                    "room": r.room_number,
                    "conf": r.confirmation_number,
                    "record_id": r.id,
                    "flags": r.validation_flags
                })

        # Find maximum continuous duration (individual single long reservation or chained spans)
        # Check single reservations meeting threshold
        max_duration = 0
        best_span = None
        evidence_notes = []

        for span in stay_spans:
            if span["nights"] > max_duration:
                max_duration = span["nights"]
                best_span = span

        # Also check chained reservations (where span B starts on or before span A ends)
        if len(stay_spans) > 1:
            sorted_spans = sorted(stay_spans, key=lambda s: s["start"])
            current_chain_start = sorted_spans[0]["start"]
            current_chain_end = sorted_spans[0]["end"]
            current_chain_nights = sorted_spans[0]["nights"]

            for next_span in sorted_spans[1:]:
                # If next span starts on or within 1 day of previous span end (continuous stay chain)
                if next_span["start"] <= current_chain_end + datetime.timedelta(days=1):
                    current_chain_end = max(current_chain_end, next_span["end"])
                    current_chain_nights = (current_chain_end - current_chain_start).days
                    if current_chain_nights > max_duration:
                        max_duration = current_chain_nights
                        best_span = {
                            "start": current_chain_start,
                            "end": current_chain_end,
                            "nights": current_chain_nights,
                            "room": next_span["room"],
                            "conf": next_span["conf"]
                        }
                        evidence_notes.append("Chained consecutive reservations.")
                else:
                    # Chain broken, start new chain
                    current_chain_start = next_span["start"]
                    current_chain_end = next_span["end"]
                    current_chain_nights = next_span["nights"]

        if max_duration >= cont_threshold and best_span:
            # Mode A criteria met!
            is_verified = True
            v_notes = []

            # Check if any validation flags or missing data
            if best_span.get("flags") and "DEPARTURE_MISMATCH" in str(best_span.get("flags")):
                is_verified = False
                v_notes.append("Report departure mismatch detected.")

            a_assessment = StayAssessment(
                guest_identity_id=identity.id,
                property_id=property_id,
                mode="continuous_stay",
                is_active_in_window=True,
                stay_duration_days=max_duration,
                reporting_dates_count=len(distinct_appearance_dates),
                first_date=best_span["start"],
                last_date=best_span["end"],
                date_list=json.dumps([best_span["start"].isoformat(), best_span["end"].isoformat()]),
                confirmation_numbers=json.dumps(distinct_confs),
                room_numbers=json.dumps(distinct_rooms),
                evidence_source=f"Reservation check-in {best_span['start'].isoformat()} to {best_span['end'].isoformat()} ({max_duration} nights).",
                verification_status="Verified" if is_verified else "Needs Verification",
                notes="; ".join(v_notes) if v_notes else f"Continuous stay duration ({max_duration} days) meets threshold ({cont_threshold} days)."
            )
            db.add(a_assessment)

    db.commit()
