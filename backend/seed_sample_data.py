import glob
import os
import datetime
from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.db.models import Property, UploadedReport, GuestRecord
from app.parsers.pdf_parser import parse_departures_pdf
from app.parsers.normalizers import parse_date_flexible
from app.core.storage import storage_service
from app.analytics.identity_matcher import match_or_create_guest_identity
from app.analytics.stay_detector import recalculate_all_analytics

def seed_sample_reports():
    print("[Seed] Initializing database...")
    init_db()
    db = SessionLocal()
    try:
        prop = db.query(Property).first()
        if not prop:
            print("[Seed] No property found.")
            return

        sample_files = sorted(glob.glob("tests/fixtures/sample_reports/*.pdf"))
        print(f"[Seed] Found {len(sample_files)} sample PDFs to import.")

        for f in sample_files:
            filename = os.path.basename(f)
            with open(f, "rb") as pdf_file:
                file_bytes = pdf_file.read()

            file_hash = storage_service.calculate_hash(file_bytes)
            
            # Check if already imported
            existing = db.query(UploadedReport).filter(UploadedReport.file_hash == file_hash).first()
            if existing:
                print(f"[Seed] Report {filename} already exists (id={existing.id}). Skipping.")
                continue

            parsed = parse_departures_pdf(f)
            stored_name, _, file_size = storage_service.save_file(file_bytes, filename)

            report = UploadedReport(
                property_id=prop.id,
                original_filename=filename,
                stored_filename=stored_name,
                file_hash=file_hash,
                file_size_bytes=file_size,
                report_type="departures",
                report_date=parsed.report_date,
                report_run_datetime=parsed.report_run_datetime,
                generated_by_user=parsed.generated_by,
                status="completed",
                total_rows_extracted=parsed.total_rows,
                valid_rows_count=parsed.valid_rows,
                is_active=True
            )
            db.add(report)
            db.flush()

            for rec in parsed.records:
                c_in = parse_date_flexible(rec["check_in_date"])
                c_out = parse_date_flexible(rec["calculated_departure_date"])

                ident, match = match_or_create_guest_identity(db, prop.id, rec)
                guest_rec = GuestRecord(
                    report_id=report.id,
                    guest_identity_id=ident.id,
                    raw_confirmation_number=rec["raw_confirmation_number"],
                    confirmation_number=rec["confirmation_number"],
                    raw_guest_name=rec["raw_guest_name"],
                    first_name=rec["first_name"],
                    last_name=rec["last_name"],
                    normalized_name=rec["normalized_name"],
                    additional_guests=rec["additional_guests"],
                    room_number=rec["room_number"],
                    check_in_date=c_in,
                    number_of_nights=rec["number_of_nights"],
                    calculated_departure_date=c_out,
                    status=rec["status"],
                    total_guest_balance=rec["total_guest_balance"],
                    actual_departed_time=rec["actual_departed_time"],
                    vip_guest=rec["vip_guest"],
                    guest_tier=rec["guest_tier"],
                    housekeeping_remarks=rec["housekeeping_remarks"],
                    source_page=rec["source_page"],
                    source_row_index=rec["source_row_index"],
                    confidence_score=rec["confidence_score"],
                    validation_flags=str(rec["validation_flags"])
                )
                db.add(guest_rec)
                db.flush()
                match.guest_record_id = guest_rec.id
                db.add(match)

            db.commit()
            print(f"[Seed] Successfully imported {filename} (Date: {parsed.report_date}, Rows: {parsed.valid_rows})")

        recalculate_all_analytics(db, prop.id)
        print("[Seed] Successfully recalculated rolling window and stay assessments.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_sample_reports()
