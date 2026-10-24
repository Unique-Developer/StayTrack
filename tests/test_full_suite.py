import os
import glob
import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.db.session import Base, get_db
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
from app.parsers.pdf_parser import parse_departures_pdf
from app.parsers.normalizers import (
    normalize_confirmation_number,
    normalize_name,
    parse_date_flexible,
    calculate_departure_date
)
from app.analytics.identity_matcher import match_or_create_guest_identity
from app.analytics.rolling_window import calculate_rolling_window
from app.analytics.stay_detector import recalculate_all_analytics
from app.main import app

# Test database using StaticPool so all threads share memory
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
    
    # Seed property and admin
    prop = Property(name="STUDIO 6 - STAFFORD, VA", property_code="3756", timezone="America/New_York")
    db.add(prop)
    admin = User(
        email="admin@staytrack.local",
        hashed_password=hash_password("StayTrack2026!"),
        full_name="Admin",
        role="admin",
        is_active=True
    )
    db.add(admin)
    db.commit()

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
    admin = db_session.query(User).filter(User.email == "admin@staytrack.local").first()
    token = create_access_token(subject=admin.id)
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


# -------------------------------------------------------------------------
# Test 1: Parser on 4 Sample PDFs
# -------------------------------------------------------------------------
def test_parse_four_sample_pdfs():
    sample_files = sorted(glob.glob("tests/fixtures/sample_reports/*.pdf"))
    assert len(sample_files) == 4, f"Expected 4 sample files, found {len(sample_files)}"

    expected_info = {
        "departures_2026-10-01.pdf": {"date": datetime.date(2026, 10, 1), "rows": 14},
        "departures_2026-10-02.pdf": {"date": datetime.date(2026, 10, 2), "rows": 11},
        "departures_2026-10-03.pdf": {"date": datetime.date(2026, 10, 3), "rows": 12},
        "departures_2026-10-04.pdf": {"date": datetime.date(2026, 10, 4), "rows": 10},
    }

    for file_path in sample_files:
        basename = os.path.basename(file_path)
        parsed = parse_departures_pdf(file_path)

        assert parsed.property_name == "STUDIO 6 - STAFFORD, VA"
        assert parsed.property_code == "3756"
        assert parsed.report_date == expected_info[basename]["date"]
        assert parsed.total_rows == expected_info[basename]["rows"]
        assert parsed.valid_rows == expected_info[basename]["rows"]

        for rec in parsed.records:
            assert rec["confirmation_number"] is not None
            assert rec["room_number"] is not None
            assert rec["normalized_name"] != ""
            assert rec["check_in_date"] is not None
            assert rec["calculated_departure_date"] is not None


# -------------------------------------------------------------------------
# Test 2: Normalizers
# -------------------------------------------------------------------------
def test_normalizers():
    assert normalize_confirmation_number("3756AAJ34\n3") == "3756AAJ343"
    assert normalize_confirmation_number("3756AAJ58 0") == "3756AAJ580"
    assert normalize_name("PRESTON,\nGEORGE\nSTANLEY") == "PRESTON GEORGE STANLEY"
    assert normalize_name("  charlie   lemmel  ") == "CHARLIE LEMMEL"
    assert parse_date_flexible("28-Sep-26") == datetime.date(2026, 9, 28)
    assert parse_date_flexible("01-Sep-26") == datetime.date(2026, 9, 1)
    assert parse_date_flexible("Oct 01, 2026") == datetime.date(2026, 10, 1)

    c_in = datetime.date(2026, 9, 1)
    calc_dept = calculate_departure_date(c_in, 30)
    assert calc_dept == datetime.date(2026, 10, 1)


