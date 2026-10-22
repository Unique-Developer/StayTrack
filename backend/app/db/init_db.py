import datetime
from sqlalchemy.orm import Session
from app.db.session import engine, Base, SessionLocal
from app.db.models import User, Property, SystemSetting
from app.core.security import hash_password
from app.core.config import settings

def init_db(db: Session = None):
    # Create all tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    try:
        # 1. Seed Default Admin User
        admin_user = db.query(User).filter(User.email == settings.DEFAULT_ADMIN_EMAIL).first()
        if not admin_user:
            admin_user = User(
                email=settings.DEFAULT_ADMIN_EMAIL,
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                full_name="Motel Owner",
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            print(f"[Init DB] Created default admin user: {settings.DEFAULT_ADMIN_EMAIL}")

        # Also seed admin@staytrack.com as alias if default is .local
        if settings.DEFAULT_ADMIN_EMAIL == "admin@staytrack.local":
            alt_admin = db.query(User).filter(User.email == "admin@staytrack.com").first()
            if not alt_admin:
                alt_admin = User(
                    email="admin@staytrack.com",
                    hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                    full_name="Motel Owner",
                    role="admin",
                    is_active=True
                )
                db.add(alt_admin)
                print("[Init DB] Created alias admin user: admin@staytrack.com")

        # 2. Seed Default Property
        prop = db.query(Property).filter(Property.property_code == settings.DEFAULT_PROPERTY_CODE).first()
        if not prop:
            prop = Property(
                name=settings.DEFAULT_PROPERTY_NAME,
                property_code=settings.DEFAULT_PROPERTY_CODE,
                timezone=settings.DEFAULT_TIMEZONE,
                address="Stafford, VA"
            )
            db.add(prop)
            print(f"[Init DB] Created default property: {settings.DEFAULT_PROPERTY_NAME} ({settings.DEFAULT_PROPERTY_CODE})")

        # 3. Seed Default System Settings
        default_settings = [
            ("rolling_window_days", str(settings.DEFAULT_ROLLING_WINDOW_DAYS), "Number of distinct reporting dates in rolling window analysis"),
            ("continuous_stay_days", str(settings.DEFAULT_CONTINUOUS_STAY_DAYS), "Threshold days for Mode A continuous stay detection"),
            ("min_appearance_days", str(settings.DEFAULT_MIN_APPEARANCE_DAYS), "Minimum distinct reporting dates for Mode B repeated appearance detection"),
            ("departure_convention", settings.DEFAULT_DEPARTURE_CONVENTION, "Stay calculation formula (checkin_plus_nights)"),
            ("property_timezone", settings.DEFAULT_TIMEZONE, "Motel local timezone"),
        ]

        for key, val, desc in default_settings:
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if not setting:
                db.add(SystemSetting(key=key, value=val, description=desc))

        # 4. Backfill Report Run Datetimes from stored PDFs if missing
        from app.db.models import UploadedReport
        import re
        reports = db.query(UploadedReport).filter(
            (UploadedReport.report_run_datetime == None) | 
            (UploadedReport.report_run_datetime.like("Report Run Date%"))
        ).all()
        if reports:
            import pdfplumber
            for r in reports:
                pdf_path = settings.STORAGE_DIR / r.stored_filename
                if pdf_path.exists():
                    try:
                        with pdfplumber.open(pdf_path) as pdf:
                            txt = pdf.pages[0].extract_text() or ""
                            m_date = re.search(r'Report Run Date:\s*([A-Za-z0-9\s,]+?)(?=\n|Report Run Time|User:|$)', txt, re.IGNORECASE)
                            m_time = re.search(r'Report Run Time:\s*([0-9:]+\s*(?:AM|PM)?)', txt, re.IGNORECASE)
                            if m_date and m_time:
                                d_str = ' '.join(m_date.group(1).split())
                                t_str = ' '.join(m_time.group(1).split())
                                r.report_run_datetime = f"{d_str} • {t_str}"
                            elif m_date:
                                r.report_run_datetime = ' '.join(m_date.group(1).split())
                    except Exception as err:
                        print(f"[Init DB] Could not backfill report #{r.id}: {err}")

        db.commit()
        print("[Init DB] Database initialization completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"[Init DB Error] {e}")
        raise e
    finally:
        if close_db:
            db.close()

if __name__ == "__main__":
    init_db()
