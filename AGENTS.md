# AGENTS.md — 双休购

> 白名单模式开源项目：只推荐严格执行双休（L1/L2）的企业及其在招岗位、代表商品。
> 面向用户的页面/接口**只展示白名单**，永不展示负面评级。
> 做数据采集、导出、发布前，先加载 skill `data-weekly-refresh`。

## 硬约束（任何改动都不得违反）

1. **白名单承诺**：对外数据/接口/页面只允许出现 L1/L2 企业；L3~L6 只存在于本地数据层，
   严禁对外展示、导出或提交。
2. **保守数据策略**：`export_data.py --full` 全量产物只写入 `data/local/`（已 gitignore），
   **绝不提交**；开源数据包只含 `companies.json`（仅白名单）、`jobs.json`、`goods.csv`。
3. **证据只存结论**：只保存公开链接 + 命中关键词 + 日期 + 打分，不存帖子/岗位/合同正文。
4. **采集边界**：不接入已验证不可用的源（BOSS/51job 等）；不直抓小红书（签名风控），
   其内容经 Bing 站点限定间接获取。新增数据源前先看 `docs/sources.md`。

## 目录

| 目录 | 职责 |
|---|---|
| `crawler/` | 采集与评分：`pipeline.py`（证据）、`collect_jobs.py`（岗位）、`collect_goods.py`（商品候选）、`fetch_lists.py`（榜单扩编）、`import_seed.py` |
| `backend/` | FastAPI 服务 + 等级聚合（`app/services/levels.py`）+ `scripts/export_data.py` 数据导出 |
| `web/` | Vue3 SPA + 本地静态版（`npm run local` 生成 `web/local/dist`） |
| `data/` | 开源数据包（周更）+ `companies/seed.csv`（企业池，当前 1019 家） |
| `docs/` | `sources.md`（数据源权威说明）、M1 验证记录、资质清单 |
| `.opencode/skills/` | 可加载运维 runbook |

## 环境

- 两个独立 venv：`crawler/.venv`、`backend/.venv`（均 Python 3.9；CI 用 3.11）
- crawler 通过 `sys.path` 引用 backend 模块（如 `app.services.levels`），不要「整理」掉
- 数据库 `data/shuangxiugou.db` 不入库（gitignore），由脚本本地生成
- 采集是长任务：每家企业约 25~35s；批量跑用后台 + 日志（`data/local/*.log`）

## 常用命令

```bash
# 测试（改代码后必须全过）
cd crawler && .venv/bin/python -m pytest tests/ -q     # 87 个
cd backend && .venv/bin/python -m pytest tests/ -q     # 53 个
cd web && npm test                                      # 5 个

# 数据验证 / 导出 / 本地站点
cd crawler && .venv/bin/python verify.py                # 数据一致性校验
cd backend && .venv/bin/python scripts/export_data.py   # 生成公开制品
cd web && npm run local                                 # 重建本地版 bundle
```

## 数据周更 / 采集运维

完整 runbook 见 skill `data-weekly-refresh`（`.opencode/skills/data-weekly-refresh/SKILL.md`）：
榜单扩编 → 分片证据采集 → 岗位老化 → 导出发布。

## 已知坑（省得重新踩）

- **Bing 证据 0 条属正常**：自动化流量下 Bing 会返回「诱饵结果」（与查询无关的页面），
  解析规则要求公司名 + 信号词同时命中，会安全丢弃；不是 bug
- **京东商品搜索不可用**：登录墙 + React SPA；商品候选走苏宁（`sources/suning.py`），
  只取标题/SKU，不存链接与价格
- **CI 空 DB 状态回灌**：`pipeline.py` 启动时从 `data/companies.json` 回灌白名单历史证据，
  白名单企业每轮全采；聚合以 DB 全量证据为准（防止分片周更导致白名单震荡）
- **岗位老化语义**：只有本轮成功采集的来源才会老化旧岗位，采集失败不误删
- **榜单长 key 匹配率低**：如「中芯国际集成电路制造」，口碑搜索命中率偏低，属已知限制

## 提交规范

- 风格：`feat(phaseN)/fix/test/chore/refactor` + 中文说明，一次提交聚焦一件事
- 数据类提交附来源健康报告（`data/source_health*.md`）
- 禁止提交：`.env`、`data/*.db`、`data/local/`、任何 L3~L6 全量数据
