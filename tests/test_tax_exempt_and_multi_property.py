import io
import csv
import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.db.models import Property, GuestIdentity, GuestRecord, UploadedReport, User
from app.core.security import hash_password, create_access_token
from app.db.init_db import init_db
from app.main import app

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_sample_records(db, property_id, guest_name, nights, check_in_str, room="101"):
    c_in = datetime.date.fromisoformat(check_in_str)
    c_out = c_in + datetime.timedelta(days=nights)
    unique_suffix = f"{guest_name.replace(' ', '_')}_{c_out.isoformat()}"
    report = UploadedReport(
        property_id=property_id,
        original_filename=f"departures_{unique_suffix}.pdf",
        stored_filename=f"stored_{unique_suffix}.pdf",
        file_hash=f"hash_{unique_suffix}",
        file_size_bytes=1024,
        report_type="departures",
        report_date=c_out,
        status="completed",
        total_rows_extracted=1,
        valid_rows_count=1,
        is_active=True
    )
    db.add(report)
    db.flush()

    identity = GuestIdentity(
        property_id=property_id,
        primary_first_name=guest_name.split()[0],
        primary_last_name=guest_name.split()[-1],
        normalized_name=guest_name,
        verification_status="verified"
    )
    db.add(identity)
    db.flush()

    record = GuestRecord(
        report_id=report.id,
        guest_identity_id=identity.id,
        confirmation_number=f"CONF_{identity.id}",
        room_number=room,
        raw_guest_name=guest_name,
        normalized_name=guest_name,
        check_in_date=c_in,
        number_of_nights=nights,
        calculated_departure_date=c_out,
        status="departed"
    )
    db.add(record)
    db.commit()
    return identity

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
    admin = db_session.query(User).filter(User.email == "admin@staytrack.local").first()
    token = create_access_token(subject=admin.id)
    c.headers["Authorization"] = f"Bearer {token}"
    return c

def test_multi_property_support(client, db_session):
    # Test GET /dashboard/properties
    res = client.get("/api/v1/dashboard/properties")
    assert res.status_code == 200
    props = res.json()
    assert len(props) >= 2
    codes = [p["property_code"] for p in props]
    assert "3756" in codes
    assert "MOTEL6" in codes

def test_tax_exempt_csv_and_pdf_export_consistency(client, db_session):
    prop_s6 = db_session.query(Property).filter(Property.property_code == "3756").first()
    assert prop_s6 is not None

    # Seed sample records for Studio 6
    seed_sample_records(db_session, prop_s6.id, "TEST GUEST LONG STAY", 95, "2026-07-01", room="201")
    seed_sample_records(db_session, prop_s6.id, "TEST GUEST COUNTY EXEMPT", 45, "2026-08-20", room="202")

    # Test CSV Export for continuous stay
    csv_res = client.get(f"/api/v1/guests/export?mode=continuous_stay&property_id={prop_s6.id}")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    reader = csv.reader(io.StringIO(csv_res.text))
    rows = list(reader)
    header = rows[0]
    assert "County Tax Exempt Start Date (30+ Days)" in header
    assert "State Tax Exempt Date (90+ Days)" in header
    assert "Tax Exemption Status" in header
    assert "Fix Rate" in header
    assert len(rows) > 1  # Contains data rows

    # Test PDF Export
    pdf_res = client.get(f"/api/v1/guests/export-pdf?property_id={prop_s6.id}&min_nights=1")
    assert pdf_res.status_code == 200
    assert "application/pdf" in pdf_res.headers["content-type"]
    assert len(pdf_res.content) > 1000

def test_motel6_guests_and_update_endpoint(client, db_session):
    prop_m6 = db_session.query(Property).filter(Property.property_code == "MOTEL6").first()
    assert prop_m6 is not None

    # Seed a Motel 6 guest
    m6_guest = seed_sample_records(db_session, prop_m6.id, "MOTEL GUEST KIERRA", 120, "2026-06-01", room="110")

    # Query monitoring for Motel 6
    m6_res = client.get(f"/api/v1/guests/monitoring?mode=continuous_stay&property_id={prop_m6.id}&min_duration=1")
    assert m6_res.status_code == 200
    m6_items = m6_res.json()["items"]
    assert len(m6_items) >= 1

    # Check that tax dates are calculated
    sample_guest = m6_items[0]
    assert sample_guest["county_exempt_date"] is not None
    assert sample_guest["state_exempt_date"] is not None
    assert sample_guest["tax_exempt_status"] is not None

    # Test PATCH /api/v1/guests/{identity_id}
    guest_id = sample_guest["guest_identity_id"]
    patch_res = client.patch(f"/api/v1/guests/{guest_id}", json={
        "fixed_rate": 79.99,
        "notes": "VIP corporate contract"
    })
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["fixed_rate"] == 79.99
    assert patch_data["notes"] == "VIP corporate contract"

    # Detail view confirms update
    detail_res = client.get(f"/api/v1/guests/{guest_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["fixed_rate"] == 79.99

def test_90plus_days_tab_and_export(client, db_session):
    prop_s6 = db_session.query(Property).filter(Property.property_code == "3756").first()
    prop_m6 = db_session.query(Property).filter(Property.property_code == "MOTEL6").first()

    seed_sample_records(db_session, prop_s6.id, "JOHN STATE EXEMPT", 110, "2026-06-01", room="105")
    seed_sample_records(db_session, prop_m6.id, "MOTEL STATE EXEMPT", 95, "2026-06-15", room="112")

    # Query monitoring with mode="continuous_stay_90" for Studio 6
    res_s6_90 = client.get(f"/api/v1/guests/monitoring?mode=continuous_stay_90&property_id={prop_s6.id}")
    assert res_s6_90.status_code == 200
    items_s6_90 = res_s6_90.json()["items"]
    assert len(items_s6_90) > 0
    for item in items_s6_90:
        assert item["stay_duration_days"] >= 90
        assert item["tax_exempt_status"] == "Fully Tax Exempt (State + County)"
        assert item["county_exempt_date"] is not None
        assert item["state_exempt_date"] is not None

    # CSV Export for 90+ days for Motel 6
    csv_90 = client.get(f"/api/v1/guests/export?mode=continuous_stay_90&property_id={prop_m6.id}")
    assert csv_90.status_code == 200
    assert "90plus_days_tax_exempt" in csv_90.headers.get("content-disposition", "")
    rows_90 = list(csv.reader(io.StringIO(csv_90.text)))
    assert len(rows_90) > 1
    for r in rows_90[1:]:
        assert int(r[4]) >= 90  # Total Consecutive Nights column
