import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')

servers = [
    {'host': '192.168.50.22', 'label': '主機 .22'},
    {'host': '192.168.50.23', 'label': '主機 .23'},
]

for s in servers:
    print(f"\n{'='*55}")
    print(f"  {s['label']} ({s['host']})")
    print(f"{'='*55}")
    try:
        conn = pymysql.connect(host=s['host'], port=3306,
                               user='radius', password='StrongradIusPass',
                               database='radius', connect_timeout=10)
        cur = conn.cursor()

        # 所有索引
        cur.execute("SHOW INDEX FROM radpostauth")
        rows = cur.fetchall()
        indexes = {}
        for r in rows:
            name = r[2]
            if name not in indexes:
                indexes[name] = []
            indexes[name].append(r[4])

        print(f"  radpostauth 索引：")
        expected = ['idx_pa_reply_user_date', 'idx_pa_authdate']
        deleted  = ['idx_pa_username_date']
        for name, cols in indexes.items():
            cols_str = ', '.join(cols)
            if name in expected:
                status = '[OK 新索引]'
            elif name in deleted:
                status = '[!! 應已刪除]'
            elif name == 'PRIMARY':
                status = '[PRIMARY]'
            else:
                status = ''
            print(f"    {status:<16} {name}  ({cols_str})")

        for exp in expected:
            if exp not in indexes:
                print(f"    [!! 缺少]      {exp}")
        for d in deleted:
            if d in indexes:
                print(f"    [!! 未刪除]    {d}")

        # 複寫狀態
        cur.execute("SHOW SLAVE STATUS")
        slave = cur.fetchone()
        if slave:
            io  = slave[10]
            sql = slave[11]
            lag = slave[32]
            err = slave[19] or slave[36] or '無'
            print(f"\n  複寫狀態：")
            print(f"    Slave_IO_Running  : {io}")
            print(f"    Slave_SQL_Running : {sql}")
            print(f"    Seconds_Behind    : {lag}")
            print(f"    Last_Error        : {err}")
            ok = '正常' if io == 'Yes' and sql == 'Yes' and (lag or 0) < 10 else '異常'
            print(f"    → 整體狀態        : {ok}")
        else:
            print(f"\n  複寫狀態：此節點無 Slave 設定")

        conn.close()
    except Exception as e:
        print(f"  [ERROR] {e}")
