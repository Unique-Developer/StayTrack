export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface DashboardSummary {
  total_reports_imported: number;
  reporting_dates_covered: number;
  unique_guest_identities: number;
  continuous_stay_count: number;
  needs_verification_count: number;
  missing_reporting_dates_count: number;
  missing_dates: string[];
  active_window_start?: string;
  active_window_end?: string;
  window_coverage_pct: number;
  latest_import?: {
    id: number;
    filename: string;
    report_date: string;
    records_count: number;
    imported_at: string;
  };
  recent_reports: Array<{
    id: number;
    filename: string;
    report_date: string;
    status: string;
    rows: number;
    created_at: string;
  }>;
  appearance_trends: Array<{
    date: string;
    display_date: string;
    departures_count: number;
  }>;
  recent_errors: Array<{
    id: number;
    filename: string;
    error: string;
    created_at: string;
  }>;
}

export interface PreviewRecord {
  raw_confirmation_number?: string;
  confirmation_number?: string;
  raw_guest_name?: string;
  first_name?: string;
  last_name?: string;
  normalized_name: string;
  additional_guests?: string;
  room_number?: string;
  check_in_date?: string;
  number_of_nights?: number;
  calculated_departure_date?: string;
  status?: string;
  total_guest_balance?: number;
  actual_departed_time?: string;
  vip_guest?: string;
  guest_tier?: string;
  housekeeping_remarks?: string;
  source_page: number;
  source_row_index: number;
  confidence_score: number;
  validation_flags: string[];
}

export interface ReportPreviewFile {
  temp_file_id: string;
  original_filename: string;
  file_size_bytes: number;
  file_hash: string;
  is_duplicate: boolean;
  duplicate_report_id?: number;
  existing_report_for_date_id?: number;
  property_name?: string;
  property_code?: string;
  report_date?: string;
  report_run_datetime?: string;
  generated_by?: string;
  total_rows: number;
  valid_rows: number;
  has_warnings: boolean;
  warnings: string[];
  extraction_method: string;
  records: PreviewRecord[];
}

export interface GuestAssessmentItem {
  id: number;
  guest_identity_id: number;
  guest_name: string;
  mode: 'continuous_stay' | 'repeated_appearance';
  stay_duration_days: number;
  reporting_dates_count: number;
  first_date?: string;
  last_date?: string;
  rooms: string[];
  confirmation_numbers: string[];
  dates_appeared: string[];
  evidence_source?: string;
  verification_status: 'Verified' | 'Needs Verification' | 'Rejected';
  confidence_score: number;
  notes?: string;
}

export interface GuestMonitoringResponse {
  total: number;
  page: number;
  page_size: number;
  items: GuestAssessmentItem[];
}

export interface GuestRecordItem {
  id: number;
  report_id: number;
  report_date?: string;
  report_filename?: string;
  guest_identity_id?: number;
  confirmation_number?: string;
  additional_guests?: string;
  room_number?: string;
  guest_name: string;
  first_name?: string;
  last_name?: string;
  check_in_date?: string;
  number_of_nights?: number;
  calculated_departure_date?: string;
  status?: string;
  total_guest_balance?: number;
  actual_departed_time?: string;
  vip_guest?: string;
  confidence_score: number;
  validation_flags: string[];
}

export interface GuestDetail {
  identity_id: number;
  normalized_name: string;
  first_name?: string;
  last_name?: string;
  verification_status: string;
  notes?: string;
  records_count: number;
  timeline: Array<{
    record_id: number;
    report_id: number;
    report_date?: string;
    report_file?: string;
    confirmation_number?: string;
    room_number?: string;
    check_in_date?: string;
    number_of_nights?: number;
    calculated_departure_date?: string;
    status?: string;
    total_guest_balance?: number;
    actual_departed_time?: string;
    source_page: number;
    source_row_index: number;
    confidence_score: number;
    validation_flags: string[];
  }>;
  matches: Array<{
    id: number;
    guest_record_id: number;
    match_type: string;
    confidence_score: number;
    status: string;
    review_notes?: string;
    created_at: string;
  }>;
  assessments: Array<{
    id: number;
    mode: string;
    stay_duration_days: number;
    reporting_dates_count: number;
    first_date?: string;
    last_date?: string;
    rooms: string[];
    confirmations: string[];
    dates_list: string[];
    evidence_source?: string;
    verification_status: string;
    notes?: string;
  }>;
}

export interface ReportItem {
  id: number;
  property_id: number;
  property_name: string;
  original_filename: string;
  file_size_bytes: number;
  report_date: string;
  report_run_datetime?: string;
  status: string;
  total_rows_extracted: number;
  valid_rows_count: number;
  created_at: string;
  created_at_ny?: string;
  is_active: boolean;
}

export interface ReviewQueueData {
  pending_matches_count: number;
  uncertain_assessments_count: number;
  proposed_matches: Array<{
    match_id: number;
    match_type: string;
    confidence_score: number;
    review_notes?: string;
    record?: {
      id: number;
      confirmation_number?: string;
      room_number?: string;
      guest_name: string;
      check_in_date?: string;
      nights?: number;
      report_date?: string;
    };
    candidate_identity?: {
      id: number;
      name: string;
      status: string;
    };
  }>;
  uncertain_assessments: Array<{
    assessment_id: number;
    guest_identity_id: number;
    guest_name: string;
    mode: string;
    stay_duration_days: number;
    reporting_dates_count: number;
    rooms: string[];
    confirmations: string[];
    evidence_source?: string;
    notes?: string;
  }>;
}

export interface SystemSettings {
  rolling_window_days: number;
  continuous_stay_days: number;
  min_appearance_days: number;
  departure_convention: string;
  property_timezone: string;
  retention_days: number;
}

export interface AuditLogItem {
  id: number;
  user_id?: number;
  user_email: string;
  action: string;
  entity_type?: string;
  entity_id?: string;
  details: Record<string, any>;
  ip_address?: string;
  created_at: string;
}
