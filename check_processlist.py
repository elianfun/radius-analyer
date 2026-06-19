import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306,
                       user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()
cur.execute("""
    SELECT ID, User, Host, Command, State, Time, LEFT(Info, 80) AS Info
    FROM information_schema.PROCESSLIST
    WHERE Command != 'Sleep'
    ORDER BY Time DESC
""")
rows = cur.fetchall()
if not rows:
    print("目前無任何 active query，可以安全建立索引")
else:
    print(f"{'ID':<10} {'Time':>6}s {'Command':<10} {'State':<35} Info")
    print("-"*100)
    for r in rows:
        flag = "  [!!! 危險]" if (r[5] or 0) > 30 else ""
        print(f"{r[0]:<10} {r[5] or 0:>6}s {r[3]:<10} {(r[4] or ''):<35} {r[6] or ''}{flag}")
conn.close()
