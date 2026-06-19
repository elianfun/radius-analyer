import pymysql, sys, time
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306, user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()

def timed(label, sql, params=None):
    t = time.time()
    cur.execute(sql, params or {})
    rows = cur.fetchall()
    elapsed = time.time() - t
    print(f'[{elapsed:.2f}s] {label}: {rows[0] if len(rows)==1 else f"{len(rows)} rows"}')

LAST_AUTH = """
    last_auth AS (
        SELECT username, MAX(authdate) AS last_accept
        FROM radpostauth
        WHERE reply = 'Access-Accept'
        GROUP BY username
    )
"""

timed('summary (CTE)', f"""
    WITH {LAST_AUTH},
    mac_status AS (
        SELECT rc.username, la.last_accept,
            CASE
                WHEN la.last_accept IS NULL                     THEN 'never'
                WHEN la.last_accept >= NOW() - INTERVAL 30 DAY THEN 'active_30'
                WHEN la.last_accept >= NOW() - INTERVAL 90 DAY THEN 'active_90'
                ELSE 'inactive'
            END AS status
        FROM radcheck rc
        LEFT JOIN last_auth la ON rc.username = la.username
        WHERE rc.attribute = 'Cleartext-Password'
    )
    SELECT
        COUNT(*) AS total,
        SUM(status IN ('active_30')) AS active_30,
        SUM(status IN ('active_30','active_90')) AS active_90,
        SUM(status = 'never') AS never,
        SUM(status IN ('never','inactive')) AS inactive_90
    FROM mac_status
""")

timed('inactive 90d list', f"""
    WITH {LAST_AUTH}
    SELECT rc.username, la.last_accept
    FROM radcheck rc
    LEFT JOIN last_auth la ON rc.username = la.username
    WHERE rc.attribute = 'Cleartext-Password'
      AND (la.last_accept IS NULL OR la.last_accept < NOW() - INTERVAL 90 DAY)
    ORDER BY la.last_accept ASC
""")

timed('by-group', f"""
    WITH {LAST_AUTH}
    SELECT COALESCE(ug.groupname,'無群組') AS grp, COUNT(DISTINCT rc.username) AS total,
           SUM(la.last_accept >= NOW() - INTERVAL 90 DAY) AS active_90
    FROM radcheck rc
    LEFT JOIN radusergroup ug ON rc.username = ug.username
    LEFT JOIN last_auth    la ON rc.username = la.username
    WHERE rc.attribute = 'Cleartext-Password'
    GROUP BY ug.groupname
""")

timed('daily 30d', """
    SELECT DATE(authdate), SUM(reply='Access-Accept'), SUM(reply='Access-Reject')
    FROM radpostauth
    WHERE authdate >= NOW() - INTERVAL 30 DAY
    GROUP BY DATE(authdate)
""")

timed('top-devices 20', """
    SELECT username, COUNT(*) AS cnt, MAX(authdate)
    FROM radpostauth
    WHERE reply = 'Access-Accept'
    GROUP BY username
    ORDER BY cnt DESC
    LIMIT 20
""")

conn.close()
