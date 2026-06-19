from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.utils import fix_row
import os

router = APIRouter(prefix="/api/accounts", tags=["accounts"])
INACTIVE_DAYS = int(os.getenv("INACTIVE_DAYS", "90"))

# 核心衍生表：每個 MAC 的最後成功認證時間（只掃 Accept，一次壓縮）
_LAST_AUTH = """
    last_auth AS (
        SELECT username, MAX(authdate) AS last_accept
        FROM radpostauth
        WHERE reply = 'Access-Accept'
        GROUP BY username
    )
"""

# radcheck 基本資料（含設備備註、群組、到期日）
_MAC_INFO = """
    mac_info AS (
        SELECT
            rc.username AS mac,
            CONVERT(CONVERT(ui.firstname USING binary) USING utf8mb4) AS description,
            ug.groupname,
            ex.value    AS expiration,
            ui.creationdate
        FROM radcheck rc
        LEFT JOIN userinfo      ui ON rc.username = ui.username
        LEFT JOIN radusergroup  ug ON rc.username = ug.username
        LEFT JOIN radcheck      ex ON rc.username = ex.username AND ex.attribute = 'Expiration'
        WHERE rc.attribute = 'Cleartext-Password'
    )
"""


@router.get("/inactive")
def get_inactive(days: int = None, db: Session = Depends(get_db)):
    """N 天內未成功認證的設備"""
    threshold = days or INACTIVE_DAYS
    result = db.execute(text(f"""
        WITH {_LAST_AUTH}, {_MAC_INFO}
        SELECT
            m.mac, m.description, m.groupname, m.expiration, m.creationdate,
            la.last_accept
        FROM mac_info m
        LEFT JOIN last_auth la ON m.mac = la.username
        WHERE la.last_accept IS NULL
           OR la.last_accept < NOW() - INTERVAL :days DAY
        ORDER BY la.last_accept ASC
    """), {"days": threshold})
    return [fix_row(dict(r)) for r in result.mappings().all()]


@router.get("/never")
def get_never(db: Session = Depends(get_db)):
    """從未成功認證的設備"""
    result = db.execute(text(f"""
        WITH {_LAST_AUTH}, {_MAC_INFO}
        SELECT m.mac, m.description, m.groupname, m.expiration, m.creationdate
        FROM mac_info m
        LEFT JOIN last_auth la ON m.mac = la.username
        WHERE la.last_accept IS NULL
        ORDER BY m.creationdate ASC
    """))
    return [fix_row(dict(r)) for r in result.mappings().all()]


@router.get("/disabled")
def get_disabled(db: Session = Depends(get_db)):
    """已停用的設備"""
    result = db.execute(text(f"""
        WITH {_LAST_AUTH}, {_MAC_INFO}
        SELECT m.mac, m.description, m.groupname, m.creationdate, la.last_accept
        FROM mac_info m
        LEFT JOIN last_auth la ON m.mac = la.username
        WHERE m.groupname = 'daloRADIUS-Disabled-Users'
        ORDER BY la.last_accept DESC
    """))
    return [fix_row(dict(r)) for r in result.mappings().all()]


@router.get("/expired")
def get_expired(db: Session = Depends(get_db)):
    """有到期日的設備及狀態"""
    result = db.execute(text(f"""
        WITH {_LAST_AUTH}, {_MAC_INFO}
        SELECT
            m.mac, m.description, m.groupname, m.expiration, m.creationdate,
            la.last_accept,
            CASE
                WHEN STR_TO_DATE(m.expiration, '%d %b %Y') < NOW()
                    THEN 'expired'
                WHEN STR_TO_DATE(m.expiration, '%d %b %Y') < NOW() + INTERVAL 30 DAY
                    THEN 'expiring_soon'
                ELSE 'valid'
            END AS exp_status
        FROM mac_info m
        LEFT JOIN last_auth la ON m.mac = la.username
        WHERE m.expiration IS NOT NULL
        ORDER BY STR_TO_DATE(m.expiration, '%d %b %Y') ASC
    """))
    return [fix_row(dict(r)) for r in result.mappings().all()]


@router.get("/")
def list_all(db: Session = Depends(get_db)):
    """所有設備及最後認證時間"""
    result = db.execute(text(f"""
        WITH {_LAST_AUTH}, {_MAC_INFO}
        SELECT
            m.mac, m.description, m.groupname, m.expiration, m.creationdate,
            la.last_accept
        FROM mac_info m
        LEFT JOIN last_auth la ON m.mac = la.username
        ORDER BY la.last_accept DESC
    """))
    return [fix_row(dict(r)) for r in result.mappings().all()]


@router.delete("/{mac}")
def delete_account(mac: str, db: Session = Depends(get_db)):
    check = db.execute(
        text("SELECT username FROM radcheck WHERE username = :u AND attribute = 'Cleartext-Password' LIMIT 1"),
        {"u": mac}
    ).fetchone()
    if not check:
        raise HTTPException(status_code=404, detail="設備不存在")
    for table in ("radcheck", "radreply", "radusergroup", "userinfo"):
        db.execute(text(f"DELETE FROM {table} WHERE username = :u"), {"u": mac})
    db.commit()
    return {"deleted": mac}
