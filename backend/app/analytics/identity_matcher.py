import json
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.db.models import GuestIdentity, GuestRecord, GuestIdentityMatch, Property

def match_or_create_guest_identity(
    db: Session,
    property_id: int,
    record_data: Dict[str, Any]
) -> Tuple[GuestIdentity, GuestIdentityMatch]:
    """
    Reconciles a guest record against existing guest identities.
    Returns (GuestIdentity, GuestIdentityMatch).
    """
    normalized_name = record_data.get("normalized_name") or "UNKNOWN"
    first_name = record_data.get("first_name") or ""
    last_name = record_data.get("last_name") or ""
    conf_no = record_data.get("confirmation_number")
    room_no = record_data.get("room_number")
    check_in_date = record_data.get("check_in_date")

    # 1. Search existing identities by confirmation number
    if conf_no:
        existing_record_with_conf = (
            db.query(GuestRecord)
            .join(GuestIdentity, GuestRecord.guest_identity_id == GuestIdentity.id)
            .filter(
                GuestIdentity.property_id == property_id,
                GuestRecord.confirmation_number == conf_no
            )
            .first()
        )
        if existing_record_with_conf and existing_record_with_conf.guest_identity:
            identity = existing_record_with_conf.guest_identity
            match = GuestIdentityMatch(
                guest_identity_id=identity.id,
                match_type="exact_confirmation",
                confidence_score=1.0,
                status="confirmed",
                review_notes="Matched by identical reservation confirmation number."
            )
            return identity, match

    # 2. Search existing identities with same normalized name
    candidates = (
        db.query(GuestIdentity)
        .filter(
            GuestIdentity.property_id == property_id,
            GuestIdentity.normalized_name == normalized_name
        )
        .all()
    )

    if candidates:
        for cand in candidates:
            # Check previous records for this identity
            prev_records = db.query(GuestRecord).filter(GuestRecord.guest_identity_id == cand.id).all()
            same_room_exists = any(r.room_number == room_no for r in prev_records) if room_no else False
            
            if same_room_exists:
                # Same guest name and same room
                match = GuestIdentityMatch(
                    guest_identity_id=cand.id,
                    match_type="name_and_room",
                    confidence_score=0.90,
                    status="confirmed",
                    review_notes=f"Matched by name and historical room {room_no}."
                )
                return cand, match
            else:
                # Same name but different room
                # If there's only 1 candidate, we link with provisional review status
                match = GuestIdentityMatch(
                    guest_identity_id=cand.id,
                    match_type="name_diff_room",
                    confidence_score=0.75,
                    status="proposed",
                    review_notes=f"Same name but different room ({room_no}). Marked for owner review."
                )
                return cand, match

    # 3. No match found: create new GuestIdentity
    new_identity = GuestIdentity(
        property_id=property_id,
        primary_first_name=first_name or normalized_name.split()[0] if normalized_name else "",
        primary_last_name=last_name or (" ".join(normalized_name.split()[1:]) if len(normalized_name.split()) > 1 else ""),
        normalized_name=normalized_name,
        verification_status="verified" if conf_no and room_no else "provisional",
        notes="Created from imported report."
    )
    db.add(new_identity)
    db.flush()

    match = GuestIdentityMatch(
        guest_identity_id=new_identity.id,
        match_type="initial_creation",
        confidence_score=1.0,
        status="confirmed",
        review_notes="Initial guest profile created."
    )
    return new_identity, match
