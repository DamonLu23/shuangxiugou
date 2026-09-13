# 数据源说明（2026-09 定版）

## 启用中的数据源

| 源 | 用途 | 实现 | 权重 | 备注 |
|---|---|---|---|---|
| 智联招聘 | 企业双休证据 + 岗位 | Playwright 渲染（`sources/zhaopin.py`） | job_post 0.4 | 两链路：搜索页 + 公司岗位页 |
| Bing 搜索片段 | 企业口碑证据 | httpx（`sources/bing_snippet.py`） | review 0.9 / review_promo 0.1 | 问句式标题仅按正文打分 |
| UGC 用户提交 | 证据 + 岗位 | API 审核队列 | ugc_contract 1.0 / offer 0.9 / other 0.5 | 在线版表单 + GitHub Issue |
| 企业官网 | 岗位（L1/L2） | httpx + Playwright 兜底（`sources/official.py`） | —— | 逐家配置，见下 |

## 官网岗位源（Phase 5 新框架）

- 配置：`data/company_job_sources.csv`（company_name / careers_url / parser / enabled / note）
- 机制：官网是雇主实时在招列表 → 每次采集全量 upsert + active 老化 → **岗位关闭自动移除**
- 解析：`generic` 链接启发式（已排除产品/客服/FAQ 页），或 `selector:CSS选择器` 指定
- 当前状态：14 家白名单企业均已探测，**全部为 SPA / 私有加密 API / 域名不可达**，
  暂 `enabled=false`（探测结论写入 note 列）；配置一个专属适配即可启用（见下）

### 如何为一家企业启用官网采集（社区贡献路径）

1. 打开企业官网招聘页，若为服务端渲染 → 配置 `parser=generic` 试跑：
   `cd crawler && .venv/bin/python collect_jobs.py --dry-run --limit 1`
2. 若为 SPA：
   - 优先找其招聘系统（ATS）的公开 JSON API（如北森/大易有公开接口）
   - 或配置 CSS 选择器：`parser=selector:.job-list a.title`
3. 验证岗位标题/链接正确后，将 CSV 的 `enabled` 改为 `true`，提 PR
4. 已知需专属适配：Moka（API 加密）、字节 jobs.bytedance.com（私有 API）

## 已弃用数据源（勿重复接入）

| 源 | 原因 |
|---|---|
| BOSS 直聘 | 反爬强（code 37 / JS 挑战），需账号+代理方案 |
| 51job / m.51job | 阿里云 WAF 纯 JS 挑战 |
| 猎聘 | SPA 壳 + 登录门槛 |
| 看准网 | 已转型婚恋业务，无职场数据 |
| LinkedIn | 中国区业务关停 + 反爬严格（决策：不做） |
| 淘宝/京东联盟 | 产品转型为白名单目录后不再需要商品 API |

## 配置与健康统计

- 源开关：`crawler/sources_config.json`（enabled / cityId / 限速）
- 健康统计：每次采集产出 `data/source_health.md`（证据源）与 `data/source_health_jobs.md`（岗位源），
  周更 PR 正文自动附带（成功/失败/条目数）
- 全量证据源复现：`crawler/pipeline.py`；岗位：`crawler/collect_jobs.py`