# web/ 站部署说明

## 前端（静态）—— Cloudflare Pages 或 Vercel 免费托管

1. 推送 GitHub 仓库后，Cloudflare Pages → Create project → 连接仓库
2. Build settings:
   - Build command: `npm run build`
   - Output directory: `dist`
3. 环境变量（Pages 设置 → Environment variables）：
   - `VITE_API_BASE=https://api.your-domain.com`（后端域名；本地开发不设则用相对 /api + Vite proxy）

## 后端 —— 海外 VPS（免备案）

```bash
# 依赖
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 生产模式配置（必须！）
export DEBUG=false
export ADMIN_TOKEN="<强随机串>"
export MALL_MODE=mock        # 本项目不使用联盟，固定 mock 提示即可
export DATABASE_URL=postgresql://user:pass@localhost/shuangxiugou   # 生产换 PG

# 表与迁移
.venv/bin/python scripts/migrate.py

# 运行（systemd 或 supervisor）
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

反代（Nginx）示例：

```nginx
server {
    listen 443 ssl;
    server_name api.your-domain.com;
    location / { proxy_pass http://127.0.0.1:8000; }
}
```

## 数据更新（本地手动）

```bash
cd crawler && .venv/bin/python -u collect_jobs.py && cd ../backend && .venv/bin/python scripts/export_data.py
```

周更由 GitHub Actions 自动执行（.github/workflows/data-refresh.yml）。