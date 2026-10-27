import csv
import io
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import User
from app.core.security import create_access_token

def main():
    client = TestClient(app)
    db = SessionLocal()
    admin = db.query(User).filter(User.email == 'admin@staytrack.local').first()
    token = create_access_token(subject=admin.id)
    headers = {'Authorization': f'Bearer {token}'}

    for pid, name in [(1, 'Studio 6'), (2, 'Motel 6')]:
        print(f"\n=== Testing {name} (Property ID: {pid}) ===")

        # 1. Test 90+ Days Continuous Stay
        m90 = client.get(f'/api/v1/guests/monitoring?mode=continuous_stay_90&property_id={pid}', headers=headers).json()
        c90 = client.get(f'/api/v1/guests/export?mode=continuous_stay_90&property_id={pid}', headers=headers)
        r90 = list(csv.reader(io.StringIO(c90.text)))[1:]
        p90 = client.get(f'/api/v1/guests/export-pdf?mode=continuous_stay_90&property_id={pid}', headers=headers)

        table_count_90 = len(m90["items"])
        csv_count_90 = len(r90)
        print(f"  [90+ Days] Table items: {table_count_90}, CSV rows: {csv_count_90}, PDF: {p90.status_code}")
        assert table_count_90 == csv_count_90, f"Mismatch in 90+ for {name}: table={table_count_90} vs csv={csv_count_90}"
        assert p90.status_code == 200
        assert p90.content[:4] == b"%PDF"

        # Verify guest names match exactly
        table_names_90 = [i["guest_name"] for i in m90["items"]]
        csv_names_90 = [r[0] for r in r90]
        assert table_names_90 == csv_names_90, f"Guest names mismatch in 90+ for {name}"

        # 2. Test 30+ Days Continuous Stay
        m30 = client.get(f'/api/v1/guests/monitoring?mode=continuous_stay&property_id={pid}', headers=headers).json()
        c30 = client.get(f'/api/v1/guests/export?mode=continuous_stay&property_id={pid}', headers=headers)
        r30 = list(csv.reader(io.StringIO(c30.text)))[1:]
        p30 = client.get(f'/api/v1/guests/export-pdf?mode=continuous_stay&property_id={pid}', headers=headers)

        table_count_30 = len(m30["items"])
        csv_count_30 = len(r30)
        print(f"  [30+ Days] Table items: {table_count_30}, CSV rows: {csv_count_30}, PDF: {p30.status_code}")
        assert table_count_30 == csv_count_30, f"Mismatch in 30+ for {name}: table={table_count_30} vs csv={csv_count_30}"
        assert p30.status_code == 200
        assert p30.content[:4] == b"%PDF"

        table_names_30 = [i["guest_name"] for i in m30["items"]]
        csv_names_30 = [r[0] for r in r30]
        assert table_names_30 == csv_names_30, f"Guest names mismatch in 30+ for {name}"

        # 3. Test Room Filter consistency
        room_test = "114" if pid == 2 else "105"
        m_rm = client.get(f'/api/v1/guests/monitoring?mode=continuous_stay&property_id={pid}&room={room_test}', headers=headers).json()
        c_rm = client.get(f'/api/v1/guests/export?mode=continuous_stay&property_id={pid}&room={room_test}', headers=headers)
        r_rm = list(csv.reader(io.StringIO(c_rm.text)))[1:]
        p_rm = client.get(f'/api/v1/guests/export-pdf?mode=continuous_stay&property_id={pid}&room={room_test}', headers=headers)
        assert len(m_rm["items"]) == len(r_rm), f"Room filter mismatch for {name}: table={len(m_rm['items'])} vs csv={len(r_rm)}"
        assert p_rm.status_code == 200

    print("\n>>> ALL CONSISTENCY CHECKS PASSED FOR BOTH STUDIO 6 AND MOTEL 6! <<<")

if __name__ == "__main__":
    main()
