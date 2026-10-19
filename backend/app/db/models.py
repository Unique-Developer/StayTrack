import datetime
import json
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="admin", nullable=False)  # admin, manager, staff
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    audit_logs = relationship("AuditLog", back_populates="user")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    property_code = Column(String(50), unique=True, index=True, nullable=False)
    timezone = Column(String(100), default="America/New_York", nullable=False)
    address = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    reports = relationship("UploadedReport", back_populates="property", cascade="all, delete-orphan")
    guest_identities = relationship("GuestIdentity", back_populates="property", cascade="all, delete-orphan")


class UploadedReport(Base):
    __tablename__ = "uploaded_reports"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_hash = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(Integer, nullable=False)
    report_type = Column(String(50), default="departures", nullable=False)
    report_date = Column(Date, nullable=False, index=True)
    report_run_datetime = Column(String(100), nullable=True)
    generated_by_user = Column(String(100), nullable=True)
    
    # Status: uploaded, processing, needs_review, completed, failed
    status = Column(String(50), default="uploaded", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    total_rows_extracted = Column(Integer, default=0, nullable=False)
    valid_rows_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # False if replaced by newer version
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    property = relationship("Property", back_populates="reports")
    records = relationship("GuestRecord", back_populates="report", cascade="all, delete-orphan")
    jobs = relationship("ReportProcessingJob", back_populates="report", cascade="all, delete-orphan")


class ReportProcessingJob(Base):
    __tablename__ = "report_processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("uploaded_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String(50), default="extract_and_match", nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, running, completed, failed
    stage = Column(String(100), default="init", nullable=False)
    logs = Column(Text, default="", nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    report = relationship("UploadedReport", back_populates="jobs")


class GuestIdentity(Base):
    __tablename__ = "guest_identities"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_first_name = Column(String(100), nullable=False)
    primary_last_name = Column(String(100), nullable=False)
    normalized_name = Column(String(200), nullable=False, index=True)
    verification_status = Column(String(50), default="provisional", nullable=False)  # verified, provisional, flagged
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    property = relationship("Property", back_populates="guest_identities")
    records = relationship("GuestRecord", back_populates="guest_identity")
    assessments = relationship("StayAssessment", back_populates="guest_identity", cascade="all, delete-orphan")
    matches = relationship("GuestIdentityMatch", back_populates="guest_identity", cascade="all, delete-orphan")


class GuestRecord(Base):
    __tablename__ = "guest_records"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("uploaded_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    guest_identity_id = Column(Integer, ForeignKey("guest_identities.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Raw values
    raw_confirmation_number = Column(String(100), nullable=True)
    raw_guest_name = Column(String(255), nullable=True)
    
    # Normalized extracted fields
    confirmation_number = Column(String(100), nullable=True, index=True)
    additional_guests = Column(String(255), nullable=True)
    room_number = Column(String(50), nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    normalized_name = Column(String(200), nullable=False, index=True)
    
    check_in_date = Column(Date, nullable=True, index=True)
    number_of_nights = Column(Integer, nullable=True)
    calculated_departure_date = Column(Date, nullable=True, index=True)
    
    status = Column(String(50), default="Checked Out", nullable=True)
    total_guest_balance = Column(Float, default=0.0, nullable=True)
    estimated_departure_time = Column(String(50), nullable=True)
    actual_departed_time = Column(String(50), nullable=True)
    vip_guest = Column(String(20), default="No", nullable=True)
    guest_tier = Column(String(50), nullable=True)
    housekeeping_remarks = Column(Text, nullable=True)
    
    # Audit & Quality
    source_page = Column(Integer, default=1, nullable=False)
    source_row_index = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Float, default=1.0, nullable=False)
    validation_flags = Column(Text, default="[]", nullable=False)  # JSON array string
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    report = relationship("UploadedReport", back_populates="records")
    guest_identity = relationship("GuestIdentity", back_populates="records")
    matches = relationship("GuestIdentityMatch", back_populates="guest_record", cascade="all, delete-orphan")


class GuestIdentityMatch(Base):
    __tablename__ = "guest_identity_matches"

    id = Column(Integer, primary_key=True, index=True)
    guest_record_id = Column(Integer, ForeignKey("guest_records.id", ondelete="CASCADE"), nullable=False, index=True)
    guest_identity_id = Column(Integer, ForeignKey("guest_identities.id", ondelete="CASCADE"), nullable=False, index=True)
    match_type = Column(String(50), nullable=False)  # exact_confirmation, name_room_overlap, name_fuzzy, manual_merge
    confidence_score = Column(Float, default=1.0, nullable=False)
    status = Column(String(50), default="confirmed", nullable=False)  # proposed, confirmed, rejected
    review_notes = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    guest_record = relationship("GuestRecord", back_populates="matches")
    guest_identity = relationship("GuestIdentity", back_populates="matches")


class StayAssessment(Base):
    __tablename__ = "stay_assessments"

    id = Column(Integer, primary_key=True, index=True)
    guest_identity_id = Column(Integer, ForeignKey("guest_identities.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Mode A: continuous_stay | Mode B: repeated_appearance
    mode = Column(String(50), nullable=False, index=True)
    is_active_in_window = Column(Boolean, default=True, nullable=False, index=True)
    
    stay_duration_days = Column(Integer, default=0, nullable=False)
    reporting_dates_count = Column(Integer, default=0, nullable=False)
    first_date = Column(Date, nullable=True)
    last_date = Column(Date, nullable=True)
    
    # Serialized details
    date_list = Column(Text, default="[]", nullable=False)  # JSON array string
    confirmation_numbers = Column(Text, default="[]", nullable=False)  # JSON array string
    room_numbers = Column(Text, default="[]", nullable=False)  # JSON array string
    evidence_source = Column(String(100), nullable=True)
    
    # Status: Verified, Needs Verification, Rejected
    verification_status = Column(String(50), default="Verified", nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    guest_identity = relationship("GuestIdentity", back_populates="assessments")


class ReportingCalendar(Base):
    __tablename__ = "reporting_calendar"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    reporting_date = Column(Date, nullable=False, index=True)
    report_id = Column(Integer, ForeignKey("uploaded_reports.id", ondelete="SET NULL"), nullable=True)
    has_report = Column(Boolean, default=True, nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    is_in_active_window = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('property_id', 'reporting_date', name='uq_property_date'),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # upload, preview, import, replace, delete, merge, export
    entity_type = Column(String(100), nullable=True)  # report, guest, match, setting
    entity_id = Column(String(100), nullable=True)
    details = Column(Text, default="{}", nullable=False)  # JSON payload
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="audit_logs")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