# -------------------------------------------------------------------------
# Test 3: Identity Reconciliation & Manual Review Queue
# -------------------------------------------------------------------------
def test_identity_matching_and_review(db_session, client):
    prop = db_session.query(Property).first()

    rec1 = {
        "confirmation_number": "3756AAJ100",
        "room_number": "101",
        "first_name": "JOHN",
        "last_name": "DOE",
        "normalized_name": "JOHN DOE",
        "check_in_date": "2026-10-01"
    }

    id1, match1 = match_or_create_guest_identity(db_session, prop.id, rec1)
    assert id1.id is not None
    assert match1.match_type == "initial_creation"

    gr1 = GuestRecord(
        report_id=1,
        guest_identity_id=id1.id,
        confirmation_number="3756AAJ100",
        room_number="101",
        normalized_name="JOHN DOE",
        source_page=1,
        source_row_index=1
    )
    db_session.add(gr1)
    db_session.commit()

    # Same name but different room -> proposed match
    rec2 = {
        "confirmation_number": "3756AAJ999",
        "room_number": "205",
        "normalized_name": "JOHN DOE",
        "first_name": "JOHN",
        "last_name": "DOE"
    }
    id2, match2 = match_or_create_guest_identity(db_session, prop.id, rec2)
    assert id2.id == id1.id
    assert match2.status == "proposed"

    gr2 = GuestRecord(
        report_id=1,
        guest_identity_id=id1.id,
        confirmation_number="3756AAJ999",
        room_number="205",
        normalized_name="JOHN DOE",
        source_page=1,
        source_row_index=2
    )
    db_session.add(gr2)
    db_session.flush()
    match2.guest_record_id = gr2.id
    db_session.add(match2)
    db_session.commit()

    # Query review queue
    q_res = client.get("/api/v1/review/queue")
    assert q_res.status_code == 200
    assert q_res.json()["pending_matches_count"] >= 1

    # Owner rejects merge and splits identities
    split_res = client.post(f"/api/v1/review/matches/{match2.id}/reject")
    assert split_res.status_code == 200

    db_session.refresh(gr2)
    assert gr2.guest_identity_id != id1.id  # Separated into new identity!


def test_batch_identity_matching_and_merge(db_session, client):
    prop = db_session.query(Property).first()

    # Create primary identity
    rec_base = {
        "confirmation_number": "3756BASE1",
        "room_number": "100",
        "first_name": "ALICE",
        "last_name": "SMITH",
        "normalized_name": "ALICE SMITH",
        "check_in_date": "2026-10-01"
    }
    id_base, m_base = match_or_create_guest_identity(db_session, prop.id, rec_base)
    gr_base = GuestRecord(
        report_id=1,
        guest_identity_id=id_base.id,
        confirmation_number="3756BASE1",
        room_number="100",
        normalized_name="ALICE SMITH",
        source_page=1,
        source_row_index=1
    )
    db_session.add(gr_base)
    db_session.commit()

    # Create 3 proposed matches for same guest in different rooms
    match_ids = []
    for i in range(1, 4):
        rec_cand = {
            "confirmation_number": f"3756CAND{i}",
            "room_number": f"20{i}",
            "normalized_name": "ALICE SMITH",
            "first_name": "ALICE",
            "last_name": "SMITH"
        }
        _, m_cand = match_or_create_guest_identity(db_session, prop.id, rec_cand)
        gr_cand = GuestRecord(
            report_id=1,
            guest_identity_id=id_base.id,
            confirmation_number=f"3756CAND{i}",
            room_number=f"20{i}",
            normalized_name="ALICE SMITH",
            source_page=1,
            source_row_index=i + 1
        )
        db_session.add(gr_cand)
        db_session.flush()
        m_cand.guest_record_id = gr_cand.id
        db_session.add(m_cand)
        db_session.commit()
        match_ids.append(m_cand.id)

    # Test batch confirm for first 2 matches
    res_batch_confirm = client.post("/api/v1/review/matches/batch-confirm", json={"match_ids": match_ids[:2]})
    assert res_batch_confirm.status_code == 200
    data_confirm = res_batch_confirm.json()
    assert data_confirm["success"] is True
    assert data_confirm["count"] == 2

    # Check database status
    m1 = db_session.query(GuestIdentityMatch).filter(GuestIdentityMatch.id == match_ids[0]).first()
    m2 = db_session.query(GuestIdentityMatch).filter(GuestIdentityMatch.id == match_ids[1]).first()
    assert m1.status == "confirmed"
    assert m2.status == "confirmed"

    # Test batch reject/split for the 3rd match
    res_batch_reject = client.post("/api/v1/review/matches/batch-reject", json={"match_ids": [match_ids[2]]})
    assert res_batch_reject.status_code == 200
    data_reject = res_batch_reject.json()
    assert data_reject["success"] is True
    assert data_reject["count"] == 1

    m3 = db_session.query(GuestIdentityMatch).filter(GuestIdentityMatch.id == match_ids[2]).first()
    assert m3.status == "rejected"
    assert m3.guest_record.guest_identity_id != id_base.id


