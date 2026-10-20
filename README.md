# StayTrack

> **"Daily Reports. Continuous Insights."**

**StayTrack** is a production-minded web application engineered for motel owners and operators. It streamlines daily motel operations by ingesting daily property management system (PMS) "Departures List" PDF reports, extracting and normalizing guest records, maintaining a historical audit database, and tracking guest stay duration patterns across a configurable rolling window (such as 30 distinct reporting days).

---

## 1. Core Architecture & Capabilities

### A. Dual Tracking Modes
1. **Mode A: Continuous Stay Detection**
   - Identifies guests whose stay duration meets a configurable threshold (default: **30 consecutive calendar days**).
   - Relies on authoritative check-in dates, number of nights, and provisional expected departure dates calculated according to the motel's convention (`check_in_date + number_of_nights`).
   - Automatically detects contiguous chained reservations (when a guest extends day-by-day).
   - Flags records with missing data or check-out date discrepancies as **"Needs Verification"** for owner review.
2. **Mode B: Repeated Daily Appearance Detection**
   - Counts distinct reporting dates on which a matching guest identity appears.
   - Configurable appearance threshold (default: **3 distinct dates**, options for 7, 15, 30).
   - Tracks all appearance dates, room numbers, and confirmation numbers without incorrectly conflating non-continuous appearances with a continuous uninterrupted stay.

### B. Rolling Window Engine (Day 1 to Multi-Day)
- Works from **Day 1** without requiring 30 initial files:
  - Day 1: Analyzes the 1st available reporting date.
  - Day 2: Analyzes the first 2 reporting dates.
  - Day 4: Analyzes all 4 available reporting dates.
  - Day 30: Analyzes the latest 30 reporting dates.
  - Day 31+: Slides forward automatically to analyze dates 2 through 31, 3 through 32, etc.
- Uses **actual reporting dates** (e.g. `2026-10-01`), not upload timestamps.
- Automatically calculates and surfaces **missing reporting dates** within the calendar span so operators can spot missing audit files immediately.
- Historical reports and guest records are retained **permanently** under a 7-year audit retention policy, remaining accessible outside the active window.

### C. Guest Identity Reconciliation Engine
- Reconciles guest profiles using: Confirmation Number, First Name, Last Name, Check-in Date, Room Number, and Property Identifier (`3756`).
- Cleans and normalizes text (handling multi-line column wrapping like `3756AAJ34\n3` -> `3756AAJ343` and `PRESTON,\nGEORGE\nSTANLEY` -> `PRESTON GEORGE STANLEY`).
- Prevents blind merges when two guests share the same name but have different rooms/dates without shared confirmation numbers; flags these in the **Review Queue** for owner confirmation.

### D. Production PDF Pipeline
- SHA-256 file hashing to detect duplicate uploads before writing to disk.
- Extracts embedded text and tables using `pdfplumber`.
- Automatic fallback to Tesseract OCR when scanned or rasterized documents are detected.
- **Editable Pre-Import Review Table**: Allows motel owners to inspect, edit, or adjust dates and fields before committing records to the database.

---

## 2. Technology Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Lucide React, Recharts.
- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0.
- **Database**: SQLite (local development with WAL mode and foreign key enforcement) and PostgreSQL-ready.
- **File Storage**: Persistent content-addressed local file storage (`backend/storage/reports`) with modular adapter design for private S3 storage.
- **Testing**: `pytest` with comprehensive fixtures.

---

## 3. Quick Start & Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ and pnpm (or npm)

### 1. Backend Installation & Database Setup
```bash
# Clone and enter the repository
cd StayTrack

# Create and activate virtual environment (optional)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Initialize database schema and default admin user
python backend/app/db/init_db.py
```

