# RADIUS Analyzer

FreeRADIUS + daloRADIUS 的自訂 Web 管理介面，用於分析設備使用狀況並清理閒置帳號。

## 功能

- **首頁複寫狀態列**：即時顯示雙主 MariaDB 複寫健康狀態，包含 IO/SQL Thread、複寫延遲、同步差距交叉比對（本機作為主機 vs 對方已讀位置），支援手動重新整理
- **閒置設備**：列出 N 天內未成功認證的設備，支援批次刪除
- **從未認證**：列出從未通過認證的設備，支援一鍵全部刪除
- **已停用設備**：列出 daloRADIUS-Disabled-Users 群組的設備
- **到期設備**：列出有設定到期日的設備及狀態（已過期 / 即將到期 / 有效）
- **全部設備**：所有帳號清單，支援 MAC / 備註 / 群組搜尋
- **使用統計**：
  - 認證最頻繁設備 Top 20
  - **近期拒絕次數最多**：可能設定異常的設備（支援按時間範圍篩選）、**清除全部 Access-Reject 紀錄**
  - 每日認證趨勢（Accept / Reject / 不重複設備）
  - 群組分佈

## 系統需求

- Python 3.10+
- FreeRADIUS + daloRADIUS（MariaDB 後端）
- 資料來源：`radpostauth`（認證日誌）、`radcheck`、`userinfo`、`radusergroup`
- 複寫狀態功能需要能 SSH 進兩台 DB 主機（root 帳號）

## 安裝

```bash
git clone https://github.com/elianfun/radius-analyer.git
cd radius-analyer
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env 填入實際 DB 連線資訊
```

## 設定

編輯 `.env`：

```env
DB_HOST=192.168.50.22
DB_PORT=3306
DB_USER=radius
DB_PASSWORD=your_password
DB_NAME=radius
INACTIVE_DAYS=90

# 複寫狀態功能（SSH 進 DB 主機執行 SHOW REPLICA/BINLOG STATUS）
SSH_HOST_1=192.168.50.22
SSH_HOST_2=192.168.50.23
SSH_USER=root
SSH_KEY_FILE=~/.ssh/id_ed25519   # 優先使用 key；找不到才 fallback 到 SSH_PASSWORD
SSH_PASSWORD=your_ssh_password
DB_ROOT_PASSWORD=your_db_root_password

# 網頁登入認證
WEB_USER=admin
WEB_PASSWORD=your_web_password
SECRET_KEY=your_random_secret_key   # 用 python -c "import secrets; print(secrets.token_hex(32))" 產生
SESSION_TIMEOUT=1800                # 閒置逾時秒數（預設 30 分鐘）
```

## 啟動

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

瀏覽器開啟 `http://localhost:8002`

## 部署到 Linux（Ubuntu 24.04）

建議直接裝在 DB 主機上，本機連線效能最佳，多台部署亦可備援。

### 1. 安裝環境

```bash
apt install -y git python3-venv
git clone https://github.com/elianfun/radius-analyer.git /opt/radius-analyer
cd /opt/radius-analyer
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
# 編輯 .env，DB_HOST 設為 localhost
```

### 2. 資料庫授權

PyMySQL 連 `localhost` 時走 TCP（`127.0.0.1`），MariaDB 預設的 `radius@localhost` 僅允許 Unix socket，需額外補授權：

```bash
mysql -u root -p -e "GRANT ALL PRIVILEGES ON radius.* TO 'radius'@'127.0.0.1' IDENTIFIED BY 'your_password'; FLUSH PRIVILEGES;"
```

### 3. 複寫狀態 SSH 金鑰設定

複寫狀態功能透過 Paramiko 以 SSH key 連進 DB 主機執行查詢。若部署多台，每台需能 SSH 到自己與其他台：

```bash
# 在每台 DB 主機上產生 key（若尚未存在）
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ''

# 將本機 public key 加入自己的 authorized_keys
cat /root/.ssh/id_ed25519.pub >> /root/.ssh/authorized_keys

# 將本機 public key 複製到其他台的 authorized_keys
# （或反向：將其他台的 public key 貼到本機的 authorized_keys）
ssh-copy-id -i /root/.ssh/id_ed25519.pub root@<other-host>
```

`stats.py` 的 `_query_replication` 會優先使用 `SSH_KEY_FILE`（預設 `~/.ssh/id_ed25519`），找不到才 fallback 到 `SSH_PASSWORD`。

### 4. systemd 服務

```bash
cat > /etc/systemd/system/radius-analyer.service << 'EOF'
[Unit]
Description=RADIUS Analyzer Web UI
After=network.target mariadb.service

[Service]
WorkingDirectory=/opt/radius-analyer
ExecStart=/opt/radius-analyer/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8002
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable radius-analyer
systemctl start radius-analyer
```

