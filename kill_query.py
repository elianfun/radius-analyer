import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = pymysql.connect(host='192.168.50.22', port=3306,
                       user='radius', password='StrongradIusPass', database='radius')
cur = conn.cursor()
cur.execute("KILL 979872")
print("KILL 979872 已送出")
conn.close()