### 2. Import the 4 Sample Studio 6 PDF Reports
The repository includes the 4 sample daily departure reports for Studio 6 Stafford (`2026-10-01` through `2026-10-04`). Run the seed utility:
```bash
python backend/seed_sample_data.py
```
This imports:
- `departures_2026-10-01.pdf` (14 records)
- `departures_2026-10-02.pdf` (11 records)
- `departures_2026-10-03.pdf` (12 records)
- `departures_2026-10-04.pdf` (10 records)
Total: **47 guest records**, **35 unique guest identities**, **3 continuous stays (>= 30 days)**, and **3 repeated appearance guests (>= 3 dates)**.

### 3. Frontend Installation & Build
```bash
cd frontend
pnpm install
pnpm build
```

---

## 4. Running the Application

### Option A: Standalone Unified Production Mode (Single Port 8000)
FastAPI serves both the REST API and the compiled React production frontend on port `8000`:
```bash
# From StayTrack root directory:
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```
Open your browser to: **`http://127.0.0.1:8000`**

### Option B: Concurrent Development Mode
Terminal 1 (Backend API with Hot Reload):
```bash
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```
Terminal 2 (Vite Frontend Development Server):
```bash
cd frontend
pnpm dev
```
Open your browser to: **`http://localhost:5173`** (proxies `/api` requests to backend).

---

## 5. Authentication & Daily Operator Workflow

### Default Credentials
StayTrack protects all report uploads, audit records, and operational settings behind authenticated access. Initialized credentials:
- **Admin Email**: `admin@staytrack.local` (or alias `admin@staytrack.com`)
- **Password**: `StayTrack2026!` (Configurable via `DEFAULT_ADMIN_PASSWORD` in `.env`)

### Daily Operator Workflow
1. **Log in**: Enter manager credentials on the secure login screen.
2. **Open Dashboard**: View rolling window coverage, total imported reports, Mode A and Mode B qualifying guests, and any missing calendar dates.
3. **Upload Daily Report**:
   - Navigate to **"Upload Reports"** or click **"Upload Daily Report"**.
   - Drag and drop today's PMS Departures List PDF.
   - The parser extracts the reporting date, property code (`3756`), and all rows.
   - If a report for that date already exists, StayTrack provides an intentional replacement workflow.
   - Review the extracted records in the editable staging table.
   - Click **"Confirm Import"**.
4. **Instant Recalculation**:
   - The PDF is saved permanently in persistent storage.
   - Normalized records are saved to the database.
   - The rolling window and guest stay duration calculations update immediately.
5. **Monitor & Audit**:
   - Open **"Guest Monitoring"** to inspect guests in **Mode A (Continuous Stay)** or **Mode B (Repeated Appearances)**.
   - Click any guest to open their full chronological timeline, room history, and calculation evidence.
   - Export filtered results to CSV or click **"Print Report"** for motel management records.

---

## 6. Running Automated Tests

Run the complete test suite with `pytest`:
```bash
pytest tests/test_full_suite.py -v
```

The test suite validates:
1. Exact parsing of all 4 Studio 6 sample PDFs without dropping rows.
2. Normalization of line-wrapped confirmations (`3756AAJ34\n3` -> `3756AAJ343`) and names.
3. Identity reconciliation rules (exact confirmation matches vs proposed matches).
4. Review Queue actions (confirming merges and splitting profiles).
5. Rolling window advancement (Day 1, 2, 4, missing date identification, and Day 31+ sliding).
6. End-to-end API preview, transactional commit, dashboard metrics, and CSV exports.

---

## 7. Production Deployment & Security

1. **PostgreSQL Configuration**:
   Set `DATABASE_URL` in `.env`:
   ```env
   DATABASE_URL="postgresql+psycopg2://user:password@db-host:5432/staytrack"
   ```
2. **Reverse Proxy (NGINX)**:
   Place behind NGINX with TLS 1.3, rate limiting on `/api/v1/auth` and `/api/v1/reports/preview`, and request size limits (`client_max_body_size 25M`).
3. **S3 Object Storage**:
   Swap `LocalStorageService` in `backend/app/core/storage.py` with standard boto3 S3 client for cloud-native deployment.
4. **Data Privacy**:
   Guest records and original PDFs are strictly protected behind server-side authentication with signed token downloads. No guest PII is ever transmitted to external AI endpoints.
