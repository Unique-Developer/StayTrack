import os
import io
import datetime
import pytest
import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.db.init_db import init_db
from app.db.models import (
    User,
    Property,
    UploadedReport,
    GuestRecord,
    GuestIdentity,
    StayAssessment,
    GuestIdentityMatch,
    ReportingCalendar
)
from app.analytics.report_excel import generate_report_excel
from app.analytics.rolling_window import calculate_rolling_window
from app.analytics.stay_detector import recalculate_all_analytics
from app.main import app

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    init_db(db)
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    admin = db_session.query(User).first()
    token = create_access_token(admin.id)
    c.headers.update({"Authorization": f"Bearer {token}"})
    yield c
    app.dependency_overrides.clear()


def test_download_report_excel_format(db_session, client):
    """Verify downloading a report produces a valid formatted Excel file without requiring physical PDF."""
    prop = db_session.query(Property).first()
    rep_date = datetime.date(2026, 10, 5)

    report = UploadedReport(
        property_id=prop.id,
        original_filename="departures_2026-10-05.pdf",
        stored_filename="report_virtual_12345",
        file_hash="virtual_hash_12345",
        file_size_bytes=4096,
        report_type="departures",
        report_date=rep_date,
        report_run_datetime="Oct 05, 2026 • 08:30 AM",
        status="completed",
        total_rows_extracted=2,
        valid_rows_count=2,
        is_active=True
    )
    db_session.add(report)
    db_session.flush()

    ident1 = GuestIdentity(
        property_id=prop.id,
        primary_first_name="JOHN",
        primary_last_name="DOE",
        normalized_name="JOHN DOE",
        verification_status="verified"
    )
    ident2 = GuestIdentity(
        property_id=prop.id,
        primary_first_name="JANE",
        primary_last_name="SMITH",
        normalized_name="JANE SMITH",
        verification_status="verified"
    )
    db_session.add_all([ident1, ident2])
    db_session.flush()

    rec1 = GuestRecord(
        report_id=report.id,
        guest_identity_id=ident1.id,
        confirmation_number="CONF101",
        room_number="101",
        first_name="JOHN",
        last_name="DOE",
        normalized_name="JOHN DOE",
        check_in_date=datetime.date(2026, 9, 5),
        number_of_nights=30,
        calculated_departure_date=datetime.date(2026, 10, 5),
        status="Checked Out",
        total_guest_balance=150.50
    )
    rec2 = GuestRecord(
        report_id=report.id,
        guest_identity_id=ident2.id,
        confirmation_number="CONF102",
        room_number="102",
        first_name="JANE",
        last_name="SMITH",
        normalized_name="JANE SMITH",
        check_in_date=datetime.date(2026, 10, 1),
        number_of_nights=4,
        calculated_departure_date=datetime.date(2026, 10, 5),
        status="Checked Out",
        total_guest_balance=0.0
    )
    db_session.add_all([rec1, rec2])
    db_session.commit()

    # Request Excel download
    res = client.get(f"/api/v1/reports/{report.id}/download")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "departures_2026-10-05_data.xlsx" in res.headers["content-disposition"]

    # Verify openpyxl can load and read the spreadsheet
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    ws = wb.active
    assert ws.title == "Departures Data"
    assert "StayTrack" in ws.cell(row=1, column=1).value

    # Verify metadata
    assert ws.cell(row=2, column=2).value == "STUDIO 6 - STAFFORD, VA (#3756)"
    assert ws.cell(row=2, column=5).value == "10-05-2026"

    # Verify headers in row 6
    headers = [ws.cell(row=6, column=c).value for c in range(1, 15)]
    assert "Conf #" in headers
    assert "Room" in headers
    assert "Guest Name" in headers
    assert "Total Balance ($)" in headers

    # Verify data in rows 7 & 8
    row7_name = ws.cell(row=7, column=3).value
    row8_name = ws.cell(row=8, column=3).value
    names = {row7_name, row8_name}
    assert "JOHN DOE" in names
    assert "JANE SMITH" in names

    # Verify totals row
    total_label = ws.cell(row=9, column=3).value
    assert "Total (2 records)" in total_label
    total_nights = ws.cell(row=9, column=6).value
    assert total_nights == 34
    total_bal = ws.cell(row=9, column=10).value
    assert abs(total_bal - 150.50) < 0.01


