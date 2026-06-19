import pymysql, time, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306,
                       user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()

sql = """
SELECT username, MAX(authdate) AS last_authdate
FROM radpostauth
WHERE reply = 'Access-Accept'
GROUP BY username
"""

t = time.time()
cur.execute(sql)
rows = cur.fetchall()
elapsed = time.time() - t
print(f"[{elapsed:.3f}s] {len(rows)} rows returned")

conn.close()
