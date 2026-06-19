import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306,
                       user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()

queries = {
    "1. _LAST_AUTH CTE (所有頁面核心)": """
        SELECT username, MAX(authdate) AS last_accept
        FROM radpostauth
        WHERE reply = 'Access-Accept'
        GROUP BY username
    """,
    "2. top-devices (統計頁)": """
        SELECT rp.username, COUNT(*) AS accept_count, MAX(rp.authdate) AS last_accept
        FROM radpostauth rp
        WHERE rp.reply = 'Access-Accept'
        GROUP BY rp.username
        ORDER BY accept_count DESC
        LIMIT 20
    """,
    "3. daily (每日趨勢)": """
        SELECT DATE(authdate), COUNT(*)
        FROM radpostauth
        WHERE authdate >= NOW() - INTERVAL 30 DAY
        GROUP BY DATE(authdate)
    """,
    "4. reject-hotspot (拒絕熱點)": """
        SELECT username, COUNT(*)
        FROM radpostauth
        WHERE reply = 'Access-Reject'
          AND authdate >= NOW() - INTERVAL 7 DAY
        GROUP BY username
    """,
    "5. COUNT Accept": """
        SELECT COUNT(*) FROM radpostauth WHERE reply = 'Access-Accept'
    """,
}

for name, sql in queries.items():
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    cur.execute("EXPLAIN " + sql)
    rows = cur.fetchall()
    for r in rows:
        print(f"  table={r[2]}  type={r[3]}  key={r[5]}  rows={r[8]}  Extra={r[9]}")

conn.close()
