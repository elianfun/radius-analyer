# RADIUS Analyzer

FreeRADIUS + daloRADIUS 的自訂 Web 管理介面，用於分析設備使用狀況並清理閒置帳號。

## 功能

- **閒置設備**：列出 N 天內未成功認證的設備，支援批次刪除
- **從未認證**：列出從未通過認證的設備，支援一鍵全部刪除
- **已停用設備**：列出 daloRADIUS-Disabled-Users 群組的設備
- **到期設備**：列出有設定到期日的設備及狀態（已過期 / 即將到期 / 有效）
- **全部設備**：所有帳號清單，支援 MAC / 備註 / 群組搜尋
- **使用統計**：每日認證趨勢、群組分佈、Top 20 設備、拒絕熱點

## 系統需求

- Python 3.10+
- FreeRADIUS + daloRADIUS（MariaDB 後端）
- 資料來源：`radpostauth`（認證日誌）、`radcheck`、`userinfo`、`radusergroup`

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
```

## 啟動

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

瀏覽器開啟 `http://localhost:8002`

## 技術架構

| 元件 | 說明 |
|------|------|
| FastAPI | Web 框架 |
| Jinja2 | HTML 模板 |
| SQLAlchemy + PyMySQL | 資料庫連線 |
| Chart.js | 圖表 |

## 注意事項

- 本系統為 MAB（MAC Authentication Bypass）架構，所有帳號均為 MAC 位址
- 主要資料來源為 `radpostauth`，建議定期清理非必要紀錄以維持查詢效能
- `.env` 含有資料庫密碼，已加入 `.gitignore`，請勿提交至版本控制
