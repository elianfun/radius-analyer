import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = pymysql.connect(host='192.168.50.22', port=3306, user='radius', password='StrongradIusPass', database='radius', connect_timeout=5)
cur = conn.cursor()

cur.execute('SELECT MIN(authdate), MAX(authdate) FROM radpostauth')
r = cur.fetchone()
print(f'radpostauth 時間範圍: {r[0]} ~ {r[1]}')

cur.execute("""
    SELECT COUNT(*) FROM radcheck rc
    WHERE rc.attribute = 'Cleartext-Password'
    AND NOT EXISTS (
        SELECT 1 FROM radpostauth rp WHERE rp.username = rc.username AND rp.reply = 'Access-Accept'
    )
""")
print(f'從未成功登入帳號數: {cur.fetchone()[0]}')

cur.execute("""
    SELECT COUNT(*) FROM radcheck rc
    WHERE rc.attribute = 'Cleartext-Password'
    AND NOT EXISTS (
        SELECT 1 FROM radpostauth rp
        WHERE rp.username = rc.username
        AND rp.reply = 'Access-Accept'
        AND rp.authdate >= NOW() - INTERVAL 90 DAY
    )
""")
print(f'90 天未登入帳號數: {cur.fetchone()[0]}')

cur.execute('SELECT firstname, lastname, email, department, company, creationdate FROM userinfo LIMIT 3')
print('\nuserinfo 樣本:')
for r in cur.fetchall():
    print(f'  {r}')

cur.execute('SELECT planName, COUNT(*) FROM userbillinfo GROUP BY planName')
print('\n方案分布:')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]}')

cur.execute('SELECT username, value FROM radcheck WHERE attribute="Expiration" LIMIT 5')
print('\nExpiration 帳號樣本:')
for r in cur.fetchall():
    print(f'  {r}')

conn.close()
