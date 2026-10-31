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


def seed_stay_record(db, property_id, guest_name, nights, check_in_str, room="101"):
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
        verification_status="Verified"
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
        status="Checked Out"
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
    admin = db_session.query(User).filter(User.email == "admin@staytrack.local").first()
    token = create_access_token(subject=admin.id)
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


def test_date_wise_report_filtering_as_of_oct_26(client, db_session):
    """
    Tests date-wise report logic for continuous stays as of 26 October 2026:
    - Guest A: 95 nights (2026-06-28 to 2026-10-01) -> within last 90 days from Oct 26 -> MUST be included
    - Guest B: 30 nights (2026-09-04 to 2026-10-04) -> within last 30 days from Oct 26 -> MUST be included
    - Guest C (Old 30+): 32 nights (2026-06-01 to 2026-07-03) -> ended > 90 days ago -> MUST be excluded
    - Guest D (Old 90+): 92 nights (2026-01-01 to 2026-04-03) -> ended > 200 days ago -> MUST be excluded
    - Guest E (Future): starts 2026-11-01 -> starts after Oct 26 -> MUST be excluded
    """
    prop = db_session.query(Property).filter(Property.property_code == "3756").first()
    assert prop is not None

    seed_stay_record(db_session, prop.id, "GUEST A RECENT 90PLUS", 95, "2026-06-28", room="101")
    seed_stay_record(db_session, prop.id, "GUEST B RECENT 30PLUS", 30, "2026-09-04", room="102")
    seed_stay_record(db_session, prop.id, "GUEST C OLD 30PLUS", 32, "2026-06-01", room="103")
    seed_stay_record(db_session, prop.id, "GUEST D OLD 90PLUS", 92, "2026-01-01", room="104")
    seed_stay_record(db_session, prop.id, "GUEST E FUTURE STAY", 35, "2026-11-01", room="105")

    # 1. Query monitoring as of 2026-10-26
    res = client.get(f"/api/v1/guests/monitoring?mode=continuous_stay&property_id={prop.id}&as_of_date=2026-10-26")
    assert res.status_code == 200
    data = res.json()
    items = data["items"]
    names = [i["guest_name"] for i in items]

    assert "GUEST A RECENT 90PLUS" in names
    assert "GUEST B RECENT 30PLUS" in names
    assert "GUEST C OLD 30PLUS" not in names, "Old 30+ stay from July must be excluded for current tax exempt as of Oct 26"
    assert "GUEST D OLD 90PLUS" not in names, "Old 90+ stay from April must be excluded for current tax exempt as of Oct 26"
    assert "GUEST E FUTURE STAY" not in names, "Future stay starting after Oct 26 must be excluded"

    # Verify counts
    assert data["counts"]["90+"] == 1
    assert data["counts"]["30+"] == 1

    # 2. Query with all_time=true -> should return the old historical stays too
    res_all = client.get(f"/api/v1/guests/monitoring?mode=continuous_stay&property_id={prop.id}&all_time=true")
    assert res_all.status_code == 200
    all_names = [i["guest_name"] for i in res_all.json()["items"]]
    assert "GUEST C OLD 30PLUS" in all_names
    assert "GUEST D OLD 90PLUS" in all_names


def test_custom_columns_csv_export(client, db_session):
    """
    Tests custom column selection on CSV exports:
    - User wants names and dates only: columns=guest_name,check_in_date,calculated_departure_date
    - User wants names only: columns=guest_name
    - User wants standard full columns (no columns param)
    """
    prop = db_session.query(Property).filter(Property.property_code == "3756").first()
    assert prop is not None

    seed_stay_record(db_session, prop.id, "ALICE SMITH", 35, "2026-09-01", room="205")
    seed_stay_record(db_session, prop.id, "BOB JOHNSON", 92, "2026-06-20", room="206")

    # 1. Export with custom columns: guest_name, check_in_date, calculated_departure_date
    res_custom = client.get(
        f"/api/v1/guests/export?mode=continuous_stay&property_id={prop.id}&columns=guest_name,check_in_date,calculated_departure_date&as_of_date=2026-10-26"
    )
    assert res_custom.status_code == 200
    assert "text/csv" in res_custom.headers["content-type"]
    assert res_custom.text.startswith('\ufeff')  # UTF-8 BOM for Windows Excel compatibility

    reader = csv.reader(io.StringIO(res_custom.text.lstrip('\ufeff')))
    rows = list(reader)
    assert len(rows) >= 3  # Header + 2 data rows
    header = rows[0]
    assert header == ["Guest Name", "Check-in Date", "Calculated Departure Date"]

    # Check data rows have exactly 3 columns and dates in MM-DD-YYYY format
    for row in rows[1:]:
        assert len(row) == 3
        # Date should match MM-DD-YYYY format (e.g. 09-01-2026)
        assert len(row[1].split("-")) == 3
        assert len(row[1].split("-")[0]) == 2
        assert len(row[1].split("-")[2]) == 4

    names_in_csv = [row[0] for row in rows[1:]]
    assert "ALICE SMITH" in names_in_csv
    assert "BOB JOHNSON" in names_in_csv

    # 2. Export with single custom column: guest_name
    res_name_only = client.get(
        f"/api/v1/guests/export?mode=continuous_stay&property_id={prop.id}&columns=guest_name&as_of_date=2026-10-26"
    )
    assert res_name_only.status_code == 200
    assert res_name_only.text.startswith('\ufeff')
    reader_name = csv.reader(io.StringIO(res_name_only.text.lstrip('\ufeff')))
    rows_name = list(reader_name)
    assert rows_name[0] == ["Guest Name"]
    for row in rows_name[1:]:
        assert len(row) == 1

    # 3. Export with default columns (no columns param) -> should contain all 10 default columns
    res_default = client.get(
        f"/api/v1/guests/export?mode=continuous_stay&property_id={prop.id}&as_of_date=2026-10-26"
    )
    assert res_default.status_code == 200
    assert res_default.text.startswith('\ufeff')
    reader_default = csv.reader(io.StringIO(res_default.text.lstrip('\ufeff')))
    rows_default = list(reader_default)
    header_default = rows_default[0]
    assert len(header_default) == 10
    assert "County Tax Exempt Start Date (30+ Days)" in header_default
    assert "State Tax Exempt Date (90+ Days)" in header_default
    assert "Tax Exemption Status" in header_default

    # Verify that stay tier for 30-89 nights is displayed as '30+ Days'
    tier_col_idx = header_default.index("Stay Tier")
    tiers = [r[tier_col_idx] for r in rows_default[1:]]
    assert "30+ Days" in tiers
    assert "30–89 Nights" not in tiers
