from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.utils import fix_row
import os, paramiko
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

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


@router.delete("/reject-records")
def delete_reject_records(db: Session = Depends(get_db)):
    """刪除 radpostauth 中所有 Access-Reject 紀錄"""
    count = db.execute(text("SELECT COUNT(*) FROM radpostauth WHERE reply = 'Access-Reject'")).scalar()
    db.execute(text("DELETE FROM radpostauth WHERE reply = 'Access-Reject'"))
    db.commit()
    return {"deleted": count}


def _query_replication(host: str, label: str) -> dict:
    ssh_user    = os.getenv("SSH_USER", "root")
    ssh_key     = os.getenv("SSH_KEY_FILE", os.path.expanduser("~/.ssh/id_ed25519"))
    ssh_pass    = os.getenv("SSH_PASSWORD", "") or None
    db_pass     = os.getenv("DB_ROOT_PASSWORD", "")
    node = {"host": host, "label": label, "error": None}
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if os.path.exists(ssh_key):
            client.connect(host, username=ssh_user, key_filename=ssh_key, timeout=10)
        else:
            client.connect(host, username=ssh_user, password=ssh_pass, timeout=10)
        _, stdout, _ = client.exec_command(
            f"mysql -u root -p{db_pass} --batch -e 'SHOW REPLICA STATUS' 2>/dev/null"
            f" && echo '---MASTER---'"
            f" && mysql -u root -p{db_pass} --batch -e 'SHOW BINLOG STATUS' 2>/dev/null"
        )
        out = stdout.read().decode().strip()
        client.close()

        parts      = out.split("---MASTER---")
        slave_out  = parts[0].strip()
        master_out = parts[1].strip() if len(parts) > 1 else ""

        if not slave_out:
            node["error"] = "無 Replica 設定"
            return node

        lines   = slave_out.split("\n")
        headers = lines[0].split("\t")
        values  = lines[1].split("\t") if len(lines) > 1 else []
        row     = dict(zip(headers, values))

        # MASTER STATUS
        node["master_file"] = ""
        node["master_pos"]  = 0
        if master_out:
            ml = master_out.split("\n")
            if len(ml) >= 2:
                mrow = dict(zip(ml[0].split("\t"), ml[1].split("\t")))
                node["master_file"] = mrow.get("File", "")
                node["master_pos"]  = int(mrow.get("Position", 0) or 0)

        lag_raw = row.get("Seconds_Behind_Master", "0")
        lag = int(lag_raw) if lag_raw and lag_raw.isdigit() else 0
        io_run  = row.get("Slave_IO_Running", "Unknown")
        sql_run = row.get("Slave_SQL_Running", "Unknown")
        last_err = row.get("Last_Error") or row.get("Last_IO_Error") or row.get("Last_SQL_Error") or ""

        read_pos    = int(row.get("Read_Master_Log_Pos") or 0)
        exec_pos    = int(row.get("Exec_Master_Log_Pos") or 0)
        relay_bytes = int(row.get("Relay_Log_Space") or 0)
        events      = int(row.get("Slave_Non_Transactional_Groups") or 0)

        node.update({
            "io_running":      io_run,
            "sql_running":     sql_run,
            "io_state":        row.get("Slave_IO_State", ""),
            "seconds_behind":  lag,
            "last_error":      last_err.strip(),
            "master_host":     row.get("Master_Host", ""),
            "master_log_file": row.get("Master_Log_File", ""),
            "read_pos":        read_pos,
            "exec_pos":        exec_pos,
            "pending_events":  max(read_pos - exec_pos, 0),
            "relay_log_mb":    round(relay_bytes / 1024 / 1024, 1),
            "events_applied":  events,
            "ok": io_run == "Yes" and sql_run == "Yes" and lag < 10,
        })
    except Exception as e:
        node["error"] = str(e)
    return node


@router.get("/replication")
def get_replication():
    hosts = [
        (os.getenv("SSH_HOST_1", "192.168.50.22"), ".22"),
        (os.getenv("SSH_HOST_2", "192.168.50.23"), ".23"),
    ]
    results = [None, None]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(_query_replication, h, l): i for i, (h, l) in enumerate(hosts)}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()
    return results


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