瀏覽器開啟 `http://<server-ip>:8002`

## 網頁認證

登入後 session 儲存於加密 cookie，閒置超過 `SESSION_TIMEOUT` 秒自動登出。導覽列有登出按鈕可主動結束 session。

**變更密碼：**

```bash
nano /opt/radius-analyer/.env   # 修改 WEB_USER / WEB_PASSWORD
systemctl restart radius-analyer
```

## 技術架構

| 元件 | 說明 |
|------|------|
| FastAPI | Web 框架 |
| Jinja2 | HTML 模板 |
| SQLAlchemy + PyMySQL | 資料庫連線 |
| Paramiko | SSH 連線（複寫狀態查詢） |
| itsdangerous | Session cookie 簽署 |
| Chart.js | 圖表 |

## 雙主複寫設定

兩台 MariaDB 互為主從（dual-master），需設定 `auto_increment_offset` 讓各自產生不重疊的 ID，避免同時新增時發生主鍵衝突。

| 伺服器 | offset | increment | 產生的 ID |
|--------|--------|-----------|-----------|
| 192.168.50.22 | 1 | 2 | 奇數（1, 3, 5 …） |
| 192.168.50.23 | 2 | 2 | 偶數（2, 4, 6 …） |

寫入 `/etc/mysql/mariadb.conf.d/50-server.cnf`：

```ini
# .22
auto_increment_increment = 2
auto_increment_offset    = 1

# .23
auto_increment_increment = 2
auto_increment_offset    = 2
```

套用（不需重啟）：

```sql
SET GLOBAL auto_increment_increment = 2;
SET GLOBAL auto_increment_offset    = 1;   -- .23 改為 2
```

> **注意**：直接在單台 DB 手動 INSERT（不經由 daloRADIUS）時，若未先確認該台的 AUTO_INCREMENT 現值，仍有機率拿到與對方重疊的 ID 造成複寫中斷。請盡量透過 daloRADIUS 操作資料。

## 資料庫索引

`radpostauth` 為主要效能瓶頸（MAB 環境下資料成長快速），已建立以下索引：

| 索引名稱 | 欄位 | 用途 |
|---------|------|------|
| `idx_pa_reply_user_date` | `(reply, username, authdate)` | 所有主要查詢（_LAST_AUTH CTE、top-devices、統計計數） |
| `idx_pa_authdate` | `(authdate)` | 每日趨勢查詢（WHERE authdate >= NOW() - INTERVAL N DAY） |

建立方式（在 DB 伺服器本機執行，遠端連線會 timeout）：

```bash
mysql -u root -p radius -e "CREATE INDEX idx_pa_reply_user_date ON radpostauth (reply, username, authdate);"
mysql -u root -p radius -e "CREATE INDEX idx_pa_authdate ON radpostauth (authdate);"
```

## 維運工具

根目錄下有數個維運用 Python 腳本，需先設定 DB 連線（或直接修改腳本內的 host/password）：

| 腳本 | 說明 |
|------|------|
| `check_processlist.py` | 列出目前所有 active query，超過 30 秒標記為危險。執行 DDL（CREATE INDEX）前務必先跑此腳本確認無卡死的 SELECT |
| `kill_query.py` | KILL 指定 process ID，修改腳本內的 ID 後執行。用於清除卡死的 query 以解除 metadata lock |
| `verify_all_indexes.py` | 驗證 .22 / .23 兩台的 radpostauth 索引是否正確，並檢查複寫狀態 |
| `explain_queries.py` | 對所有主要查詢執行 EXPLAIN，確認是否有走到索引（type 欄位應為 ref 或 range，非 ALL） |

### 典型使用流程（新增索引前）

```bash
# 1. 確認無卡死的查詢
python3 check_processlist.py

# 2. 若有危險 query，修改 kill_query.py 內的 ID 後執行
python3 kill_query.py

# 3. 在 DB 伺服器本機執行 CREATE INDEX

# 4. 執行後驗證兩台同步
python3 verify_all_indexes.py
```

## 注意事項

- 本系統為 MAB（MAC Authentication Bypass）架構，所有帳號均為 MAC 位址
- 主要資料來源為 `radpostauth`，建議定期清理非必要紀錄以維持查詢效能
- `.env` 含有資料庫密碼，已加入 `.gitignore`，請勿提交至版本控制
- 執行 CREATE INDEX 期間 `radpostauth` 寫入會短暫排隊（metadata lock），RADIUS 認證本身不受影響
- 執行任何 DDL 前必須先確認無長時間執行的 SELECT，否則會造成 metadata lock 互相等待