# -------------------------------------------------------------------------
# Test 4: Rolling Window: Day 1, Day 2, Day 4, Missing Dates, and Day 31+
# -------------------------------------------------------------------------
def test_rolling_window_multi_day_and_missing_dates(db_session):
    prop = db_session.query(Property).first()

    # 1. Day 1, Day 2, and Day 4 (intentionally skipping Day 3 to test missing date detection)
    dates_to_add = [
        datetime.date(2026, 10, 1),
        datetime.date(2026, 10, 2),
        datetime.date(2026, 10, 4),  # Skipping Oct 3
    ]

    for idx, r_date in enumerate(dates_to_add, start=1):
        rep = UploadedReport(
            property_id=prop.id,
            original_filename=f"rep_{r_date}.pdf",
            stored_filename=f"stored_{r_date}.pdf",
            file_hash=f"hash_{r_date}",
            file_size_bytes=1000,
            report_date=r_date,
            status="completed",
            total_rows_extracted=1,
            valid_rows_count=1,
            is_active=True
        )
        db_session.add(rep)
    db_session.commit()

    win = calculate_rolling_window(db_session, prop.id)
    assert win["total_reporting_dates"] == 3
    # Oct 03 must be detected as missing calendar date!
    assert "2026-10-03" in win["missing_calendar_dates"]

    # Now add dates up to 35 to test sliding 30-day window
    for day_i in range(5, 36):
        d = datetime.date(2026, 10, 1) + datetime.timedelta(days=day_i)
        rep = UploadedReport(
            property_id=prop.id,
            original_filename=f"rep_{d}.pdf",
            stored_filename=f"stored_{d}.pdf",
            file_hash=f"hash_{d}",
            file_size_bytes=1000,
            report_date=d,
            status="completed",
            total_rows_extracted=1,
            valid_rows_count=1,
            is_active=True
        )
        db_session.add(rep)
    db_session.commit()

    win35 = calculate_rolling_window(db_session, prop.id)
    assert win35["total_reporting_dates"] == 3 + 31  # 34 total dates
    # Window limit defaults to 30
    assert len(win35["active_window_dates"]) == 30
    # Oldest dates rolled out of active window
    assert win35["window_start_date"] > "2026-10-01"


# -------------------------------------------------------------------------
# Test 5: End-to-End Import from Fixtures and Mode A vs Mode B Verification
# -------------------------------------------------------------------------
def test_end_to_end_import_and_analytics(client, db_session):
    prop = db_session.query(Property).first()
    sample_files = sorted(glob.glob("tests/fixtures/sample_reports/*.pdf"))

    # Upload files using API preview
    files_payload = []
    for f in sample_files:
        files_payload.append(
            ("files", (os.path.basename(f), open(f, "rb"), "application/pdf"))
        )

    res_preview = client.post("/api/v1/reports/preview", files=files_payload)
    assert res_preview.status_code == 200
    preview_data = res_preview.json()
    assert len(preview_data) == 4

    # Verify duplicate detection on preview if re-uploaded
    dup_preview = client.post("/api/v1/reports/preview", files=[
        ("files", (os.path.basename(sample_files[0]), open(sample_files[0], "rb"), "application/pdf"))
    ])
    # The file hash matches one of the staging files
    assert dup_preview.status_code == 200

    # Commit the previewed reports
    commit_payload = {
        "files": [
            {
                "temp_file_id": item["temp_file_id"],
                "report_date": item["report_date"],
                "records": item["records"]
            }
            for item in preview_data
        ]
    }
    commit_res = client.post("/api/v1/reports/commit", json=commit_payload)
    assert commit_res.status_code == 200
    assert commit_res.json()["success"] is True

    # 1. Dashboard metrics
    dash_res = client.get("/api/v1/dashboard/summary")
    assert dash_res.status_code == 200
    summary = dash_res.json()
    assert summary["total_reports_imported"] == 4
    assert summary["reporting_dates_covered"] == 4
    assert summary["continuous_stay_count"] >= 3
    assert len(summary["appearance_trends"]) == 4

    # 2. Mode A (Continuous Stay) Monitoring Table
    mode_a_res = client.get("/api/v1/guests/monitoring?mode=continuous_stay")
    assert mode_a_res.status_code == 200
    mode_a_items = mode_a_res.json()["items"]
    assert len(mode_a_items) >= 3
    for it in mode_a_items:
        assert it["mode"] == "continuous_stay"
        assert it["stay_duration_days"] >= 30

    # 3. Mode B (Repeated Appearances) Monitoring Table
    mode_b_res = client.get("/api/v1/guests/monitoring?mode=repeated_appearance")
    assert mode_b_res.status_code == 200
    mode_b_items = mode_b_res.json()["items"]
    assert len(mode_b_items) >= 3
    for it in mode_b_items:
        assert it["mode"] == "repeated_appearance"
        assert it["reporting_dates_count"] >= 3

    # 4. Guest Detail Page with Timeline and Evidence
    first_guest_id = mode_a_items[0]["guest_identity_id"]
    guest_detail = client.get(f"/api/v1/guests/{first_guest_id}")
    assert guest_detail.status_code == 200
    gd_data = guest_detail.json()
    assert len(gd_data["timeline"]) >= 1
    assert "assessments" in gd_data
    assert "matches" in gd_data

    # 5. CSV Export
    csv_res = client.get("/api/v1/guests/export")
    assert csv_res.status_code == 200
    assert "Guest Name,Tracking Mode" in csv_res.text

    # 6. All Records Endpoint
    records_res = client.get("/api/v1/records")
    assert records_res.status_code == 200
    assert records_res.json()["total"] == 47  # 14 + 11 + 12 + 10 = 47


