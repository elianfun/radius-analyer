from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.utils import fix_row

router = APIRouter(prefix="/api/stats", tags=["stats"])

# 同一個衍生表：只掃 Accept，壓縮成每 MAC 一筆
_LAST_AUTH = """
    last_auth AS (
        SELECT username, MAX(authdate) AS last_accept
        FROM radpostauth
        WHERE reply = 'Access-Accept'
        GROUP BY username
    )
"""


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """
    一次 WITH 查詢取得所有摘要數字：
    radpostauth 只掃一次（僅 Accept），再跟 radcheck 比對。
    """
    result = db.execute(text(f"""
        WITH {_LAST_AUTH},
        mac_status AS (
            SELECT
                rc.username,
                la.last_accept,
                CASE
                    WHEN la.last_accept IS NULL                              THEN 'never'
                    WHEN la.last_accept >= NOW() - INTERVAL 30 DAY          THEN 'active_30'
                    WHEN la.last_accept >= NOW() - INTERVAL 90 DAY          THEN 'active_90'
                    ELSE                                                          'inactive'
                END AS status
            FROM radcheck rc
            LEFT JOIN last_auth la ON rc.username = la.username
            WHERE rc.attribute = 'Cleartext-Password'
        )
        SELECT
            COUNT(*)                                        AS total,
            SUM(status IN ('active_30'))                    AS active_30,
            SUM(status IN ('active_30','active_90'))        AS active_90,
            SUM(status = 'never')                           AS never,
            SUM(status IN ('never','inactive'))             AS inactive_90
        FROM mac_status
    """)).mappings().one()

    disabled = db.execute(text(
        "SELECT COUNT(DISTINCT username) FROM radusergroup WHERE groupname = 'daloRADIUS-Disabled-Users'"
    )).scalar()

    expired = db.execute(text(
        "SELECT COUNT(*) FROM radcheck WHERE attribute = 'Expiration' AND STR_TO_DATE(value, '%d %b %Y') < NOW()"
    )).scalar()

    # reject 總數：直接 COUNT，不 JOIN（快）
    total_accept = db.execute(text("SELECT COUNT(*) FROM radpostauth WHERE reply = 'Access-Accept'")).scalar()
    total_reject = db.execute(text("SELECT COUNT(*) FROM radpostauth WHERE reply = 'Access-Reject'")).scalar()

    return {
        **dict(result),
        "disabled": disabled,
        "expired": expired,
        "total_accept": total_accept,
        "total_reject": total_reject,
    }


@router.get("/by-group")
def get_by_group(db: Session = Depends(get_db)):
    """各群組的設備總數及 90 天活躍數"""
    result = db.execute(text(f"""
        WITH {_LAST_AUTH}
        SELECT
            COALESCE(ug.groupname, '（無群組）') AS groupname,
            COUNT(DISTINCT rc.username)           AS total,
            SUM(la.last_accept >= NOW() - INTERVAL 90 DAY) AS active_90
        FROM radcheck rc
        LEFT JOIN radusergroup ug ON rc.username = ug.username
        LEFT JOIN last_auth    la ON rc.username = la.username
        WHERE rc.attribute = 'Cleartext-Password'
        GROUP BY ug.groupname
        ORDER BY total DESC
    """))
    return [dict(r) for r in result.mappings().all()]


@router.get("/top-devices")
def get_top_devices(limit: int = 20, db: Session = Depends(get_db)):
    """認證最頻繁的設備（只統計 Accept）"""
    result = db.execute(text("""
        WITH top AS (
            SELECT username, COUNT(*) AS accept_count, MAX(authdate) AS last_accept
            FROM radpostauth
            WHERE reply = 'Access-Accept'
            GROUP BY username
            ORDER BY accept_count DESC
            LIMIT :lim
        )
        SELECT
            t.username AS mac,
            CONVERT(CONVERT(ui.firstname USING binary) USING utf8mb4) AS description,
            ug.groupname,
            t.accept_count,
            t.last_accept
        FROM top t
        LEFT JOIN userinfo    ui ON t.username = ui.username
        LEFT JOIN radusergroup ug ON t.username = ug.username
        ORDER BY t.accept_count DESC
    """), {"lim": limit})
    return [fix_row(dict(r)) for r in result.mappings().all()]


@router.get("/daily")
def get_daily(days: int = 30, db: Session = Depends(get_db)):
    """過去 N 天每日認證數（時間範圍先過濾，縮小掃描量）"""
    result = db.execute(text("""
        SELECT
            DATE(authdate)                                                    AS date,
            SUM(reply = 'Access-Accept')                                      AS accept,
            SUM(reply = 'Access-Reject')                                      AS reject,
            COUNT(DISTINCT CASE WHEN reply = 'Access-Accept' THEN username END) AS unique_devices
        FROM radpostauth
        WHERE authdate >= NOW() - INTERVAL :days DAY
        GROUP BY DATE(authdate)
        ORDER BY date ASC
    """), {"days": days})
    return [dict(r) for r in result.mappings().all()]


@router.get("/reject-hotspot")
def get_reject_hotspot(days: int = 7, limit: int = 20, db: Session = Depends(get_db)):
    """近 N 天拒絕最多的 MAC（先用時間過濾縮小資料量）"""
    result = db.execute(text("""
        SELECT
            username AS mac,
            COUNT(*) AS reject_count,
            MAX(authdate) AS last_attempt
        FROM radpostauth
        WHERE reply = 'Access-Reject'
          AND authdate >= NOW() - INTERVAL :days DAY
        GROUP BY username
        ORDER BY reject_count DESC
        LIMIT :lim
    """), {"days": days, "lim": limit})
    return [dict(r) for r in result.mappings().all()]
