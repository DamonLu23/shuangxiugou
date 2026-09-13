# 在线部署（可选·自托管）

> 当前主路径是「本地版」（`npm run local`，零服务器）。
> 以下为社区壮大、有人愿意自托管在线服务时的部署手册（非主路径）。

## 前端（在线 SPA）

```bash
npm install && npm run build   # 产物 dist/
```

托管到 Cloudflare Pages / Vercel / 自有 Nginx 均可（Build command: `npm run build`）。

## 后端 —— 海外 VPS（免备案）

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

export DEBUG=false
export ADMIN_TOKEN="<强随机串>"
export MALL_MODE=mock
export DATABASE_URL=postgresql://user:pass@localhost/shuangxiugou   # 生产换 PG

.venv/bin/python scripts/migrate.py
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Nginx 反代示例：

```nginx
server {
    listen 443 ssl;
    server_name api.your-domain.com;
    location / { proxy_pass http://127.0.0.1:8000; }
}
```

## 成本提示（在线形态）

- 前端静态托管：¥0（Cloudflare Pages/Vercel 免费档）
- 后端 VPS：香港/新加坡轻量 ¥25~35/月（按年付更低）
- 域名：.com 约 ¥60~80/年
- SSL：Let's Encrypt / Cloudflare 免费

> 注意：在线服务面向大陆用户时推荐前端+后端同机部署在香港 VPS（对大陆线路好）；
> Cloudflare Pages 免费 CDN 大陆访问不稳定。保守策略下在线站仅展示白名单数据。

## 数据更新（在线形态）

```bash
cd crawler && .venv/bin/python -u collect_jobs.py
cd ../backend && .venv/bin/python scripts/export_data.py
```

周更由 GitHub Actions 自动执行（.github/workflows/data-refresh.yml），本地形态无需此步。