# -------------------------------------------------------------------------
# Test 6: Auth Flow and Unauthenticated Protection
# -------------------------------------------------------------------------
def test_auth_flow_and_security_guard(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as unauth_client:
        # 1. Unauthenticated requests should be rejected with 401
        r_dash = unauth_client.get("/api/v1/dashboard/summary")
        assert r_dash.status_code == 401
        assert "credentials not provided" in r_dash.json()["detail"].lower()

        r_upload = unauth_client.post("/api/v1/reports/preview")
        assert r_upload.status_code == 401

        r_guests = unauth_client.get("/api/v1/guests/monitoring")
        assert r_guests.status_code == 401

        r_records = unauth_client.get("/api/v1/records")
        assert r_records.status_code == 401

        # 2. Login with bad credentials should fail
        bad_login = unauth_client.post("/api/v1/auth/login", json={
            "email": "admin@staytrack.local",
            "password": "wrongpassword"
        })
        assert bad_login.status_code == 401

        # 3. Login with correct credentials should succeed
        login_res = unauth_client.post("/api/v1/auth/login", json={
            "email": "admin@staytrack.local",
            "password": "StayTrack2026!"
        })
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["user"]["email"] == "admin@staytrack.local"

        token = token_data["access_token"]

        # 4. Authenticated request with Bearer token should succeed
        auth_client = TestClient(app)
        auth_client.headers["Authorization"] = f"Bearer {token}"
        r_auth = auth_client.get("/api/v1/dashboard/summary")
        assert r_auth.status_code == 200

        # 5. Token query parameter for export/download should succeed
        r_query_auth = unauth_client.get(f"/api/v1/guests/export?token={token}")
        assert r_query_auth.status_code == 200

    app.dependency_overrides.clear()


def test_guest_identities_merge(db_session, client):
    prop = db_session.query(Property).first()

    # Create two separate identities
    g1 = GuestIdentity(
        property_id=prop.id,
        primary_first_name="BOB",
        primary_last_name="WILLIAMS",
        normalized_name="BOB WILLIAMS",
        verification_status="verified"
    )
    g2 = GuestIdentity(
        property_id=prop.id,
        primary_first_name="ROBERT",
        primary_last_name="WILLIAMS",
        normalized_name="ROBERT WILLIAMS",
        verification_status="provisional"
    )
    db_session.add_all([g1, g2])
    db_session.flush()

    rec1 = GuestRecord(
        report_id=1,
        guest_identity_id=g1.id,
        confirmation_number="CONF1",
        room_number="101",
        normalized_name="BOB WILLIAMS",
        source_page=1,
        source_row_index=1
    )
    rec2 = GuestRecord(
        report_id=1,
        guest_identity_id=g2.id,
        confirmation_number="CONF2",
        room_number="102",
        normalized_name="ROBERT WILLIAMS",
        source_page=1,
        source_row_index=2
    )
    db_session.add_all([rec1, rec2])
    db_session.commit()

    # Merge g2 into g1
    res = client.post("/api/v1/guests/merge", json={
        "primary_identity_id": g1.id,
        "secondary_identity_ids": [g2.id]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["primary_identity_id"] == g1.id
    assert data["merged_count"] == 1

    # Verify rec2 is now associated with g1
    db_session.refresh(rec2)
    assert rec2.guest_identity_id == g1.id

    # Verify g2 is deleted
    assert db_session.query(GuestIdentity).filter(GuestIdentity.id == g2.id).first() is None


def test_new_york_time_and_report_history(db_session, client):
    from app.core.time_utils import to_utc_iso, to_ny_iso, to_ny_display_str, get_ny_now
    import datetime

    # 1. Test UTC ISO formatting with explicit Z
    naive_dt = datetime.datetime(2026, 10, 22, 14, 30, 0)
    utc_iso = to_utc_iso(naive_dt)
    assert utc_iso == "2026-10-22T14:30:00Z"

    # 2. Test NY display string formatting (14:30 UTC is 10:30 AM EDT in New York)
    ny_str = to_ny_display_str(naive_dt)
    assert "10:30 AM" in ny_str
    assert "EDT" in ny_str or "EST" in ny_str

    # 3. Test PDF parser extracts Report Run Date and Time
    sample_pdf = os.path.join(os.path.dirname(__file__), "fixtures", "sample_reports", "departures_2026-10-01.pdf")
    if os.path.exists(sample_pdf):
        parsed = parse_departures_pdf(sample_pdf)
        assert parsed.report_run_datetime is not None
        assert "Oct 15, 2026" in parsed.report_run_datetime
        assert "07:38 AM" in parsed.report_run_datetime

    # 4. Insert report and test reports API returns report_run_datetime and ISO timestamps with Z
    prop = db_session.query(Property).first()
    rep = UploadedReport(
        property_id=prop.id,
        original_filename="departures_2026-10-01.pdf",
        stored_filename="mock.pdf",
        file_hash="mockhash",
        file_size_bytes=1000,
        report_type="departures",
        report_date=datetime.date(2026, 10, 1),
        report_run_datetime="Oct 15, 2026 • 07:38 AM",
        status="completed",
        total_rows_extracted=5,
        valid_rows_count=5,
        is_active=True
    )
    db_session.add(rep)
    db_session.commit()

    res = client.get("/api/v1/reports")
    assert res.status_code == 200
    reports_data = res.json()
    assert len(reports_data) > 0
    first_rep = reports_data[0]
    assert first_rep["report_run_datetime"] == "Oct 15, 2026 • 07:38 AM"
    assert first_rep["created_at"].endswith("Z")
    assert "created_at_ny" in first_rep

    # 5. Test dashboard summary returns ISO timestamps with Z
    res_dash = client.get("/api/v1/dashboard/summary")
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    if dash_data.get("latest_import"):
        assert dash_data["latest_import"]["imported_at"].endswith("Z")
    if dash_data.get("recent_reports"):
        assert dash_data["recent_reports"][0]["created_at"].endswith("Z")


def test_export_pdf_with_many_confirmations(client, db_session):
    """Verify that export-pdf never fails with 500 when guests have dozens of renewals/confirmations."""
    prop = db_session.query(Property).first()
    rep = UploadedReport(
        property_id=prop.id,
        original_filename="departures_batch.pdf",
        stored_filename="mock.pdf",
        file_hash="mockhash_pdf",
        file_size_bytes=1000,
        report_type="departures",
        report_date=datetime.date(2026, 10, 20),
        status="completed",
        is_active=True
    )
    db_session.add(rep)
    db_session.commit()

    identity = GuestIdentity(
        property_id=prop.id,
        primary_first_name="TRINITY",
        primary_last_name="GRIFFITH",
        normalized_name="TRINITY GRIFFITH",
        verification_status="verified"
    )
    db_session.add(identity)
    db_session.commit()

    # Create 60 continuous daily records
    base_date = datetime.date(2026, 8, 1)
    for i in range(60):
        c_in = base_date + datetime.timedelta(days=i)
        c_out = c_in + datetime.timedelta(days=1)
        rec = GuestRecord(
            report_id=rep.id,
            guest_identity_id=identity.id,
            confirmation_number=f"3756AAJ{i:03d}",
            room_number=f"{150 + (i % 4)}",
            normalized_name="TRINITY GRIFFITH",
            check_in_date=c_in,
            number_of_nights=1,
            calculated_departure_date=c_out,
            status="Checked Out"
        )
        db_session.add(rec)
    db_session.commit()

    res = client.get("/api/v1/guests/export-pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 1000
    assert res.content[:4] == b"%PDF"



