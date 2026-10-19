from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
import datetime

# Auth Schemas
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool

# Report Schemas
class PreviewRecord(BaseModel):
    raw_confirmation_number: Optional[str] = None
    confirmation_number: Optional[str] = None
    raw_guest_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    normalized_name: str
    additional_guests: Optional[str] = None
    room_number: Optional[str] = None
    check_in_date: Optional[str] = None
    number_of_nights: Optional[int] = None
    calculated_departure_date: Optional[str] = None
    status: Optional[str] = "Checked Out"
    total_guest_balance: Optional[float] = 0.0
    actual_departed_time: Optional[str] = None
    vip_guest: Optional[str] = "No"
    guest_tier: Optional[str] = None
    housekeeping_remarks: Optional[str] = None
    source_page: int = 1
    source_row_index: int = 0
    confidence_score: float = 1.0
    validation_flags: List[str] = []

class ReportPreviewFile(BaseModel):
    temp_file_id: str
    original_filename: str
    file_size_bytes: int
    file_hash: str
    is_duplicate: bool
    duplicate_report_id: Optional[int] = None
    existing_report_for_date_id: Optional[int] = None
    property_name: Optional[str] = None
    property_code: Optional[str] = None
    report_date: Optional[str] = None
    report_run_datetime: Optional[str] = None
    generated_by: Optional[str] = None
    total_rows: int
    valid_rows: int
    has_warnings: bool
    warnings: List[str] = []
    extraction_method: str = "pdfplumber"
    records: List[PreviewRecord] = []

class ReportCommitItem(BaseModel):
    temp_file_id: str
    property_id: Optional[int] = None
    report_date: str
    replace_existing_id: Optional[int] = None
    records: List[PreviewRecord]

class ReportCommitRequest(BaseModel):
    files: List[ReportCommitItem]

class ReportResponse(BaseModel):
    id: int
    property_id: int
    property_name: str
    original_filename: str
    file_size_bytes: int
    report_date: str
    status: str
    total_rows_extracted: int
    valid_rows_count: int
    created_at: str
    is_active: bool

# Dashboard Schemas
class DashboardSummary(BaseModel):
    total_reports_imported: int
    reporting_dates_covered: int
    unique_guest_identities: int
    continuous_stay_count: int
    needs_verification_count: int
    missing_reporting_dates_count: int
    missing_dates: List[str]
    active_window_start: Optional[str]
    active_window_end: Optional[str]
    window_coverage_pct: float
    latest_import: Optional[Dict[str, Any]]
    recent_reports: List[Dict[str, Any]]
    appearance_trends: List[Dict[str, Any]]
    recent_errors: List[Dict[str, Any]]

# Guest Monitoring Schemas
class GuestAssessmentItem(BaseModel):
    id: int
    guest_identity_id: int
    guest_name: str
    mode: str
    stay_duration_days: int
    reporting_dates_count: int
    first_date: Optional[str]
    last_date: Optional[str]
    rooms: List[str]
    confirmation_numbers: List[str]
    dates_appeared: List[str]
    evidence_source: Optional[str]
    verification_status: str
    confidence_score: float
    notes: Optional[str]

class GuestMonitoringResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[GuestAssessmentItem]

# Settings Schemas
class SettingsResponse(BaseModel):
    rolling_window_days: int
    continuous_stay_days: int
    min_appearance_days: int
    departure_convention: str
    property_timezone: str
    retention_days: int

class SettingsUpdateRequest(BaseModel):
    rolling_window_days: Optional[int] = None
    continuous_stay_days: Optional[int] = None
    min_appearance_days: Optional[int] = None
    departure_convention: Optional[str] = None
    property_timezone: Optional[str] = None