def test_delete_report_in_both_motels(db_session, client):
    """Verify deleting reports works across both motels and cleanly deletes reports, records, orphan identities, and recalcs."""
    p1 = db_session.query(Property).filter(Property.property_code == "3756").first()
    p2 = db_session.query(Property).filter(Property.property_code == "MOTEL6").first()

    # 1. Setup Studio 6 report (Property 1)
    r1 = UploadedReport(
        property_id=p1.id,
        original_filename="departures_studio6_2026-10-01.pdf",
        stored_filename="rep_p1_01",
        file_hash="hash_p1_01",
        file_size_bytes=2048,
        report_type="departures",
        report_date=datetime.date(2026, 10, 1),
        status="completed",
        total_rows_extracted=1,
        valid_rows_count=1,
        is_active=True
    )
    db_session.add(r1)
    db_session.flush()

    id1 = GuestIdentity(property_id=p1.id, primary_first_name="ALICE", primary_last_name="WONDER", normalized_name="ALICE WONDER")
    db_session.add(id1)
    db_session.flush()

    rec1 = GuestRecord(
        report_id=r1.id,
        guest_identity_id=id1.id,
        confirmation_number="CONF_P1",
        room_number="101",
        first_name="ALICE",
        last_name="WONDER",
        normalized_name="ALICE WONDER",
        check_in_date=datetime.date(2026, 9, 1),
        number_of_nights=30,
        calculated_departure_date=datetime.date(2026, 10, 1)
    )
    db_session.add(rec1)
    db_session.flush()

    match1 = GuestIdentityMatch(
        guest_record_id=rec1.id,
        guest_identity_id=id1.id,
        match_type="exact",
        status="confirmed"
    )
    db_session.add(match1)

    # 2. Setup Motel 6 report (Property 2)
    r2 = UploadedReport(
        property_id=p2.id,
        original_filename="departures_motel6_2026-10-02.pdf",
        stored_filename="rep_p2_02",
        file_hash="hash_p2_02",
        file_size_bytes=2048,
        report_type="departures",
        report_date=datetime.date(2026, 10, 2),
        status="completed",
        total_rows_extracted=1,
        valid_rows_count=1,
        is_active=True
    )
    db_session.add(r2)
    db_session.flush()

    id2 = GuestIdentity(property_id=p2.id, primary_first_name="BOB", primary_last_name="BUILDER", normalized_name="BOB BUILDER")
    db_session.add(id2)
    db_session.flush()

    rec2 = GuestRecord(
        report_id=r2.id,
        guest_identity_id=id2.id,
        confirmation_number="CONF_P2",
        room_number="202",
        first_name="BOB",
        last_name="BUILDER",
        normalized_name="BOB BUILDER",
        check_in_date=datetime.date(2026, 9, 2),
        number_of_nights=30,
        calculated_departure_date=datetime.date(2026, 10, 2)
    )
    db_session.add(rec2)
    db_session.flush()

    match2 = GuestIdentityMatch(
        guest_record_id=rec2.id,
        guest_identity_id=id2.id,
        match_type="exact",
        status="confirmed"
    )
    db_session.add(match2)
    db_session.commit()

    # Recalculate both
    recalculate_all_analytics(db_session, p1.id)
    recalculate_all_analytics(db_session, p2.id)

    r1_id = r1.id
    r2_id = r2.id
    id1_id = id1.id
    id2_id = id2.id
    rec1_id = rec1.id
    rec2_id = rec2.id

    p1_reports_before = db_session.query(UploadedReport).filter(UploadedReport.property_id == p1.id).count()
    p2_reports_before = db_session.query(UploadedReport).filter(UploadedReport.property_id == p2.id).count()
    p1_recs_before = db_session.query(GuestRecord).join(UploadedReport).filter(UploadedReport.property_id == p1.id).count()
    p2_recs_before = db_session.query(GuestRecord).join(UploadedReport).filter(UploadedReport.property_id == p2.id).count()

    # Verify both exist before deletion
    assert db_session.query(UploadedReport).filter(UploadedReport.id == r1_id).first() is not None
    assert db_session.query(UploadedReport).filter(UploadedReport.id == r2_id).first() is not None
    assert db_session.query(GuestIdentity).filter(GuestIdentity.id == id1_id).first() is not None
    assert db_session.query(GuestIdentity).filter(GuestIdentity.id == id2_id).first() is not None

    # 3. Delete Motel 6 report (r2)
    del_res = client.delete(f"/api/v1/reports/{r2_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify Motel 6 report, its records, matches, and orphan identity are completely deleted
    assert db_session.query(UploadedReport).filter(UploadedReport.id == r2_id).first() is None
    assert db_session.query(GuestRecord).filter(GuestRecord.report_id == r2_id).count() == 0
    assert db_session.query(GuestIdentityMatch).filter(GuestIdentityMatch.guest_record_id == rec2_id).count() == 0
    # BOB BUILDER only existed in r2, so orphan identity must be deleted
    assert db_session.query(GuestIdentity).filter(GuestIdentity.id == id2_id).first() is None
    # Motel 6 reports count decreased by 1
    assert db_session.query(UploadedReport).filter(UploadedReport.property_id == p2.id).count() == p2_reports_before - 1
    assert db_session.query(GuestRecord).join(UploadedReport).filter(UploadedReport.property_id == p2.id).count() == p2_recs_before - 1

    # Verify Studio 6 data is completely unaffected
    assert db_session.query(UploadedReport).filter(UploadedReport.id == r1_id).first() is not None
    assert db_session.query(GuestRecord).filter(GuestRecord.report_id == r1_id).count() == 1
    assert db_session.query(GuestIdentity).filter(GuestIdentity.id == id1_id).first() is not None
    assert db_session.query(UploadedReport).filter(UploadedReport.property_id == p1.id).count() == p1_reports_before

    # 4. Now delete Studio 6 report (r1)
    del_res1 = client.delete(f"/api/v1/reports/{r1_id}")
    assert del_res1.status_code == 200
    assert del_res1.json()["success"] is True

    # Verify r1 and ALICE WONDER are deleted
    assert db_session.query(UploadedReport).filter(UploadedReport.id == r1_id).first() is None
    assert db_session.query(GuestRecord).filter(GuestRecord.report_id == r1_id).count() == 0
    assert db_session.query(GuestIdentity).filter(GuestIdentity.id == id1_id).first() is None
    assert db_session.query(UploadedReport).filter(UploadedReport.property_id == p1.id).count() == p1_reports_before - 1
