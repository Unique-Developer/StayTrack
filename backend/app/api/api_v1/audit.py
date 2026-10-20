import json
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import AuditLog, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/logs")
def get_audit_logs(
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for l in logs:
        details_obj = {}
        try:
            details_obj = json.loads(l.details) if l.details else {}
        except Exception:
            details_obj = {"raw": l.details}

        items.append({
            "id": l.id,
            "user_id": l.user_id,
            "user_email": l.user.email if l.user else "System",
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "details": details_obj,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat()
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }
