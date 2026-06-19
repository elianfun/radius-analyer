import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306, user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()

# userinfo 非MAC帳號有多少
cur.execute(r"SELECT COUNT(*) FROM userinfo WHERE username NOT REGEXP '^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$'")
print('userinfo 非MAC筆數:', cur.fetchone()[0])

cur.execute(r"SELECT username, firstname, creationdate FROM userinfo WHERE username NOT REGEXP '^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$' LIMIT 5")
print('非MAC userinfo 樣本:')
for r in cur.fetchall():
    print(f'  {r}')

# 一個 MAC 在 radcheck 可能有多筆（Cleartext-Password + Expiration）
cur.execute("SELECT username, attribute, value FROM radcheck WHERE username = (SELECT username FROM radcheck WHERE attribute='Expiration' LIMIT 1)")
print('\n一個有 Expiration 的 MAC 的 radcheck 內容:')
for r in cur.fetchall():
    print(f'  {r}')

# 90天沒認證的 MAC 數
cur.execute(r"""
    SELECT COUNT(DISTINCT rc.username) FROM radcheck rc
    WHERE rc.attribute = 'Cleartext-Password'
    AND NOT EXISTS (
        SELECT 1 FROM radpostauth rp
        WHERE rp.username = rc.username AND rp.reply = 'Access-Accept'
        AND rp.authdate >= NOW() - INTERVAL 90 DAY
    )
""")
print('\n90天內沒有成功認證的MAC數:', cur.fetchone()[0])

# 從未認證的 MAC 數
cur.execute(r"""
    SELECT COUNT(DISTINCT rc.username) FROM radcheck rc
    WHERE rc.attribute = 'Cleartext-Password'
    AND NOT EXISTS (
        SELECT 1 FROM radpostauth rp
        WHERE rp.username = rc.username AND rp.reply = 'Access-Accept'
    )
""")
print('從未成功認證的MAC數:', cur.fetchone()[0])

# 有 Expiration 且已過期的
cur.execute(r"""
    SELECT COUNT(*) FROM radcheck WHERE attribute = 'Expiration'
    AND STR_TO_DATE(value, '%d %b %Y') < NOW()
""")
print('已過期MAC數:', cur.fetchone()[0])

conn.close()
