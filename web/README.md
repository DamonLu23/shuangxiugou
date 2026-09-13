# web/ 前端（双形态）

## 形态 1：本地版（主路径，零服务器）

```bash
npm run local
```

生成 `web/local/dist/`（`data.js` 内嵌公开数据包：白名单企业/岗位/好物），
双击 `index.html` 即可使用（file:// 安全，无任何后端依赖）。

- 数据随仓库每周更新，`git pull` 后重新 `npm run local` 即得最新
- 报岗位/申诉/纠错入口跳转 GitHub Issue 模板（无需后端）

## 形态 2：在线 SPA（可选自托管）

```bash
npm install && npm run build   # 产物 dist/，配 Vite proxy + FastAPI 后端
npm run dev                    # 开发：/api 代理到 127.0.0.1:8000
```

在线部署可选（非主路径）：传统部署见 DEPLOY.md。零成本优先推荐本地形态。
