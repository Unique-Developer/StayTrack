import os
import uuid
import datetime
from pathlib import Path
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import (
    UploadedReport,
    Property,
    GuestRecord,
    GuestIdentity,
    GuestIdentityMatch,
    ReportProcessingJob,
    User
)
from app.parsers.pdf_parser import parse_departures_pdf
from app.parsers.normalizers import parse_date_flexible
from app.core.storage import storage_service
from app.core.config import settings
from app.analytics.identity_matcher import match_or_create_guest_identity
from app.analytics.stay_detector import recalculate_all_analytics
from app.schemas.models import (
    ReportPreviewFile,
    ReportCommitRequest,
    ReportResponse
)
from app.core.time_utils import to_utc_iso, to_ny_display_str
from app.api.deps import get_current_user, log_audit

router = APIRouter(prefix="/reports", tags=["reports"])

# In-memory staging for uploaded files awaiting user review/confirmation
TEMP_STAGING_DIR = settings.BASE_DIR / "storage" / "staging"
TEMP_STAGING_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/preview", response_model=List[ReportPreviewFile])
async def preview_reports(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 1 of Import Workflow:
    Accepts daily PDF reports, extracts text/table data, checks file hashes and existing dates,
    and returns an editable preview before committing to persistent storage.
    """
    prop = db.query(Property).first()
    property_id = prop.id if prop else 1
    results = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            continue

        file_bytes = await file.read()
        file_hash = storage_service.calculate_hash(file_bytes)
        file_size = len(file_bytes)

        # 1. Check duplicate file hash
        existing_report_hash = (
            db.query(UploadedReport)
            .filter(UploadedReport.file_hash == file_hash, UploadedReport.is_active == True)
            .first()
        )

        # Save to staging
        temp_id = str(uuid.uuid4())
        staging_path = TEMP_STAGING_DIR / f"{temp_id}.pdf"
        with open(staging_path, "wb") as f:
            f.write(file_bytes)

        # 2. Parse PDF
        parsed = parse_departures_pdf(str(staging_path))

        # 3. Check if report for this date already exists
        existing_report_date = None
        if parsed.report_date:
            existing_report_date = (
                db.query(UploadedReport)
                .filter(
                    UploadedReport.property_id == property_id,
                    UploadedReport.report_date == parsed.report_date,
                    UploadedReport.status == "completed",
                    UploadedReport.is_active == True
                )
                .first()
            )

        preview_file = ReportPreviewFile(
            temp_file_id=temp_id,
            original_filename=file.filename,
            file_size_bytes=file_size,
            file_hash=file_hash,
            is_duplicate=existing_report_hash is not None,
            duplicate_report_id=existing_report_hash.id if existing_report_hash else None,
            existing_report_for_date_id=existing_report_date.id if existing_report_date else None,
            property_name=parsed.property_name,
            property_code=parsed.property_code,
            report_date=parsed.report_date.isoformat() if parsed.report_date else None,
            report_run_datetime=parsed.report_run_datetime,
            generated_by=parsed.generated_by,
            total_rows=parsed.total_rows,
            valid_rows=parsed.valid_rows,
            has_warnings=parsed.has_warnings,
            warnings=parsed.warnings,
            extraction_method=parsed.extraction_method,
            records=parsed.records
        )
        results.append(preview_file)

    log_audit(db, current_user.id, "upload_preview", "report", details={"files_count": len(results)})
    return results


@router.post("/commit")
async def commit_reports(
    payload: ReportCommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 2 of Import Workflow:
    Persists original PDF in storage, saves report & guest records in database,
    performs identity reconciliation, and triggers analytics recalculation.
    """
    prop = db.query(Property).first()
    property_id = prop.id if prop else 1
    committed_ids = []

    for item in payload.files:
        staging_path = TEMP_STAGING_DIR / f"{item.temp_file_id}.pdf"
        if not staging_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Staging file {item.temp_file_id} not found or expired."
            )

        with open(staging_path, "rb") as f:
            file_bytes = f.read()

        # Parse date
        rep_date = parse_date_flexible(item.report_date)
        if not rep_date:
            raise HTTPException(status_code=400, detail=f"Invalid report date: {item.report_date}")

        # Handle replacement if indicated
        if item.replace_existing_id:
            old_rep = db.query(UploadedReport).filter(UploadedReport.id == item.replace_existing_id).first()
            if old_rep:
                old_rep.is_active = False
                log_audit(db, current_user.id, "replace_report", "report", str(old_rep.id), {"replaced_by_temp_id": item.temp_file_id})

        # Save to persistent storage
        stored_name, file_hash, file_size = storage_service.save_file(file_bytes, f"departures_{rep_date.isoformat()}.pdf")

        # Create UploadedReport
        orig_filename = item.original_filename or f"departures_{rep_date.isoformat()}.pdf"
        report = UploadedReport(
            property_id=item.property_id or property_id,
            original_filename=orig_filename,
            stored_filename=stored_name,
            file_hash=file_hash,
            file_size_bytes=file_size,
            report_type="departures",
            report_date=rep_date,
            report_run_datetime=item.report_run_datetime,
            status="completed",
            total_rows_extracted=len(item.records),
            valid_rows_count=len(item.records),
            is_active=True
        )
        db.add(report)
        db.flush()

        # Insert GuestRecords and reconcile identities
        for rec in item.records:
            rec_dict = rec.model_dump() if hasattr(rec, "model_dump") else rec.dict()
            rec_c_in = parse_date_flexible(rec_dict.get("check_in_date"))
            rec_c_out = parse_date_flexible(rec_dict.get("calculated_departure_date"))

            # Reconciliation
            identity, match = match_or_create_guest_identity(db, property_id, rec_dict)

            guest_rec = GuestRecord(
                report_id=report.id,
                guest_identity_id=identity.id,
                raw_confirmation_number=rec_dict.get("raw_confirmation_number"),
                confirmation_number=rec_dict.get("confirmation_number"),
                raw_guest_name=rec_dict.get("raw_guest_name"),
                first_name=rec_dict.get("first_name"),
                last_name=rec_dict.get("last_name"),
                normalized_name=rec_dict.get("normalized_name"),
                additional_guests=rec_dict.get("additional_guests"),
                room_number=rec_dict.get("room_number"),
                check_in_date=rec_c_in,
                number_of_nights=rec_dict.get("number_of_nights"),
                calculated_departure_date=rec_c_out,
                status=rec_dict.get("status") or "Checked Out",
                total_guest_balance=rec_dict.get("total_guest_balance") or 0.0,
                actual_departed_time=rec_dict.get("actual_departed_time"),
                vip_guest=rec_dict.get("vip_guest") or "No",
                guest_tier=rec_dict.get("guest_tier"),
                housekeeping_remarks=rec_dict.get("housekeeping_remarks"),
                source_page=rec_dict.get("source_page", 1),
                source_row_index=rec_dict.get("source_row_index", 0),
                confidence_score=rec_dict.get("confidence_score", 1.0),
                validation_flags=str(rec_dict.get("validation_flags", []))
            )
            db.add(guest_rec)
            db.flush()

            # Link match to guest_record_id
            match.guest_record_id = guest_rec.id
            db.add(match)

        committed_ids.append(report.id)
        # Clean up staging file
        try:
            staging_path.unlink()
        except Exception:
            pass

    db.commit()

    # Recalculate rolling window and stay assessments
    recalculate_all_analytics(db, property_id)

    log_audit(
        db,
        current_user.id,
        "commit_import",
        "report",
        details={"report_ids": committed_ids, "count": len(committed_ids)}
    )

    return {
        "success": True,
        "message": f"Successfully imported {len(committed_ids)} reports.",
        "imported_report_ids": committed_ids
    }


