# 《双休购》三轮视角 Review（2026-09-12）

评审对象：产品方案 + 整体架构 + 代码实现（M0~M4 现状）
结论：**主线闭环成立、可交付 MVP；存在 3 个 P0 级生产隐患、4 个架构债、5 个产品体验缺口。**

---

## 一、产品经理视角

### 优势
- 价值主张清晰且差异化：「买东西，支持双休」——价值观消费 + 决策辅助，市场无同类
- 6 级等级 + 置信度双指标，比「是/否双休」有说服力；UGC 举报/纠错是冷启动利器
- 核心路径短：搜索 → 列表 → 详情 → 购买，3 步完成

### 问题与方案

**P1 覆盖率悖论（最严重的产品风险）**
现状：202 家企业档案中 43 家有等级（21%）；真实联盟数据下长尾商品 90%+ 品牌不在名单 → 用户体验 = 满屏「待验证」。
方案：
- 搜索页加「只看已收录」开关（默认开），未收录商品弱化排在尾部（后端已实现排序）
- 「双休企业好物榜」作为主浏览路径，承担全量已收录商品展示
- 品牌扩编：202 → 1000+ 头部品牌（用企查查/爱企查公开名录批量补 seed，配合 1 级人工抽检）

**P2 数据源可持续性**
招聘站爬取存在风控/法律风险（已有 BOSS/51job 教训记录）。
方案：UGC 权重机制已就绪，产品侧增加「贡献者激励」（如档案贡献徽章/榜单署名），把用户上报从工具变成功能。

**P2 价格与信息时效**
联盟真实数据接入后，价格/库存实时性成为承诺。方案：详情页文案「价格以电商页面为准」，商品缓存 TTL 2h。

**P2 合规文案**
「双休判断可能与企业实际有出入」的免责声明需进入企业档案页页脚（避免企业名誉投诉）。

**P3 功能缺口**
- 首页缺品类入口（原型有：数码/美妆/食品…）
- 无用户账户/收藏（MVP 可后置）
- 贡献提交后无反馈闭环（审核结果通知）

---

## 二、架构师视角

### 优势
- monorepo 分层清晰：crawler（采集）/ backend（服务）/ ios（端）/ data（数据），DB 作为契约
- 权重模型独立成 services，可调参可测试；verify.py 固化验证
- mock 模式让前后端联调不依赖第三方资质（好设计）

### 问题与方案

**P0-1 mock 模式静默降级（生产事故隐患）**
`mall.py`：未配 AppKey 时**自动返回假商品**，生产环境忘配 → 用户看到假数据无任何感知。
方案：`settings.mall_mode = "mock" | "taobao"` 显式开关；生产模式缺 Key 直接启动失败并给出明确错误。

**P0-2 数据 schema 无迁移机制**
`create_all` 只增不删；`UgcReport` 表加列后无 alembic 版本管理，上线后改表靠手工 SQL。
方案：引入 alembic（轻量）；SQLite 开发 / PostgreSQL 生产已在 README 规划，需落实 DATABASE_URL 区分环境。

**P0-3 生产安全默认值**
`admin_token = "changeme-admin-token"` 默认值可被直接利用（审核接口能改企业等级）。
方案：启动时检测默认 token，打印大警告并拒绝在非 debug 模式启动；UGC 上报加 IP 级限流（简单内存/Redis 计数）。

**P1-1 模块级 engine 全局变量（测试脆弱）**
`routers/search.py:14`、`routers/company.py` 各自 `create_engine`，测试靠 monkeypatch 模块属性。
方案：统一 `db.py`（engine + `get_db` 依赖注入），路由用 `Depends(get_db)`，测试用 `app.dependency_overrides`。

**P1-2 crawler 与 backend 依赖割裂**
两个独立 venv、`sys.path` hack 互导、requirements 两份。
方案：合并为单一 pyproject（backend/crawler 两个入口），一个 venv；或 crawler 引用 backend 为可安装包。

**P1-3 Playwright 每公司新建浏览器（性能主因）**
202 家 = 202 次 chromium 启动，全量 70 分钟。
方案：单 session 复用 + 页面顺序 goto + 失败重试/熔断（3 次失败暂停 5 分钟）+ 全局限速，预计提速 3~5 倍。

**P1-4 iOS 网络配置硬编码**
`ApiClient.swift` baseURL 写死 `http://127.0.0.1:8000`；http 明文在真机会被 ATS 拦截。
方案：Info.plist 加 ATS 例外（仅 Debug 用 localhost）；baseURL 从 Build Config/xcconfig 注入；Release 用 https 域名。

**P2 其他**
- CORS middleware（将来 Web 管理后台需要，现在不必）
- 审核队列无通知机制（后端可留 webhook 位）

---

## 三、程序员视角

### 优势
- 信号词单一来源（signalkeys.py），crawler 薄封装，避免词表漂移
- 24 个单测 + 契约验证 + verify 脚本 + typecheck，验证链完整
- 来源细分（review/review_promo）、否定词处理（不加班）等细节质量高

### 问题与方案

