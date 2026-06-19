import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306, user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()

# radpostauth 的 username 樣本
cur.execute("SELECT username, reply, authdate FROM radpostauth ORDER BY authdate DESC LIMIT 10")
print('=== radpostauth 最新 10 筆 ===')
for r in cur.fetchall():
    print(f'  {r}')

# radpostauth 非 MAC username 的數量
cur.execute(r"SELECT COUNT(DISTINCT username) FROM radpostauth WHERE username NOT REGEXP '^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$'")
print('\nradpostauth 非MAC帳號數:', cur.fetchone()[0])

cur.execute(r"SELECT DISTINCT username FROM radpostauth WHERE username NOT REGEXP '^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$' LIMIT 10")
print('非MAC樣本:')
for r in cur.fetchall():
    print(f'  {r[0]}')

# userinfo 的 T/L 帳號是否出現在 radpostauth
cur.execute("SELECT ui.username FROM userinfo ui WHERE EXISTS (SELECT 1 FROM radpostauth rp WHERE rp.username = ui.username) LIMIT 5")
print('\nuserinfo 有出現在 radpostauth 的帳號:')
for r in cur.fetchall():
    print(f'  {r[0]}')

# radusergroup 裡的非 MAC 帳號
cur.execute(r"SELECT DISTINCT username FROM radusergroup WHERE username NOT REGEXP '^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$' LIMIT 10")
print('\nradusergroup 非MAC帳號:')
for r in cur.fetchall():
    print(f'  {r[0]}')

# 群組和 MAC
cur.execute("SELECT groupname, COUNT(*) FROM radusergroup GROUP BY groupname")
print('\n群組分布（含MAC）:')
for r in cur.fetchall():
    print(f'  {r}')

conn.close()
