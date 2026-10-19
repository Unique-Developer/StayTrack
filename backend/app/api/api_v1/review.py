import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import (
    GuestIdentityMatch,
    GuestIdentity,
    GuestRecord,
    StayAssessment,
    User
)
from app.analytics.stay_detector import recalculate_all_analytics
from app.api.deps import get_current_user, log_audit

router = APIRouter(prefix="/review", tags=["review"])

@router.get("/queue")
def get_review_queue(db: Session = Depends(get_db)):
    """
    Returns items requiring motel owner verification:
    1. Proposed identity matches (e.g. same name across different rooms/dates)
    2. Assessments marked 'Needs Verification'
    """
    proposed_matches = (
        db.query(GuestIdentityMatch)
        .filter(GuestIdentityMatch.status == "proposed")
        .all()
    )

    matches_list = []
    for m in proposed_matches:
        rec = m.guest_record
        ident = m.guest_identity
        matches_list.append({
            "match_id": m.id,
            "match_type": m.match_type,
            "confidence_score": m.confidence_score,
            "review_notes": m.review_notes,
            "record": {
                "id": rec.id,
                "confirmation_number": rec.confirmation_number,
                "room_number": rec.room_number,
                "guest_name": rec.normalized_name,
                "check_in_date": rec.check_in_date.isoformat() if rec.check_in_date else None,
                "nights": rec.number_of_nights,
                "report_date": rec.report.report_date.isoformat() if rec.report else None
            } if rec else None,
            "candidate_identity": {
                "id": ident.id,
                "name": ident.normalized_name,
                "status": ident.verification_status
            } if ident else None
        })

    uncertain_assessments = (
        db.query(StayAssessment)
        .filter(
            StayAssessment.is_active_in_window == True,
            StayAssessment.verification_status == "Needs Verification"
        )
        .all()
    )

    assessments_list = []
    for a in uncertain_assessments:
        assessments_list.append({
            "assessment_id": a.id,
            "guest_identity_id": a.guest_identity_id,
            "guest_name": a.guest_identity.normalized_name,
            "mode": a.mode,
            "stay_duration_days": a.stay_duration_days,
            "reporting_dates_count": a.reporting_dates_count,
            "rooms": json.loads(a.room_numbers or "[]"),
            "confirmations": json.loads(a.confirmation_numbers or "[]"),
            "evidence_source": a.evidence_source,
            "notes": a.notes
        })

    return {
        "pending_matches_count": len(matches_list),
        "uncertain_assessments_count": len(assessments_list),
        "proposed_matches": matches_list,
        "uncertain_assessments": assessments_list
    }


@router.post("/matches/{match_id}/confirm")
def confirm_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    match = db.query(GuestIdentityMatch).filter(GuestIdentityMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    match.status = "confirmed"
    match.reviewed_by_user_id = current_user.id
    match.review_notes = (match.review_notes or "") + " [Confirmed by owner]"
    db.commit()

    prop_id = match.guest_identity.property_id if match.guest_identity else 1
    recalculate_all_analytics(db, prop_id)

    log_audit(db, current_user.id, "confirm_match", "guest_identity_match", str(match.id))
    return {"success": True, "message": "Identity match confirmed."}


@router.post("/matches/{match_id}/reject")
def reject_match_and_split(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    match = db.query(GuestIdentityMatch).filter(GuestIdentityMatch.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    rec = match.guest_record
    if not rec:
        raise HTTPException(status_code=400, detail="Associated guest record not found")

    prop_id = match.guest_identity.property_id if match.guest_identity else 1

    # Split into new independent identity
    new_identity = GuestIdentity(
        property_id=prop_id,
        primary_first_name=rec.first_name or "",
        primary_last_name=rec.last_name or "",
        normalized_name=rec.normalized_name,
        verification_status="verified",
        notes=f"Created via manual split from identity #{match.guest_identity_id}."
    )
    db.add(new_identity)
    db.flush()

    rec.guest_identity_id = new_identity.id
    match.status = "rejected"
    match.reviewed_by_user_id = current_user.id
    match.review_notes = f"Rejected merge by owner. Split into identity #{new_identity.id}."
    db.commit()

    recalculate_all_analytics(db, prop_id)

    log_audit(
        db,
        current_user.id,
        "split_guest_identity",
        "guest_identity",
        str(new_identity.id),
        {"from_identity_id": match.guest_identity_id, "record_id": rec.id}
    )

    return {"success": True, "message": "Identity split successfully into separate guest profile."}


@router.post("/assessments/{assessment_id}/verify")
def verify_assessment(
    assessment_id: int,
    action: str = Body(..., embed=True, description="verify or reject"),
    notes: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assessment = db.query(StayAssessment).filter(StayAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if action == "verify":
        assessment.verification_status = "Verified"
    elif action == "reject":
        assessment.verification_status = "Rejected"
    else:
        raise HTTPException(status_code=400, detail="Action must be 'verify' or 'reject'")

    if notes:
        assessment.notes = (assessment.notes or "") + f" [{notes}]"

    db.commit()
    log_audit(db, current_user.id, f"assessment_{action}", "stay_assessment", str(assessment.id))
    return {"success": True, "status": assessment.verification_status}
