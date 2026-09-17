# 数据源说明（2026-09 定版）

## 启用中的数据源

| 源 | 用途 | 实现 | 权重 | 备注 |
|---|---|---|---|---|
| 智联招聘 | 企业双休证据 + 岗位 | Playwright 渲染（`sources/zhaopin.py`） | job_post 0.4 | 两链路：搜索页 + 公司岗位页 |
| Bing 搜索片段 | 企业口碑证据 | httpx（`sources/bing_snippet.py`） | review 0.9 / review_promo 0.1 | 问句式标题仅按正文打分；含小红书站点限定模板 |
| UGC 用户提交 | 证据 + 岗位 | API 审核队列 | ugc_contract 1.0 / offer 0.9 / other 0.5 | 在线版表单 + GitHub Issue |
| 企业官网 | 岗位（L1/L2） | httpx + Playwright 兜底（`sources/official.py`） | —— | 逐家配置，见下 |
| 排行榜名录 | 种子企业池扩编 | httpx + 纯解析（`sources/list_rankings.py`） | —— | 只生成企业候选，不产生证据 |
| 苏宁易购 | 商品候选（人工确认制） | httpx 静态页（`sources/suning.py`） | —— | 只存标题/SKU，不存链接价格 |

## 种子企业池：排行榜名录源（Phase 6 新增）

- 目的：把企业池从手工 295 家扩到榜单级规模（当前 **1019 家**，新增企业默认 L6）
- 流程：`fetch_lists.py` 抓取榜单 → 去重（同名/同 key/中文品牌包含）→ `seed_extra.csv`
  → `expand_seed.py` 合并进 `seed.csv` → `import_seed.py` 导入 DB
- 榜单源（`sources/list_rankings.py` 的 `LIST_SOURCES`，新增榜单=加 URL+解析函数）：
  | 榜单 | 家数 | 备注 |
  |---|---|---|
  | 2026《财富》中国500强 | 500 | 官方静态表 |
  | 2026《财富》世界500强（中国公司） | 122 | 官方静态表，与上表高度重叠 |
  | 2025 中企联中国企业500强 | 500 | 官方原版为图片，用公开转载表格 |
  | 2025 中国互联网综合实力前百家 | 95 | 官方为图片/PDF，用公开转载表格 |
- 周更分片：企业池变大后 CI 单次跑不完全量 → `pipeline.py --chunk K/N`
  （按 key 哈希分片，CI 用 `周数%4+1` 取一片，4 周覆盖全池；本地可用 `--stale-days 28` 增量）

## 商品候选源（人工确认制）

- 京东：**不可用**。2026-09 实测搜索页已改为登录墙 + React SPA（headless/有头均 302 到
  passport.jd.com，渲染后无商品节点）→ 原京东 Playwright 方案废弃
- 苏宁易购：可用。搜索页服务端渲染，httpx 直取；低频（白名单品牌 × 1 次搜索）+ 限速 2s
- 产物 `data/goods_candidates.csv`（标题/SKU/品类猜测，**不含链接与价格**）
  → 人工挑选代表商品 + 补官网/官方旗舰店链接 → 追加 `data/goods.csv`
- 命令：`cd crawler && .venv/bin/python collect_goods.py [--dry-run]`

## Bing 站点限定与降级行为

- `QUERY_TEMPLATES` 含 `{kw} 双休 site:xiaohongshu.com`、`{kw} 加班 site:xiaohongshu.com`：
  小红书内容经 Bing 索引间接获取（不直抓小红书：签名风控 + 账号风险），
  命中 `www.xiaohongshu.com` 自动按员工口碑（review 0.9）计权
- 注意：Bing 在自动化流量下会偶发返回「诱饵结果」（与查询无关的页面），
  现有解析要求公司名出现在标题/正文并命中信号词，诱饵会被自然丢弃（安全，但该轮无证据）

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
| 京东（商品搜索） | 登录墙 + React SPA，无商品节点（2026-09 实测） |
| 淘宝联盟 API | 免费但需媒体备案（ICP 域名+10 页面）；资质办下来前用苏宁替代 |
| 小红书（直抓） | 登录 + 请求签名风控；改走 Bing 站点限定（见上） |

## 配置与健康统计

- 源开关：`crawler/sources_config.json`（enabled / cityId / 限速）
- 健康统计：每次采集产出 `data/source_health.md`（证据源）、`data/source_health_jobs.md`（岗位源）
  与 `data/source_health_goods.md`（商品候选源），周更 PR 正文自动附带（成功/失败/条目数）
- 全量证据源复现：`crawler/pipeline.py`；岗位：`crawler/collect_jobs.py`；商品候选：`crawler/collect_goods.py`
- 企业池扩编：`crawler/fetch_lists.py` → `expand_seed.py` → `import_seed.py`（幂等）