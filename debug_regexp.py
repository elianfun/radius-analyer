import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306, user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM radcheck WHERE attribute = 'Cleartext-Password'")
print('Total Cleartext-Password:', cur.fetchone()[0])

cur.execute(r"SELECT COUNT(*) FROM radcheck WHERE attribute = 'Cleartext-Password' AND username NOT REGEXP '^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$'")
print('After REGEXP filter:', cur.fetchone()[0])

cur.execute(r"SELECT username FROM radcheck WHERE attribute = 'Cleartext-Password' AND username NOT REGEXP '^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$' LIMIT 5")
print('Sample non-MAC:', cur.fetchall())

cur.execute("SELECT username FROM radcheck WHERE attribute = 'Cleartext-Password' LIMIT 5")
print('Sample raw:', cur.fetchall())

conn.close()