@router.get("", response_model=List[ReportResponse])
def get_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    reports = (
        db.query(UploadedReport)
        .order_by(UploadedReport.report_date.desc(), UploadedReport.created_at.desc())
        .all()
    )
    result = []
    for r in reports:
        result.append(
            ReportResponse(
                id=r.id,
                property_id=r.property_id,
                property_name=r.property.name if r.property else "Studio 6",
                original_filename=r.original_filename,
                file_size_bytes=r.file_size_bytes,
                report_date=r.report_date.isoformat(),
                report_run_datetime=r.report_run_datetime,
                status=r.status,
                total_rows_extracted=r.total_rows_extracted,
                valid_rows_count=r.valid_rows_count,
                created_at=to_utc_iso(r.created_at) or r.created_at.isoformat(),
                created_at_ny=to_ny_display_str(r.created_at),
                is_active=r.is_active
            )
        )
    return result


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = db.query(UploadedReport).filter(UploadedReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    file_path = storage_service.get_file_path(report.stored_filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical PDF file missing from storage")

    log_audit(db, current_user.id, "download_pdf", "report", str(report.id))
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=report.original_filename
    )


@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = db.query(UploadedReport).filter(UploadedReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    prop_id = report.property_id
    storage_service.delete_file(report.stored_filename)
    db.delete(report)
    db.commit()

    # Recalculate analytics
    recalculate_all_analytics(db, prop_id)

    log_audit(db, current_user.id, "delete_report", "report", str(report_id))
    return {"success": True, "message": "Report deleted successfully"}
