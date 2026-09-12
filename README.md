# 双休购

> 找工作，只搜双休企业；买东西，只荐双休企业。

「双休购」是一个**白名单模式**的开源项目：只推荐严格执行双休（周末两天休息）的企业及其在招岗位、代表商品。不展示也不评价任何企业的负面信息。

- **求职搜索**：搜岗位 → 只展示双休企业的在招岗位（智联采集 + 用户上报，周更）
- **好物目录**：搜品类 → 只推荐双休企业的代表商品（社区维护）
- **数据透明**：所有结论附公开证据链接，可自查、可复核、可申诉（48h）
- **前端网站**（`web/`）：Vue 3 白名单站，部署见 [web/DEPLOY.md](web/DEPLOY.md)

## 白名单承诺

1. 所有面向用户的页面仅展示 **L1 严格双休 / L2 双休** 的企业
2. 永不展示负面评级、不评价未收录企业（你没被推荐 ≠ 你不好）
3. 企业可随时申诉更正（见 [APPEAL.md](APPEAL.md)）
4. 证据只链接不转述（数据来源均为公开招聘信息与公开讨论）

## 数据

`data/` 目录为开源数据包，每周自动更新（GitHub Actions），`git pull` 即得最新等级。

| 文件 | 内容 | 说明 |
|---|---|---|
| `companies.json` | 白名单企业档案 | 等级 + 置信度 + 证据链接，对外唯一权威 |
| `companies_all.json` | 全量档案（含 L3~L6） | 仅供本地研究/复现，禁止对外展示 |
| `evidences.json` | 证据明细 | 链接 + 关键词 + 日期，不存原文 |
| `jobs.json` | 白名单企业在招岗位快照（301+） | `collect_jobs.py` 周更 |
| `goods.csv` | 好物目录 | 社区 PR 维护（`company,品类,商品,官方链接`） |

### 等级体系

| 等级 | 含义 |
|---|---|
| L1 | 严格双休（双休 + 正常作息） |
| L2 | 双休（双休为主，偶有加班） |
| L3~L5 | 大小周 / 单休 / 996（**仅存于数据层，不对外展示**） |
| L6 | 暂无充分证据（白名单外） |

置信度 = Σ(来源权重 × 时间衰减)，多源交叉验证，证据可点击复核。

## 快速开始（复现数据）

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
# API 文档 http://127.0.0.1:8000/docs
```

## 贡献

欢迎以三种方式参与：

1. **提交证据**：PR 补充企业档案证据（offer/合同/公开报道链接），说明证据类型与时效
2. **好物目录**：PR 更新 `data/goods.csv`（只加白名单企业商品）
3. **企业申诉**：企业方请走 [APPEAL.md](APPEAL.md) 流程，一般 48h 内处理

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 免责声明

> 本项目的双休等级由公开招聘信息与公开讨论聚合而成，仅供参考，**不构成**对任何企业的法律评价。数据可能存在滞后或误差，请以企业官方信息为准。本项目为非商业开源项目，不对任何用法承担责任。

## 目录结构

```
data/       开源数据包（周更）
crawler/    采集器（证据 + 岗位）+ 评分算法 + 校验
backend/    FastAPI（求职/好物/档案/申诉/UGC 审核 API）
web/        白名单网站 SPA（Vue 3 + Vite，见 DEPLOY.md）
docs/       产品/资质/验证记录
ios/        （已弃用）早期 SwiftUI 原型，保留参考
```

## API 一览

| 接口 | 说明 |
|---|---|
| `GET /api/jobs/search?q=&city=` | 求职搜索（仅白名单 L1/L2 企业岗位） |
| `POST /api/jobs/report` | 用户上报岗位（审核后展示） |
| `GET /api/goods/search?q=` | 好物目录搜索（仅白名单企业商品） |
| `GET /api/companies` / `{id}` | 企业榜 / 白名单企业档案（含证据链接） |
| `POST /api/companies/{id}/appeal` | 企业申诉（48h 承诺） |
| `POST /api/companies/{id}/report` | 用户补充证据（审核队列） |
| `GET/POST /api/admin/*` | 管理端（X-Admin-Token 鉴权） |

## License

[MIT](LICENSE)