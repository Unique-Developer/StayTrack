from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import SystemSetting, Property, User
from app.schemas.models import SettingsResponse, SettingsUpdateRequest
from app.core.config import settings
from app.analytics.stay_detector import recalculate_all_analytics
from app.api.deps import get_current_user, log_audit

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    def get_val(k: str, default: str) -> str:
        s = db.query(SystemSetting).filter(SystemSetting.key == k).first()
        return s.value if s else default

    return SettingsResponse(
        rolling_window_days=int(get_val("rolling_window_days", str(settings.DEFAULT_ROLLING_WINDOW_DAYS))),
        continuous_stay_days=int(get_val("continuous_stay_days", str(settings.DEFAULT_CONTINUOUS_STAY_DAYS))),
        min_appearance_days=int(get_val("min_appearance_days", str(settings.DEFAULT_MIN_APPEARANCE_DAYS))),
        departure_convention=get_val("departure_convention", settings.DEFAULT_DEPARTURE_CONVENTION),
        property_timezone=get_val("property_timezone", settings.DEFAULT_TIMEZONE),
        retention_days=settings.RETENTION_DAYS
    )

@router.put("", response_model=SettingsResponse)
def update_settings(
    req: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    updates = {}
    if req.rolling_window_days is not None:
        updates["rolling_window_days"] = str(req.rolling_window_days)
    if req.continuous_stay_days is not None:
        updates["continuous_stay_days"] = str(req.continuous_stay_days)
    if req.min_appearance_days is not None:
        updates["min_appearance_days"] = str(req.min_appearance_days)
    if req.departure_convention is not None:
        updates["departure_convention"] = str(req.departure_convention)
    if req.property_timezone is not None:
        updates["property_timezone"] = str(req.property_timezone)

    for k, v in updates.items():
        s = db.query(SystemSetting).filter(SystemSetting.key == k).first()
        if s:
            s.value = v
        else:
            db.add(SystemSetting(key=k, value=v, description="Configured setting"))

    db.commit()

    prop = db.query(Property).first()
    prop_id = prop.id if prop else 1
    recalculate_all_analytics(db, prop_id)

    log_audit(db, current_user.id, "update_settings", "system_settings", details=updates)
    return get_settings(db)