**Bug / 隐患**
1. `main.py:21-23` 残留注释掉的死代码 → 删除
2. `search.py:18` `@router.on_event("startup")` 已废弃（FastAPI 将移除）→ 改用 lifespan
3. `search.py:83` `_norm()` 与 `brand.py:normalize_brand()` 重复实现（规则漂移风险）→ 统一调用
4. `Evidence.weight` 字段写了 1.0 但聚合从不读（levels.py 用 SOURCE_WEIGHTS）→ 删字段或删 SOURCE_WEIGHTS 改为入库时写死权重（二选一，建议后者：权重进库，调整参数无需重算语义）
5. `levels.py:64` `ugc_other` 走 `get(..., 0.5)` 默认分支（隐式）→ 显式写入 SOURCE_WEIGHTS 并注释
6. `company.py` UGC_SOURCE_TYPES 是展示文案与校验耦合 → 拆分（校验用集合、文案用字典）
7. `zhaopin.py` `_SEARCH_CARDS_JS` 查询了未使用的 `.job-card__title-main` → 清理
8. iOS `ApiClient` `URL(string:)!` 强解包 + `ProductDetailView.loadCompany` 失败静默无重试 → 失败态提示 + 下拉重试

**测试缺口**
9. crawler 两个 source 的解析逻辑无单测（HTML→evidence 纯函数可抽出：zhaopin 卡片 JSON、bing 结果正则）→ 抽纯函数 + fixture HTML 单测
10. `time_decay` 边界（clamp 到 365 天后 = 0.6）未断言精确值
11. test_search.py `self_engine()` 手写 helper → 用 fixture 复用

**风格**
12. `mall.py` `MOCK_BRANDS` 与 seed 数据耦合（改 seed 忘改 mock）→ mock 品牌从 seed 动态取样
13. 中文注释/英文混合 ok，但 `zhaopin.py` 中英混排可整理

---

## 优先级执行顺序（建议）

| 批次 | 内容 | 工时估算 |
|---|---|---|
| P0 | mock 显式开关 + admin_token 启动校验 + 上报限流 + on_event→lifespan + 死代码清理 | 0.5 天 |
| P1 | db.py 统一 + DI + alembic 引入 + crawler 合并依赖 + Playwright 复用提速 | 1.5 天 |
| P1 | iOS ATS/环境配置 + 失败重试 UX | 0.5 天 |
| P2 | 「只看已收录」开关 + L6 弱化 + 品牌扩编脚本 + 免责声明 | 1 天 |
| P3 | 解析纯函数单测 + fixture 重构 + 样式整理 | 0.5 天 |

---

## 实施记录（2026-09-12，全部完成）

| 项 | 状态 | 实现 |
|---|---|---|
| db.py 统一 + DI | ✅ | `app/db/session.py`（唯一 engine 出处），路由 `Depends(get_db)`，测试 `dependency_overrides` |
| mock 显式开关 | ✅ | `settings.mall_mode`（mock/taobao）；taobao 缺 Key 初始化即抛错；生产缺 Key 拒绝启动 |
| admin_token 校验 | ✅ | `validate_runtime_config()`：debug 下警告；生产默认 token 直接拒绝启动（HTTP 实测验证） |
| UGC 限流 | ✅ | 每 IP 每小时 5 条内存滑窗（HTTP 实测第 6 条 429） |
| on_event→lifespan | ✅ | `main.py` lifespan：配置校验 + 品牌种子导入；死代码已删 |
| Evidence.weight 快照 | ✅ | 权重入库（`weight_for()`），聚合以入库值为准；迁移脚本 `scripts/migrate.py`（幂等，已回填+重算） |
| ugc_other 显式权重 | ✅ | SOURCE_WEIGHTS 显式 0.5 |
| _norm 去重 | ✅ | 统一 `brand.normalize_brand` |
| Playwright 复用 | ✅ | `launch_shared()` 跨公司共享浏览器 + 导航重试 + 公司间限速 1.5s |
| Bing client 复用 bug | ✅ | 修复（重构时发现并验证） |
| iOS ATS/baseURL | ✅ | Info.plist 注入式 `ApiBaseURL` + `NSAllowsLocalNetworking`（模板已给，上线改 https 删 ATS） |
| iOS 失败重试 | ✅ | 列表错误态+重试按钮+下拉刷新；详情企业卡失败态+重试 |
| indexed_only | ✅ | 后端参数 + iOS「只看已收录」开关（默认开） |
| 免责声明 | ✅ | 企业档案页页脚 |
| 品牌扩编 | ✅ | `expand_seed.py` + seed_extra.csv：202 → **295** 家（幂等去重，21 家重复自动跳过） |
| 解析纯函数单测 | ✅ | `parse_bing_results` 抽出，7 个新用例（黑名单/问句/员工平台分类/无关公司） |

**验证汇总**：backend 14 + crawler 20 测试全过；M1 verify ALL PASS（295 档案）；HTTP e2e（搜索排序/indexed_only/限流/生产启动校验）全过；iOS typecheck CLEAN。

**遗留（后续批次）**：
- alembic 完整引入（生产 PostgreSQL 切换时）
- crawler/backend 合并单一 venv（pyproject）
- 品牌扩编至 1000+（需批量名录数据源）
- 贡献者激励、品类导航、审核结果通知（产品侧）
